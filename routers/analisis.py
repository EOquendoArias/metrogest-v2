import io
from datetime import date, datetime
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
from utils.calculos import calcular_regresiones, calcular_semaforo

router = APIRouter()
T = Jinja2Templates(directory="templates")

# ── PÁGINA PRINCIPAL DE ANÁLISIS ──────────────────────────────────────────────

@router.get("/{cid}", response_class=HTMLResponse)
def analisis_page(cid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if not cal: raise HTTPException(status_code=404)

    mag    = cal.magnitud
    puntos = cal.puntos

    # Toggle incertidumbre — se guarda en la calibración
    usar_u = cal.usar_incertidumbre if hasattr(cal, 'usar_incertidumbre') else True

    # Recalcular semáforo según el toggle actual
    for p in puntos:
        p.dentro_tolerancia = calcular_semaforo(
            p.error,
            p.incertidumbre if usar_u else None,
            p.emp_punto
        )

    regs = []
    if len(puntos) >= 2 and mag and mag.tipo_instrumento != "discreto":
        regs = calcular_regresiones(puntos)

    hist = db.query(models.Calibracion).filter(
        models.Calibracion.magnitud_id == cal.magnitud_id,
        models.Calibracion.id != cid
    ).order_by(models.Calibracion.fecha_calibracion.desc()).limit(3).all()

    gs = cal.grado_regresion_sel
    mg = regs[0]["grado"] if regs and not gs else gs

    # ¿Es la segunda calibración o posterior?
    num_calibraciones = db.query(models.Calibracion).filter(
        models.Calibracion.magnitud_id == cal.magnitud_id
    ).count()
    es_segunda_o_posterior = num_calibraciones >= 2

    # Config ILAC existente
    config_ilac = db.query(models.ConfigILAC).filter(
        models.ConfigILAC.magnitud_id == cal.magnitud_id
    ).first() if mag else None

    return T.TemplateResponse(request, "analisis/analisis.html", {
        "usuario_actual": u,
        "calibracion": cal,
        "magnitud": mag,
        "equipo": mag.equipo if mag else None,
        "puntos": puntos,
        "regresiones": regs,
        "mejor_grado": mg,
        "grado_sel": gs,
        "historico": hist,
        "emp": mag.emp_valor if mag else None,
        "usar_incertidumbre": usar_u,
        "ok":   sum(1 for p in puntos if p.dentro_tolerancia is True),
        "fail": sum(1 for p in puntos if p.dentro_tolerancia is False),
        "aprobado": cal.resultado == "aprobado",
        "aprobado_por": cal.aprobado_por,
        "fecha_aprobacion": cal.fecha_aprobacion,
        "es_segunda_o_posterior": es_segunda_o_posterior,
        "config_ilac": config_ilac,
    })

# ── TOGGLE INCERTIDUMBRE ──────────────────────────────────────────────────────

@router.post("/{cid}/toggle-incertidumbre")
def toggle_incertidumbre(cid: int, request: Request,
                          usar: str = Form("true"), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if cal and hasattr(cal, 'usar_incertidumbre'):
        cal.usar_incertidumbre = (usar == "true")
        db.commit()
    return RedirectResponse(url=f"/analisis/{cid}", status_code=302)

# ── AGREGAR PUNTO ─────────────────────────────────────────────────────────────

@router.post("/{cid}/punto")
def agregar_punto(cid: int, request: Request,
    valor_patron: float = Form(...), valor_indicado: float = Form(...),
    incertidumbre: str = Form(""), tolerancia_inf: str = Form(""),
    tolerancia_sup: str = Form(""), emp_punto: str = Form(""),
    observacion: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if not cal: raise HTTPException(status_code=404)

    usar_u = cal.usar_incertidumbre if hasattr(cal, 'usar_incertidumbre') else True
    err   = round(valor_indicado - valor_patron, 8)
    u_val = float(incertidumbre) if incertidumbre and usar_u else None
    emp_p = float(emp_punto) if emp_punto else (cal.magnitud.emp_valor if cal.magnitud else None)
    ti = float(tolerancia_inf) if tolerancia_inf else (-abs(emp_p) if emp_p else None)
    ts = float(tolerancia_sup) if tolerancia_sup else (abs(emp_p) if emp_p else None)
    dentro = calcular_semaforo(err, u_val, emp_p)
    aeu = round(abs(err) + (u_val or 0), 8)

    n = db.query(models.PuntoCalibracion).filter(
        models.PuntoCalibracion.calibracion_id == cid).count()
    db.add(models.PuntoCalibracion(
        calibracion_id=cid, numero_punto=n+1,
        valor_patron=valor_patron, valor_indicado=valor_indicado, error=err,
        tolerancia_inf=ti, tolerancia_sup=ts,
        incertidumbre=float(incertidumbre) if incertidumbre else None,
        abs_error_mas_u=aeu, emp_punto=emp_p,
        dentro_tolerancia=dentro, observacion=observacion or None))
    db.commit()
    return RedirectResponse(url=f"/analisis/{cid}", status_code=302)

# ── ELIMINAR PUNTO ────────────────────────────────────────────────────────────

@router.post("/{cid}/punto/{pid}/eliminar")
def eliminar_punto(cid: int, pid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    p = db.query(models.PuntoCalibracion).filter(models.PuntoCalibracion.id == pid).first()
    if p:
        db.delete(p); db.flush()
        for i, pt in enumerate(db.query(models.PuntoCalibracion).filter(
            models.PuntoCalibracion.calibracion_id == cid
        ).order_by(models.PuntoCalibracion.numero_punto).all()):
            pt.numero_punto = i + 1
        db.commit()
    return RedirectResponse(url=f"/analisis/{cid}", status_code=302)

# ── SELECCIONAR REGRESIÓN ─────────────────────────────────────────────────────

@router.post("/{cid}/regresion")
def sel_regresion(cid: int, request: Request,
                   grado: int = Form(...), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if cal: cal.grado_regresion_sel = grado; db.commit()
    return RedirectResponse(url=f"/analisis/{cid}", status_code=302)

# ── APROBAR ───────────────────────────────────────────────────────────────────

@router.post("/{cid}/aprobar")
def aprobar(cid: int, request: Request,
            obs_aprobacion: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/analisis/{cid}")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if not cal: raise HTTPException(status_code=404)
    cal.resultado = "aprobado"
    cal.aprobado_por_id = u.id
    cal.fecha_aprobacion = datetime.now()
    eq = db.query(models.Equipo).filter(models.Equipo.id == cal.equipo_id).first()
    if eq:
        ant = eq.estado; eq.estado = "operativo"
        eq.apto_para_uso = True; eq.confirmacion_metrologica = True
        db.add(models.HistorialEstado(
            equipo_id=eq.id, usuario_id=u.id,
            estado_anterior=ant, estado_nuevo="operativo",
            motivo=f"Calibración aprobada — {cal.numero_certificado or cid}. {obs_aprobacion}"))
    db.commit()
    return RedirectResponse(url=f"/analisis/{cid}", status_code=302)

# ── PDF ───────────────────────────────────────────────────────────────────────

@router.get("/{cid}/pdf")
def pdf(cid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    cal = db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()
    if not cal: raise HTTPException(status_code=404)
    regs = calcular_regresiones(cal.puntos) if len(cal.puntos) >= 2 else []
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    usar_u = cal.usar_incertidumbre if hasattr(cal, 'usar_incertidumbre') else True
    from utils.pdf_analisis import generar_pdf_analisis
    pdf_bytes = generar_pdf_analisis(cal, cal.puntos, regs,
                                     cal.grado_regresion_sel, u, config, usar_u)
    nombre = f"analisis_{cal.numero_certificado or cid}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})
