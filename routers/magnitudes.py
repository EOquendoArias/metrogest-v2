import os, shutil, uuid
from datetime import date
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/equipo/{eid}", response_class=HTMLResponse)
def lista(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    eq = db.query(models.Equipo).filter(models.Equipo.id==eid).first()
    if not eq: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "magnitudes/lista.html",
        {"usuario_actual": u, "equipo": eq, "magnitudes": eq.magnitudes, "hoy": date.today()})

@router.get("/equipo/{eid}/nueva", response_class=HTMLResponse)
def nueva_page(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url=f"/magnitudes/equipo/{eid}")
    eq = db.query(models.Equipo).filter(models.Equipo.id==eid).first()
    if not eq: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "magnitudes/formulario.html",
        {"usuario_actual": u, "equipo": eq, "magnitud": None})

@router.post("/equipo/{eid}/nueva")
def crear(eid: int, request: Request,
    nombre: str = Form(...), simbolo: str = Form(""), unidad: str = Form(""),
    rango_min: str = Form(""), rango_max: str = Form(""), resolucion: str = Form(""),
    emp_texto: str = Form(""), emp_valor: str = Form(""), emp_unidad: str = Form(""),
    clase_exactitud: str = Form(""), tipo_instrumento: str = Form("continuo"),
    umbral_alerta_pct: float = Form(70.0), umbral_fuera_pct: float = Form(100.0),
    notas: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url=f"/magnitudes/equipo/{eid}")
    orden = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.equipo_id==eid).count()+1
    db.add(models.MagnitudEquipo(
        equipo_id=eid, nombre=nombre, simbolo=simbolo or None, unidad=unidad or None,
        rango_min=float(rango_min) if rango_min else None,
        rango_max=float(rango_max) if rango_max else None,
        resolucion=resolucion or None, emp_texto=emp_texto or None,
        emp_valor=float(emp_valor) if emp_valor else None, emp_unidad=emp_unidad or None,
        clase_exactitud=clase_exactitud or None, tipo_instrumento=tipo_instrumento,
        umbral_alerta_pct=umbral_alerta_pct, umbral_fuera_pct=umbral_fuera_pct,
        notas=notas or None, orden=orden))
    db.commit()
    return RedirectResponse(url=f"/magnitudes/equipo/{eid}", status_code=302)

@router.get("/{mid}/editar", response_class=HTMLResponse)
def editar_page(mid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url="/equipos/")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "magnitudes/formulario.html",
        {"usuario_actual": u, "equipo": mag.equipo, "magnitud": mag})

@router.post("/{mid}/editar")
def editar(mid: int, request: Request,
    nombre: str = Form(...), simbolo: str = Form(""), unidad: str = Form(""),
    rango_min: str = Form(""), rango_max: str = Form(""), resolucion: str = Form(""),
    emp_texto: str = Form(""), emp_valor: str = Form(""), emp_unidad: str = Form(""),
    clase_exactitud: str = Form(""), tipo_instrumento: str = Form("continuo"),
    umbral_alerta_pct: float = Form(70.0), umbral_fuera_pct: float = Form(100.0),
    notas: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url="/equipos/")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    mag.nombre=nombre; mag.simbolo=simbolo or None; mag.unidad=unidad or None
    mag.rango_min=float(rango_min) if rango_min else None
    mag.rango_max=float(rango_max) if rango_max else None
    mag.resolucion=resolucion or None; mag.emp_texto=emp_texto or None
    mag.emp_valor=float(emp_valor) if emp_valor else None; mag.emp_unidad=emp_unidad or None
    mag.clase_exactitud=clase_exactitud or None; mag.tipo_instrumento=tipo_instrumento
    mag.umbral_alerta_pct=umbral_alerta_pct; mag.umbral_fuera_pct=umbral_fuera_pct
    mag.notas=notas or None
    db.commit()
    return RedirectResponse(url=f"/magnitudes/equipo/{mag.equipo_id}", status_code=302)

@router.post("/{mid}/desactivar")
def desactivar(mid: int, request: Request, motivo: str = Form(""), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url="/equipos/")
    mag = db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id==mid).first()
    if not mag: raise HTTPException(status_code=404)
    eid = mag.equipo_id; mag.activa = not mag.activa
    mag.motivo_desactivacion = (motivo or "Sin motivo") if not mag.activa else None
    db.commit()
    return RedirectResponse(url=f"/magnitudes/equipo/{eid}", status_code=302)
