import uuid
from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
from utils.validar_archivo import (guardar_archivo_validado, EXTENSIONES_DOCUMENTO,
                                    EXTENSIONES_IMAGEN, MAX_TAMANO_DOCUMENTO_BYTES)

EXTENSIONES_CERTIFICADO = EXTENSIONES_DOCUMENTO | EXTENSIONES_IMAGEN

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/magnitud/{mid}", response_class=HTMLResponse)
def historial(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "calibraciones/historial.html", {
        "usuario_actual": u, "magnitud": mag, "equipo": mag.equipo,
        "calibraciones": mag.calibraciones, "hoy": date.today()})

@router.get("/magnitud/{mid}/nueva", response_class=HTMLResponse)
def nueva_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url=f"/calibraciones/magnitud/{mid}")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "calibraciones/formulario.html",
        {"usuario_actual": u, "magnitud": mag, "equipo": mag.equipo})

@router.post("/magnitud/{mid}/nueva")
async def crear(mid: int, request: Request,
    numero_certificado: str = Form(""), laboratorio: str = Form(""),
    acreditacion_laboratorio: str = Form(""), fecha_calibracion: str = Form(...),
    patrones_utilizados: str = Form(""), metodo_calibracion: str = Form(""),
    temperatura_ambiente: str = Form(""), humedad_relativa: str = Form(""),
    trazabilidad: str = Form(""), observaciones: str = Form(""), costo: str = Form(""),
    certificado: UploadFile = File(None), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/calibraciones/magnitud/{mid}")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    cert_path = None
    if certificado and certificado.filename:
        n = f"static/certificados/cert_{uuid.uuid4()}"
        ruta = guardar_archivo_validado(certificado, n, EXTENSIONES_CERTIFICADO, MAX_TAMANO_DOCUMENTO_BYTES)
        cert_path = f"/{ruta}"
    cal = models.Calibracion(
        magnitud_id=mid, equipo_id=mag.equipo_id,
        numero_certificado=numero_certificado or None,
        laboratorio=laboratorio or None,
        acreditacion_laboratorio=acreditacion_laboratorio or None,
        fecha_calibracion=date.fromisoformat(fecha_calibracion),
        patrones_utilizados=patrones_utilizados or None,
        metodo_calibracion=metodo_calibracion or None,
        temperatura_ambiente=float(temperatura_ambiente) if temperatura_ambiente else None,
        humedad_relativa=float(humedad_relativa) if humedad_relativa else None,
        trazabilidad=trazabilidad or None, observaciones=observaciones or None,
        costo=float(costo) if costo else None,
        certificado_path=cert_path, resultado="pendiente")
    db.add(cal); db.commit(); db.refresh(cal)
    return RedirectResponse(url=f"/analisis/{cal.id}", status_code=302)
