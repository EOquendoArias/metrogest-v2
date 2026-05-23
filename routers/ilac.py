import io
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
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
    db: Session = Depends(get_db)):

    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
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
    if ci:
        ci.intervalo_inicial_meses = ado; ci.intervalo_actual_meses = ado
    else:
        db.add(models.ConfigILAC(magnitud_id=mid,
                                   intervalo_inicial_meses=ado,
                                   intervalo_actual_meses=ado))
    if mag.calibraciones:
        ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
        ul.proxima_calibracion = ul.fecha_calibracion + relativedelta(months=ado)
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
    })

@router.post("/periodo/{mid}/guardar")
def guardar_periodo(mid: int, request: Request,
    intervalo: int = Form(...),
    metodo: str = Form("estandar"),
    justificacion: str = Form(""),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
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

    db.commit()
    return RedirectResponse(url=f"/calibraciones/magnitud/{mid}", status_code=302)


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

    return T.TemplateResponse(request, "ilac/frecuencias.html", {
        "usuario_actual":  u,
        "magnitud":        mag,
        "equipo":          mag.equipo,
        "ev":              ev,
        "ci":              ci,
        "registros":       registros,
        "hoy":             date.today(),
        "campos_f_labels": CAMPOS_F_LABELS,
    })
