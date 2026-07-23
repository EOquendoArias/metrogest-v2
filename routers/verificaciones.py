import io, uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
import utils.firma_electronica as firma
from utils.validar_archivo import (guardar_archivo_validado, EXTENSIONES_DOCUMENTO,
                                    EXTENSIONES_IMAGEN, MAX_TAMANO_DOCUMENTO_BYTES)

EXTENSIONES_ARCHIVO_VERIF = EXTENSIONES_DOCUMENTO | EXTENSIONES_IMAGEN

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/plan/{mid}", response_class=HTMLResponse)
def plan_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    return T.TemplateResponse(request, "verificaciones/plan.html",
        {"usuario_actual": u, "magnitud": mag, "equipo": mag.equipo, "plan": plan})

@router.post("/plan/{mid}")
def guardar_plan(mid: int, request: Request,
    activo: str = Form("true"),
    frecuencia_meses: str = Form(""),
    procedimiento: str = Form(""),
    patron_referencia: str = Form(""),
    umbral_alerta_pct: float = Form(70.0),
    umbral_fuera_pct: float = Form(100.0),
    justificacion_no_aplica: str = Form(""),
    aprobado_por_nombre: str = Form(""),
    aprobado_por_cargo: str = Form(""),
    fecha_aprobacion: str = Form(""),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/plan/{mid}")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    hace = (activo == "true")
    # frecuencia_meses tiene NOT NULL en la BD; cuando no aplica conservamos el valor
    # anterior o usamos 12 como placeholder (se ignora en la lógica cuando activo=False)
    if hace:
        frec = int(frecuencia_meses) if frecuencia_meses else 12
    else:
        frec = (plan.frecuencia_meses if plan and plan.frecuencia_meses else 12)
    fapb = date.fromisoformat(fecha_aprobacion) if fecha_aprobacion else None
    v = dict(
        magnitud_id=mid, equipo_id=mag.equipo_id,
        activo=hace,
        frecuencia_meses=frec,
        procedimiento=procedimiento or None,
        patron_referencia=patron_referencia or None,
        umbral_alerta_pct=umbral_alerta_pct,
        umbral_fuera_pct=umbral_fuera_pct,
        justificacion_no_aplica=justificacion_no_aplica or None,
        aprobado_por_nombre=aprobado_por_nombre or None,
        aprobado_por_cargo=aprobado_por_cargo or None,
        fecha_aprobacion=fapb,
    )
    if plan:
        for k, val in v.items(): setattr(plan, k, val)
    else:
        plan = models.PlanVerificacion(**v); db.add(plan)
    db.commit()
    return RedirectResponse(url=f"/verificaciones/historial/{mid}", status_code=302)


@router.get("/plan/{mid}/pdf")
def pdf_plan_verificacion(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    if not plan: raise HTTPException(status_code=404, detail="Sin plan de verificaciones")
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_plan_verificacion
    pdf_bytes = generar_pdf_plan_verificacion(mag, plan, u, config)
    nombre = f"plan_verificacion_{mag.nombre}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})

@router.get("/historial/{mid}", response_class=HTMLResponse)
def historial(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    verifs = plan.verificaciones if plan else []
    hoy = date.today(); proxima = None; dias = None
    if plan and verifs:
        # Recalculate from last verification date + current plan frequency
        ultima_ver = verifs[0]
        proxima = ultima_ver.fecha + relativedelta(months=plan.frecuencia_meses)
        # Update stored value if it differs significantly
    elif plan and mag.calibraciones:
        primera_cal = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
        proxima = primera_cal.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
    if proxima: dias = (proxima - hoy).days
    return T.TemplateResponse(request, "verificaciones/historial.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "plan": plan, "verificaciones": verifs, "proxima": proxima, "dias": dias, "hoy": hoy})

@router.get("/nueva/{mid}", response_class=HTMLResponse)
def nueva_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    if not mag or not plan: return RedirectResponse(url=f"/verificaciones/plan/{mid}")
    return T.TemplateResponse(request, "verificaciones/nueva.html",
        {"usuario_actual": u, "magnitud": mag, "equipo": mag.equipo, "plan": plan, "hoy": date.today()})

@router.post("/nueva/{mid}")
async def crear(mid: int, request: Request,
    fecha: str = Form(...), tipo: str = Form("programada"),
    realizada_por: str = Form(""), patron_usado: str = Form(""),
    observaciones: str = Form(""), archivo: UploadFile = File(None),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/nueva/{mid}")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    plan = db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id==mid).first()
    if not mag or not plan: raise HTTPException(status_code=404)
    ap = None
    if archivo and archivo.filename:
        n = f"static/certificados/verif_{uuid.uuid4()}"
        ruta = guardar_archivo_validado(archivo, n, EXTENSIONES_ARCHIVO_VERIF, MAX_TAMANO_DOCUMENTO_BYTES)
        ap = f"/{ruta}"
    fv = date.fromisoformat(fecha)
    ver = models.VerificacionIntermedia(
        plan_id=plan.id, equipo_id=mag.equipo_id, magnitud_id=mid,
        fecha=fv, proxima_verificacion=fv+relativedelta(months=plan.frecuencia_meses),
        tipo=tipo, realizada_por=realizada_por or None,
        patron_usado=patron_usado or plan.patron_referencia or None,
        observaciones=observaciones or None, archivo_path=ap, resultado="pendiente")
    db.add(ver); db.commit(); db.refresh(ver)
    return RedirectResponse(url=f"/verificaciones/{ver.id}/puntos", status_code=302)

@router.get("/{vid}/puntos", response_class=HTMLResponse)
def puntos_page(vid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    ver = db.query(models.VerificacionIntermedia).filter(models.VerificacionIntermedia.id==vid).first()
    if not ver: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "verificaciones/puntos.html", {
        "usuario_actual": u, "verificacion": ver, "magnitud": ver.magnitud,
        "equipo": ver.equipo, "plan": ver.plan, "puntos": ver.puntos,
        "emp": ver.magnitud.emp_valor if ver.magnitud else None,
        "error_firma": request.query_params.get("error_firma"),
        "significado_cerrar": firma.SIGNIFICADOS["cerrar_verificacion"]})

@router.post("/{vid}/punto")
def agregar_punto(vid: int, request: Request,
    valor_patron: float = Form(...), valor_indicado: float = Form(...),
    tolerancia_inf: str = Form(""), tolerancia_sup: str = Form(""),
    observacion: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos")
    ver = db.query(models.VerificacionIntermedia).filter(models.VerificacionIntermedia.id==vid).first()
    if not ver: raise HTTPException(status_code=404)
    err = round(valor_indicado - valor_patron, 8)
    emp = ver.magnitud.emp_valor if ver.magnitud else None
    ti = float(tolerancia_inf) if tolerancia_inf else (-abs(emp) if emp else None)
    ts = float(tolerancia_sup) if tolerancia_sup else (abs(emp) if emp else None)
    desv = round(abs(err)/abs(emp)*100,2) if emp else None
    ua = ver.plan.umbral_alerta_pct if ver.plan else 70
    uf = ver.plan.umbral_fuera_pct if ver.plan else 100
    res = ("fuera" if desv and desv>=uf else "alerta" if desv and desv>=ua else "ok") if desv is not None else None
    n = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.verificacion_id==vid,
        models.PuntoVerificacion.eliminado==False).count()
    db.add(models.PuntoVerificacion(verificacion_id=vid, numero_punto=n+1,
        valor_patron=valor_patron, valor_indicado=valor_indicado, error=err,
        tolerancia_inf=ti, tolerancia_sup=ts, desviacion_pct=desv,
        resultado=res, observacion=observacion or None))
    db.flush()
    pts = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.verificacion_id==vid,
        models.PuntoVerificacion.eliminado==False).all()
    rs = [p.resultado for p in pts if p.resultado]
    ds = [p.desviacion_pct for p in pts if p.desviacion_pct is not None]
    ver.max_desviacion_pct = max(ds) if ds else None
    ver.resultado = "reprobado" if "fuera" in rs else "alerta" if "alerta" in rs else "aprobado" if rs else "pendiente"
    db.commit()
    return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=302)

@router.post("/{vid}/cerrar")
def cerrar(vid: int, request: Request,
    accion_tomada: str = Form("ninguna"), observaciones: str = Form(""),
    password: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos")
    ver = db.query(models.VerificacionIntermedia).filter(models.VerificacionIntermedia.id==vid).first()
    if ver:
        ok, error = firma.verificar_y_firmar(db, request, u, password,
            "verificaciones_intermedias", vid, "cerrar_verificacion")
        if not ok:
            return RedirectResponse(url=f"/verificaciones/{vid}/puntos?error_firma=1", status_code=303)
        ver.accion_tomada=accion_tomada
        if observaciones: ver.observaciones=observaciones
        db.commit()
        return RedirectResponse(url=f"/verificaciones/historial/{ver.magnitud_id}", status_code=302)
    return RedirectResponse(url="/equipos/")

@router.post("/{vid}/punto/{pid}/eliminar")
def eliminar_punto(vid: int, pid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos")
    p = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.id==pid,
        models.PuntoVerificacion.eliminado==False).first()
    if p:
        p.eliminado = True
        p.eliminado_en = datetime.now()
        p.eliminado_por_id = u.id
        db.flush()
        pts = db.query(models.PuntoVerificacion).filter(
            models.PuntoVerificacion.verificacion_id==vid,
            models.PuntoVerificacion.eliminado==False
        ).order_by(models.PuntoVerificacion.numero_punto).all()
        for i, pt in enumerate(pts):
            pt.numero_punto = i + 1
        db.commit()
    return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=302)


@router.get("/{vid}/pdf")
def pdf_verificacion(vid: int, request: Request, db: Session = Depends(get_db)):
    import io
    from fastapi.responses import StreamingResponse
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    ver = db.query(models.VerificacionIntermedia).filter(
        models.VerificacionIntermedia.id == vid).first()
    if not ver:
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_verificacion
    pdf_bytes = generar_pdf_verificacion(ver, u, config)
    from datetime import date
    nombre = f"verificacion_{ver.magnitud.nombre if ver.magnitud else vid}_{ver.fecha.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})
