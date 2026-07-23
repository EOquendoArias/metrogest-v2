import io, uuid
from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
from utils.validar_archivo import (guardar_archivo_validado, EXTENSIONES_DOCUMENTO,
                                    EXTENSIONES_IMAGEN, MAX_TAMANO_DOCUMENTO_BYTES)

EXTENSIONES_ARCHIVO_MANT = EXTENSIONES_DOCUMENTO | EXTENSIONES_IMAGEN

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/equipo/{eid}", response_class=HTMLResponse)
def lista(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    mants = sorted(eq.mantenimientos,
                   key=lambda m: m.fecha_programada or date.min, reverse=True)
    return T.TemplateResponse(request, "mantenimientos/lista.html",
        {"usuario_actual": u, "equipo": eq, "mantenimientos": mants, "hoy": date.today()})

@router.get("/equipo/{eid}/nuevo", response_class=HTMLResponse)
def nuevo_page(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "mantenimientos/formulario.html",
        {"usuario_actual": u, "equipo": eq, "mant": None})

@router.post("/equipo/{eid}/nuevo")
async def crear(eid: int, request: Request,
    tipo: str = Form(...), origen: str = Form(...), titulo: str = Form(...),
    descripcion: str = Form(""), responsable_interno: str = Form(""),
    empresa_externa: str = Form(""), tecnico_externo: str = Form(""),
    orden_trabajo: str = Form(""), fecha_programada: str = Form(""),
    fecha_inicio: str = Form(""), fecha_fin: str = Form(""),
    estado: str = Form("programado"), falla_encontrada: str = Form(""),
    trabajo_realizado: str = Form(""), repuestos_utilizados: str = Form(""),
    costo: str = Form(""), requiere_calibracion: str = Form(""),
    afecta_medicion: str = Form(""), observaciones_metrologicas: str = Form(""),
    archivo: UploadFile = File(None), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/mantenimientos/equipo/{eid}", status_code=303)
    ap = None
    if archivo and archivo.filename:
        n = f"static/certificados/mant_{uuid.uuid4()}"
        ruta = guardar_archivo_validado(archivo, n, EXTENSIONES_ARCHIVO_MANT, MAX_TAMANO_DOCUMENTO_BYTES)
        ap = f"/{ruta}"
    mant = models.Mantenimiento(
        equipo_id=eid, tipo=tipo, origen=origen, titulo=titulo,
        descripcion=descripcion or None,
        responsable_interno=responsable_interno or None,
        empresa_externa=empresa_externa or None,
        tecnico_externo=tecnico_externo or None,
        orden_trabajo=orden_trabajo or None,
        fecha_programada=date.fromisoformat(fecha_programada) if fecha_programada else None,
        fecha_inicio=date.fromisoformat(fecha_inicio) if fecha_inicio else None,
        fecha_fin=date.fromisoformat(fecha_fin) if fecha_fin else None,
        estado=estado, falla_encontrada=falla_encontrada or None,
        trabajo_realizado=trabajo_realizado or None,
        repuestos_utilizados=repuestos_utilizados or None,
        costo=float(costo) if costo else None,
        requiere_calibracion=(requiere_calibracion == "true"),
        afecta_medicion=(afecta_medicion == "true"),
        observaciones_metrologicas=observaciones_metrologicas or None,
        archivo_path=ap)
    db.add(mant)
    if requiere_calibracion == "true":
        eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
        if eq and eq.estado == "operativo":
            ant = eq.estado; eq.estado = "en_mantenimiento"
            db.add(models.HistorialEstado(equipo_id=eid, usuario_id=u.id,
                estado_anterior=ant, estado_nuevo="en_mantenimiento",
                motivo=f"Mantenimiento: {titulo}"))
    db.commit()
    db.refresh(mant)
    return RedirectResponse(url=f"/mantenimientos/equipo/{eid}", status_code=302)

@router.get("/equipo/{eid}/mant/{mid}/pdf")
def pdf_mantenimiento(eid: int, mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mant = db.query(models.Mantenimiento).filter(models.Mantenimiento.id == mid).first()
    if not mant: raise HTTPException(status_code=404)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_mantenimiento
    pdf_bytes = generar_pdf_mantenimiento(mant, u, config)
    nombre = f"mantenimiento_{mant.titulo[:30].replace(' ','_')}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})

@router.get("/{mid}/pdf")
def pdf_mant_simple(mid: int, request: Request, db: Session = Depends(get_db)):
    """Ruta simplificada que usa el template: /mantenimientos/{id}/pdf"""
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mant = db.query(models.Mantenimiento).filter(models.Mantenimiento.id == mid).first()
    if not mant: raise HTTPException(status_code=404)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_mantenimiento
    pdf_bytes = generar_pdf_mantenimiento(mant, u, config)
    nombre = f"mantenimiento_{mant.titulo[:30].replace(' ','_')}_{date.today().strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})

@router.get("/{mid}/editar", response_class=HTMLResponse)
def editar_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mant = db.query(models.Mantenimiento).filter(models.Mantenimiento.id == mid).first()
    if not mant: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "mantenimientos/formulario.html",
        {"usuario_actual": u, "equipo": mant.equipo, "mant": mant})
