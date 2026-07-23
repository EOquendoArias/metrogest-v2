from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth
from utils.validar_archivo import guardar_archivo_validado, EXTENSIONES_IMAGEN, MAX_TAMANO_IMAGEN_BYTES

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def config_page(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador": return RedirectResponse(url="/equipos/", status_code=303)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    return T.TemplateResponse(request, "config_lab/config.html",
        {"usuario_actual": u, "config": config, "ok": request.query_params.get("ok"), "hoy": date.today()})

@router.post("/guardar")
async def guardar(request: Request,
    nombre: str = Form(...), razon_social: str = Form(""),
    direccion: str = Form(""), ciudad: str = Form(""),
    codigo_formato_analisis: str = Form("FOR-MET-001"),
    codigo_formato_verificacion: str = Form("FOR-MET-002"),
    codigo_formato_mantenimiento: str = Form("FOR-MET-003"),
    codigo_formato_baja: str = Form("FOR-MET-004"),
    codigo_formato_auditoria: str = Form("FOR-MET-005"),
    version_analisis: str = Form("1.0"), version_verificacion: str = Form("1.0"),
    version_mantenimiento: str = Form("1.0"), version_baja: str = Form("1.0"),
    version_auditoria: str = Form("1.0"),
    elaborado_por: str = Form(""), revisado_por: str = Form(""), aprobado_por: str = Form(""),
    logo: UploadFile = File(None), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador": return RedirectResponse(url="/equipos/", status_code=303)
    c = db.query(models.ConfigLaboratorio).first()
    if not c: c = models.ConfigLaboratorio(); db.add(c)
    if logo and logo.filename:
        ruta = guardar_archivo_validado(logo, "static/uploads/logo_lab",
                                         EXTENSIONES_IMAGEN, MAX_TAMANO_IMAGEN_BYTES)
        c.logo_path = f"/{ruta}"
    c.nombre=nombre; c.razon_social=razon_social or None
    c.direccion=direccion or None; c.ciudad=ciudad or None
    c.codigo_formato_analisis=codigo_formato_analisis
    c.codigo_formato_verificacion=codigo_formato_verificacion
    c.codigo_formato_mantenimiento=codigo_formato_mantenimiento
    c.codigo_formato_baja=codigo_formato_baja; c.codigo_formato_auditoria=codigo_formato_auditoria
    c.version_analisis=version_analisis; c.version_verificacion=version_verificacion
    c.version_mantenimiento=version_mantenimiento; c.version_baja=version_baja
    c.version_auditoria=version_auditoria
    c.elaborado_por=elaborado_por or None; c.revisado_por=revisado_por or None
    c.aprobado_por=aprobado_por or None
    db.commit()
    return RedirectResponse(url="/config-lab/?ok=1", status_code=302)
