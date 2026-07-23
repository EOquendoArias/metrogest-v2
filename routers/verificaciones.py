import io
from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
import utils.firma_electronica as firma
import services.verificaciones_service as svc

router = APIRouter()
T = Jinja2Templates(directory="templates")


@router.get("/plan/{mid}", response_class=HTMLResponse)
def plan_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = svc.obtener_magnitud(db, mid)
    if not mag: raise HTTPException(status_code=404)
    plan = svc.obtener_plan(db, mid)
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
        return RedirectResponse(url=f"/verificaciones/plan/{mid}", status_code=303)
    mag = svc.obtener_magnitud(db, mid)
    if not mag: raise HTTPException(status_code=404)
    svc.guardar_plan(db, mid, mag, activo, frecuencia_meses, procedimiento,
                      patron_referencia, umbral_alerta_pct, umbral_fuera_pct,
                      justificacion_no_aplica, aprobado_por_nombre,
                      aprobado_por_cargo, fecha_aprobacion)
    return RedirectResponse(url=f"/verificaciones/historial/{mid}", status_code=302)


@router.get("/plan/{mid}/pdf")
def pdf_plan_verificacion(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = svc.obtener_magnitud(db, mid)
    if not mag: raise HTTPException(status_code=404)
    plan = svc.obtener_plan(db, mid)
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
    mag = svc.obtener_magnitud(db, mid)
    if not mag: raise HTTPException(status_code=404)
    plan = svc.obtener_plan(db, mid)
    verifs, hoy, proxima, dias = svc.datos_historial(db, mag, plan)
    return T.TemplateResponse(request, "verificaciones/historial.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "plan": plan, "verificaciones": verifs, "proxima": proxima, "dias": dias, "hoy": hoy})


@router.get("/nueva/{mid}", response_class=HTMLResponse)
def nueva_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = svc.obtener_magnitud(db, mid)
    plan = svc.obtener_plan(db, mid)
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
        return RedirectResponse(url=f"/verificaciones/nueva/{mid}", status_code=303)
    mag = svc.obtener_magnitud(db, mid)
    plan = svc.obtener_plan(db, mid)
    if not mag or not plan: raise HTTPException(status_code=404)
    ver = svc.crear_verificacion(db, mid, mag, plan, fecha, tipo, realizada_por,
                                  patron_usado, observaciones, archivo)
    return RedirectResponse(url=f"/verificaciones/{ver.id}/puntos", status_code=302)


@router.get("/{vid}/puntos", response_class=HTMLResponse)
def puntos_page(vid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    ver = svc.obtener_verificacion(db, vid)
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
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=303)
    ver = svc.obtener_verificacion(db, vid)
    if not ver: raise HTTPException(status_code=404)
    svc.agregar_punto(db, ver, valor_patron, valor_indicado, tolerancia_inf,
                       tolerancia_sup, observacion)
    return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=302)


@router.post("/{vid}/puntos/lote")
def agregar_puntos_lote(vid: int, request: Request,
    valor_patron: list[str] = Form([]), valor_indicado: list[str] = Form([]),
    tolerancia_inf: list[str] = Form([]), tolerancia_sup: list[str] = Form([]),
    observacion: list[str] = Form([]), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=303)
    ver = svc.obtener_verificacion(db, vid)
    if not ver: raise HTTPException(status_code=404)
    svc.agregar_puntos_lote(db, ver, valor_patron, valor_indicado,
                             tolerancia_inf, tolerancia_sup, observacion)
    return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=303)


@router.post("/{vid}/cerrar")
def cerrar(vid: int, request: Request,
    accion_tomada: str = Form("ninguna"), observaciones: str = Form(""),
    password: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=303)
    ver = svc.obtener_verificacion(db, vid)
    if not ver:
        return RedirectResponse(url="/equipos/", status_code=303)
    ok, error = svc.cerrar_verificacion(db, request, u, ver, accion_tomada, observaciones, password)
    if not ok:
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos?error_firma=1", status_code=303)
    return RedirectResponse(url=f"/verificaciones/historial/{ver.magnitud_id}", status_code=302)


@router.post("/{vid}/punto/{pid}/eliminar")
def eliminar_punto(vid: int, pid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=303)
    svc.eliminar_punto(db, vid, pid, u.id)
    return RedirectResponse(url=f"/verificaciones/{vid}/puntos", status_code=302)


@router.get("/{vid}/pdf")
def pdf_verificacion(vid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    ver = svc.obtener_verificacion(db, vid)
    if not ver: raise HTTPException(status_code=404)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_verificacion
    pdf_bytes = generar_pdf_verificacion(ver, u, config)
    nombre = f"verificacion_{ver.magnitud.nombre if ver.magnitud else vid}_{ver.fecha.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})
