import io
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
import utils.firma_electronica as firma
from utils.calculos import calcular_intervalo_inicial

router = APIRouter()
T = Jinja2Templates(directory="templates")

CAMPOS_F = ["f_incertidumbre","f_tipo","f_riesgo_emp","f_fabricante","f_deriva",
            "f_uso","f_ambiental","f_magnitud","f_similares","f_comparaciones",
            "f_verificaciones","f_transporte","f_personal","f_legal"]

@router.get("/riesgo/{mid}", response_class=HTMLResponse)
def riesgo_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag: raise HTTPException(status_code=404)
    ev = db.query(models.EvaluacionRiesgo).filter(
        models.EvaluacionRiesgo.magnitud_id == mid).first()
    error_exceso = request.query_params.get("error_exceso")
    return T.TemplateResponse(request, "ilac/riesgo.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "ev": ev, "hoy": date.today(), "campos_f": CAMPOS_F,
        "error_exceso": error_exceso,
        "requiere_confirmacion": request.query_params.get("requiere_confirmacion"),
        "error_firma": request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_riesgo"],
    })

@router.post("/riesgo/{mid}")
def guardar_riesgo(mid: int, request: Request,
    f_incertidumbre: int=Form(3), f_tipo: int=Form(3),
    f_riesgo_emp: int=Form(3), f_fabricante: int=Form(3),
    f_deriva: int=Form(3), f_uso: int=Form(3),
    f_ambiental: int=Form(3), f_magnitud: int=Form(3),
    f_similares: int=Form(3), f_comparaciones: int=Form(3),
    f_verificaciones: int=Form(3), f_transporte: int=Form(3),
    f_personal: int=Form(3), f_legal: int=Form(3),
    intervalo_fabricante_meses: str=Form(""),
    intervalo_adoptado_meses: str=Form(""),
    justificacion: str=Form(""),
    justificacion_exceso: str=Form(""),
    evaluado_por: str=Form(""),
    confirmar_edicion: str=Form(""),
    password: str=Form(""),
    db: Session = Depends(get_db)):

    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/riesgo/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag: raise HTTPException(status_code=404)

    fab = int(intervalo_fabricante_meses) if intervalo_fabricante_meses else None
    fs  = [f_incertidumbre,f_tipo,f_riesgo_emp,f_fabricante,f_deriva,f_uso,
           f_ambiental,f_magnitud,f_similares,f_comparaciones,
           f_verificaciones,f_transporte,f_personal,f_legal]
    sug = calcular_intervalo_inicial(fs, fab)
    ado = int(intervalo_adoptado_meses) if intervalo_adoptado_meses else sug
    pun = round(sum(fs)/len(fs), 2)

    # BLOQUEAR si adoptado > sugerido y no hay justificación
    if ado > sug and not justificacion_exceso.strip():
        return RedirectResponse(
            url=f"/ilac/riesgo/{mid}?error_exceso=1", status_code=302)

    ev = db.query(models.EvaluacionRiesgo).filter(
        models.EvaluacionRiesgo.magnitud_id == mid).first()

    # El §5.1 (registro de la calibración inicial) se hace una sola vez.
    # Re-editarlo requiere confirmación explícita del usuario.
    if ev is not None and confirmar_edicion != "si":
        return RedirectResponse(
            url=f"/ilac/riesgo/{mid}?requiere_confirmacion=1", status_code=302)

    v = dict(magnitud_id=mid,
             f_incertidumbre=f_incertidumbre, f_tipo=f_tipo,
             f_riesgo_emp=f_riesgo_emp, f_fabricante=f_fabricante,
             f_deriva=f_deriva, f_uso=f_uso, f_ambiental=f_ambiental,
             f_magnitud=f_magnitud, f_similares=f_similares,
             f_comparaciones=f_comparaciones, f_verificaciones=f_verificaciones,
             f_transporte=f_transporte, f_personal=f_personal, f_legal=f_legal,
             intervalo_fabricante_meses=fab, puntuacion_total=pun,
             intervalo_sugerido_meses=sug, intervalo_adoptado_meses=ado,
             justificacion=justificacion or None,
             justificacion_exceso=justificacion_exceso or None,
             evaluado_por=evaluado_por or None,
             fecha_evaluacion=date.today())
    if ev:
        for k, val in v.items(): setattr(ev, k, val)
    else:
        ev = models.EvaluacionRiesgo(**v); db.add(ev)

    ci = db.query(models.ConfigILAC).filter(
        models.ConfigILAC.magnitud_id == mid).first()
    if not ci:
        ci = models.ConfigILAC(magnitud_id=mid, intervalo_inicial_meses=ado,
                                 intervalo_actual_meses=ado)
        db.add(ci)
    # El §5.1 siempre fija el intervalo INICIAL (registro estable de la 1ª calibración)
    ci.intervalo_inicial_meses = ado

    # Solo controla el intervalo VIGENTE si ningún método avanzado (M1-M4/manual) lo maneja.
    # Así, cambiar el §5.1 no pisa las frecuencias definidas luego por los métodos.
    cals = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)
    ultima = cals[-1] if cals else None
    METODOS_AVANZADOS = ("deriva_m1", "caja-negra", "horas", "escalera",
                         "ajuste_manual", "estandar")
    if ultima is None or ultima.metodo_periodo not in METODOS_AVANZADOS:
        ci.intervalo_actual_meses = ado
        if ultima:
            ultima.proxima_calibracion = ultima.fecha_calibracion + relativedelta(months=ado)

    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "magnitudes_equipo", mid, "definir_intervalo_ilac_riesgo")
    if not ok:
        db.rollback()
        return RedirectResponse(url=f"/ilac/riesgo/{mid}?error_firma=1", status_code=302)

    db.commit()
    return RedirectResponse(url=f"/ilac/riesgo/{mid}", status_code=302)

@router.get("/riesgo/{mid}/pdf")
def pdf_ilac(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag: raise HTTPException(status_code=404)
    ev = db.query(models.EvaluacionRiesgo).filter(
        models.EvaluacionRiesgo.magnitud_id == mid).first()
    if not ev: raise HTTPException(status_code=404, detail="Sin evaluación ILAC registrada")
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_ilac
    pdf_bytes = generar_pdf_ilac(mag, ev, u, config)
    nombre = f"periodo_calibracion_{mag.nombre}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})

# ── NUEVO PERÍODO (segunda calibración en adelante) ───────────────────────────

@router.get("/periodo/{mid}", response_class=HTMLResponse)
def nuevo_periodo_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag: raise HTTPException(status_code=404)

    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    intervalo_actual = ci.intervalo_actual_meses if ci else 12

    from licencia import tiene_modulo
    modulo_avanzado = tiene_modulo("avanzado_ilac")

    calibraciones = db.query(models.Calibracion).filter(
        models.Calibracion.magnitud_id == mid
    ).order_by(models.Calibracion.fecha_calibracion.desc()).all()

    return T.TemplateResponse(request, "ilac/nuevo_periodo.html", {
        "usuario_actual": u,
        "magnitud": mag,
        "equipo": mag.equipo,
        "calibraciones": calibraciones,
        "intervalo_actual": intervalo_actual,
        "modulo_avanzado": modulo_avanzado,
        "error_firma": request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_estandar"],
    })

@router.post("/periodo/{mid}/guardar")
def guardar_periodo(mid: int, request: Request,
    intervalo: int = Form(...),
    metodo: str = Form("estandar"),
    justificacion: str = Form(""),
    password: str = Form(""),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/periodo/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag: raise HTTPException(status_code=404)

    # Aplicar tope máximo de 18 meses siempre
    intervalo = min(intervalo, 18)
    intervalo = max(intervalo, 1)

    # Actualizar o crear ConfigILAC
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    if ci:
        ci.intervalo_actual_meses = intervalo
        ci.metodo = metodo
    else:
        db.add(models.ConfigILAC(magnitud_id=mid,
                                   intervalo_inicial_meses=intervalo,
                                   intervalo_actual_meses=intervalo,
                                   metodo=metodo))

    # Actualizar proxima_calibracion + decisión de período en la última calibración
    if mag.calibraciones:
        ultima = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
        from dateutil.relativedelta import relativedelta
        ultima.proxima_calibracion    = ultima.fecha_calibracion + relativedelta(months=intervalo)
        ultima.metodo_periodo         = metodo
        ultima.justificacion_periodo  = justificacion or None

    # Registrar en historial de estados del equipo
    db.add(models.HistorialEstado(
        equipo_id=mag.equipo_id, usuario_id=u.id,
        estado_anterior=None, estado_nuevo="periodo_actualizado",
        motivo=f"{mag.nombre}: período {intervalo} meses ({metodo}). {justificacion}"
    ))

    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "magnitudes_equipo", mid, "definir_intervalo_ilac_estandar")
    if not ok:
        db.rollback()
        return RedirectResponse(url=f"/ilac/periodo/{mid}?error_firma=1", status_code=302)

    db.commit()
    return RedirectResponse(url=f"/calibraciones/magnitud/{mid}", status_code=302)


# ── M1 · ANÁLISIS DE DERIVA ───────────────────────────────────────────────────

@router.get("/deriva/{mid}", response_class=HTMLResponse)
def deriva_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)

    from licencia import tiene_modulo
    if not tiene_modulo("avanzado_ilac"):
        return RedirectResponse(url=f"/ilac/periodo/{mid}")

    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.deriva import analizar_deriva
    analisis = analizar_deriva(mag, ci)

    return T.TemplateResponse(request, "ilac/deriva.html", {
        "usuario_actual": u,
        "magnitud":       mag,
        "equipo":         mag.equipo,
        "analisis":       analisis,
        "error":          request.query_params.get("error"),
        "error_firma":    request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_deriva"],
    })


@router.post("/deriva/{mid}/aplicar")
def aplicar_deriva(mid: int, request: Request,
                   intervalo: int = Form(...),
                   justificacion: str = Form(""),
                   password: str = Form(""),
                   db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/deriva/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)

    # Tope 60 meses; arriba de 18 exige justificación escrita
    intervalo = max(1, min(intervalo, 60))
    if intervalo > 18 and not justificacion.strip():
        return RedirectResponse(url=f"/ilac/deriva/{mid}?error=justif", status_code=303)

    just_final = justificacion.strip() or f"Análisis de deriva M1 · {intervalo} meses"

    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    if ci:
        ci.intervalo_actual_meses = intervalo
        ci.metodo = "m1"
    else:
        db.add(models.ConfigILAC(magnitud_id=mid,
                                   intervalo_inicial_meses=intervalo,
                                   intervalo_actual_meses=intervalo,
                                   metodo="m1"))

    if mag.calibraciones:
        ultima = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
        ultima.proxima_calibracion   = ultima.fecha_calibracion + relativedelta(months=intervalo)
        ultima.metodo_periodo        = "deriva_m1"
        ultima.justificacion_periodo = just_final

    db.add(models.HistorialEstado(
        equipo_id=mag.equipo_id, usuario_id=u.id,
        estado_anterior=None, estado_nuevo="periodo_actualizado",
        motivo=f"{mag.nombre}: período {intervalo} meses (deriva M1). {just_final}"))

    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "magnitudes_equipo", mid, "definir_intervalo_ilac_deriva")
    if not ok:
        db.rollback()
        return RedirectResponse(url=f"/ilac/deriva/{mid}?error_firma=1", status_code=303)

    db.commit()
    return RedirectResponse(url=f"/calibraciones/magnitud/{mid}", status_code=303)


# ── Helper compartido para aplicar un período avanzado ────────────────────────

def _aplicar_periodo(db, request, u, mag, mid, intervalo, justificacion, metodo, etiqueta, accion_firma, password):
    """Guarda el intervalo de un método avanzado. Tope 60; >18 exige justificación."""
    intervalo = max(1, min(intervalo, 60))
    if intervalo > 18 and not justificacion.strip():
        return RedirectResponse(url=f"/ilac/{metodo}/{mid}?error=justif", status_code=303)

    just_final = justificacion.strip() or f"{etiqueta} · {intervalo} meses"

    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    if ci:
        ci.intervalo_actual_meses = intervalo
        ci.metodo = metodo
    else:
        db.add(models.ConfigILAC(magnitud_id=mid, intervalo_inicial_meses=intervalo,
                                   intervalo_actual_meses=intervalo, metodo=metodo))

    if mag.calibraciones:
        ultima = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
        ultima.proxima_calibracion   = ultima.fecha_calibracion + relativedelta(months=intervalo)
        ultima.metodo_periodo        = metodo
        ultima.justificacion_periodo = just_final

    db.add(models.HistorialEstado(
        equipo_id=mag.equipo_id, usuario_id=u.id,
        estado_anterior=None, estado_nuevo="periodo_actualizado",
        motivo=f"{mag.nombre}: período {intervalo} meses ({etiqueta}). {just_final}"))

    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "magnitudes_equipo", mid, accion_firma)
    if not ok:
        db.rollback()
        return RedirectResponse(url=f"/ilac/{metodo}/{mid}?error_firma=1", status_code=303)

    db.commit()
    return RedirectResponse(url=f"/calibraciones/magnitud/{mid}", status_code=303)


def _cargar_mag_avanzado(mid, request, db):
    """Valida usuario, magnitud y licencia. Retorna (u, mag, redirect|None)."""
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return None, None, RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)
    from licencia import tiene_modulo
    if not tiene_modulo("avanzado_ilac"):
        return u, mag, RedirectResponse(url=f"/ilac/periodo/{mid}")
    return u, mag, None


# ── M4 · ESCALERA ─────────────────────────────────────────────────────────────

@router.get("/escalera/{mid}", response_class=HTMLResponse)
def escalera_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.escalera import analizar_escalera
    analisis = analizar_escalera(mag, ci)
    return T.TemplateResponse(request, "ilac/escalera.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "analisis": analisis, "error": request.query_params.get("error"),
        "error_firma": request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_escalera"]})


@router.post("/escalera/{mid}/aplicar")
def aplicar_escalera(mid: int, request: Request, intervalo: int = Form(...),
                     justificacion: str = Form(""), password: str = Form(""),
                     db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/escalera/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)
    return _aplicar_periodo(db, request, u, mag, mid, intervalo, justificacion, "escalera", "Escalera M4",
                             "definir_intervalo_ilac_escalera", password)


# ── M2 · CAJA NEGRA ───────────────────────────────────────────────────────────

@router.get("/caja-negra/{mid}", response_class=HTMLResponse)
def caja_negra_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    pv = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id == mid).first()
    verifs = db.query(models.VerificacionIntermedia).filter(
        models.VerificacionIntermedia.magnitud_id == mid).all()
    from utils.caja_negra import analizar_caja_negra
    analisis = analizar_caja_negra(verifs, ci, pv)
    return T.TemplateResponse(request, "ilac/caja_negra.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "analisis": analisis, "error": request.query_params.get("error"),
        "error_firma": request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_caja_negra"]})


@router.post("/caja-negra/{mid}/aplicar")
def aplicar_caja_negra(mid: int, request: Request, intervalo: int = Form(...),
                       justificacion: str = Form(""), password: str = Form(""),
                       db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/caja-negra/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)
    return _aplicar_periodo(db, request, u, mag, mid, intervalo, justificacion, "caja-negra", "Caja negra M2",
                             "definir_intervalo_ilac_caja_negra", password)


# ── M3 · HORAS DE USO ─────────────────────────────────────────────────────────

@router.get("/horas/{mid}", response_class=HTMLResponse)
def horas_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.horas import analizar_horas
    # Permite previsualizar con parámetros de query (?limite=&acumuladas=&horas_mes=)
    def _f(name):
        v = request.query_params.get(name)
        try:    return float(v) if v not in (None, "") else None
        except: return None
    analisis = analizar_horas(ci, _f("limite"), _f("acumuladas"), _f("horas_mes"))
    return T.TemplateResponse(request, "ilac/horas.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "analisis": analisis, "error": request.query_params.get("error"),
        "error_firma": request.query_params.get("error_firma"),
        "significado_ilac": firma.SIGNIFICADOS["definir_intervalo_ilac_horas"]})


@router.post("/horas/{mid}/aplicar")
def aplicar_horas(mid: int, request: Request,
                  limite: float = Form(...), acumuladas: float = Form(0),
                  horas_mes: float = Form(...), intervalo: int = Form(...),
                  justificacion: str = Form(""), password: str = Form(""),
                  db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/ilac/horas/{mid}", status_code=303)
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)

    # Guardar la config de horas en ConfigILAC
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    if not ci:
        ci = models.ConfigILAC(magnitud_id=mid, intervalo_inicial_meses=12,
                                 intervalo_actual_meses=12)
        db.add(ci); db.flush()
    ci.horas_uso_limite     = limite
    ci.horas_uso_acumuladas = acumuladas
    return _aplicar_periodo(db, request, u, mag, mid, intervalo, justificacion, "horas", "Horas de uso M3",
                             "definir_intervalo_ilac_horas", password)


# ── PDFs de los métodos avanzados ─────────────────────────────────────────────

def _stream_pdf_metodo(mag, analisis, metodo, u, db):
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_metodos import generar_pdf_metodo
    pdf = generar_pdf_metodo(mag, analisis, metodo, u, config)
    nombre = f"{metodo}_{mag.nombre}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})


@router.get("/deriva/{mid}/pdf")
def pdf_deriva(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.deriva import analizar_deriva
    return _stream_pdf_metodo(mag, analizar_deriva(mag, ci), "deriva", u, db)


@router.get("/escalera/{mid}/pdf")
def pdf_escalera(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.escalera import analizar_escalera
    return _stream_pdf_metodo(mag, analizar_escalera(mag, ci), "escalera", u, db)


@router.get("/caja-negra/{mid}/pdf")
def pdf_caja_negra(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    pv = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id == mid).first()
    verifs = db.query(models.VerificacionIntermedia).filter(
        models.VerificacionIntermedia.magnitud_id == mid).all()
    from utils.caja_negra import analizar_caja_negra
    return _stream_pdf_metodo(mag, analizar_caja_negra(verifs, ci, pv), "caja-negra", u, db)


@router.get("/horas/{mid}/pdf")
def pdf_horas(mid: int, request: Request, db: Session = Depends(get_db)):
    u, mag, redir = _cargar_mag_avanzado(mid, request, db)
    if redir:
        return redir
    ci = db.query(models.ConfigILAC).filter(models.ConfigILAC.magnitud_id == mid).first()
    from utils.horas import analizar_horas
    def _f(name):
        v = request.query_params.get(name)
        try:    return float(v) if v not in (None, "") else None
        except: return None
    analisis = analizar_horas(ci, _f("limite"), _f("acumuladas"), _f("horas_mes"))
    return _stream_pdf_metodo(mag, analisis, "horas", u, db)


# ── FRECUENCIAS DE CALIBRACIÓN (vista consolidada) ────────────────────────────

CAMPOS_F_LABELS = [
    ("f_incertidumbre", "a)", "Incertidumbre de medición requerida"),
    ("f_tipo",          "b)", "Tipo de instrumento"),
    ("f_riesgo_emp",    "c)", "Riesgo de superar el EMP"),
    ("f_fabricante",    "d)", "Recomendación del fabricante"),
    ("f_deriva",        "e)", "Tendencia al desgaste y deriva"),
    ("f_uso",           "f)", "Intensidad de uso"),
    ("f_ambiental",     "g)", "Condiciones ambientales"),
    ("f_magnitud",      "h)", "Influencia de la magnitud medida"),
    ("f_similares",     "i)", "Datos de dispositivos similares"),
    ("f_comparaciones", "j)", "Frecuencia de comparaciones"),
    ("f_verificaciones","k)", "Verificaciones intermedias"),
    ("f_transporte",    "l)", "Riesgo de transporte"),
    ("f_personal",      "m)", "Capacitación del personal"),
    ("f_legal",         "n)", "Requisitos legales"),
]


def _meses_entre(d1, d2):
    if not d1 or not d2:
        return None
    rd = relativedelta(d2, d1)
    return rd.years * 12 + rd.months


@router.get("/frecuencias/{mid}", response_class=HTMLResponse)
def frecuencias_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()
    if not mag:
        raise HTTPException(status_code=404)

    ev = db.query(models.EvaluacionRiesgo).filter(
        models.EvaluacionRiesgo.magnitud_id == mid).first()
    ci = db.query(models.ConfigILAC).filter(
        models.ConfigILAC.magnitud_id == mid).first()

    # Calibraciones en orden cronológico (más antigua primero)
    calibraciones_raw = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)

    registros = []
    for i, c in enumerate(calibraciones_raw):
        intervalo = _meses_entre(c.fecha_calibracion, c.proxima_calibracion)
        prev = calibraciones_raw[i - 1] if i > 0 else None
        intervalo_prev = _meses_entre(prev.fecha_calibracion, prev.proxima_calibracion) if prev else None
        ok   = sum(1 for p in c.puntos if p.dentro_tolerancia is True)
        fail = sum(1 for p in c.puntos if p.dentro_tolerancia is False)
        registros.append({
            "num":              i + 1,
            "es_primera":       i == 0,
            "cal":              c,
            "intervalo_meses":  intervalo,
            "intervalo_anterior": intervalo_prev,
            "cambio_intervalo": intervalo != intervalo_prev if intervalo and intervalo_prev else False,
            "puntos_ok":        ok,
            "puntos_fail":      fail,
            "puntos_total":     len(c.puntos),
            "es_ultima":        False,  # se actualiza abajo
        })
    if registros:
        registros[-1]["es_ultima"] = True

    # Método que fijó el período vigente (según la última calibración)
    _MAP = {
        'deriva_m1':    ('M1 · Análisis de deriva', 'fa-chart-line',   'deriva',     'avanzado'),
        'caja-negra':   ('M2 · Caja negra',         'fa-box-archive',  'caja-negra', 'avanzado'),
        'horas':        ('M3 · Horas de uso',       'fa-clock',        'horas',      'avanzado'),
        'escalera':     ('M4 · Escalera',           'fa-stairs',       'escalera',   'avanzado'),
        'estandar':     ('Período estándar',        'fa-calendar-check','periodo',   'estandar'),
        'ajuste_manual':('Ajuste manual',           'fa-sliders',      'periodo',    'manual'),
    }
    metodo_vigente = None
    ult_cal = calibraciones_raw[-1] if calibraciones_raw else None
    mp = ult_cal.metodo_periodo if ult_cal else None
    if mp and mp in _MAP:
        nombre, icono, ruta, tipo = _MAP[mp]
        metodo_vigente = {
            "nombre": nombre, "icono": icono, "ruta": ruta, "tipo": tipo,
            "intervalo": ci.intervalo_actual_meses if ci else None,
            "justificacion": ult_cal.justificacion_periodo,
            "fecha": ult_cal.fecha_calibracion,
        }

    return T.TemplateResponse(request, "ilac/frecuencias.html", {
        "usuario_actual":  u,
        "magnitud":        mag,
        "equipo":          mag.equipo,
        "ev":              ev,
        "ci":              ci,
        "registros":       registros,
        "metodo_vigente":  metodo_vigente,
        "hoy":             date.today(),
        "campos_f_labels": CAMPOS_F_LABELS,
    })
