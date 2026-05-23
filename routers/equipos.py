import os, shutil, uuid
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Form, File, UploadFile, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")

ESTADOS = ["en_espera_calibracion","operativo","en_calibracion",
           "en_mantenimiento","fuera_de_uso","dado_de_baja"]

def _prox(eq):
    fechas = []
    for mag in eq.magnitudes:
        if not mag.activa or not mag.calibraciones: continue
        u = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
        if u.proxima_calibracion: fechas.append((u.proxima_calibracion, mag.nombre))
    if fechas: fechas.sort(); return fechas[0]
    return None, None

def _historial_unificado(eq):
    eventos = []

    # Calibraciones
    for mag in eq.magnitudes:
        for cal in mag.calibraciones:
            eventos.append({
                "fecha": cal.fecha_calibracion, "tipo": "calibracion",
                "descripcion": f"{mag.nombre} — Cert. {cal.numero_certificado or '(sin número)'}",
                "resultado": cal.resultado,
                "realizado_por": cal.laboratorio or None,
                "link": f"/analisis/{cal.id}",
            })
        # Verificaciones
        if mag.plan_verificacion:
            for ver in mag.plan_verificacion.verificaciones:
                eventos.append({
                    "fecha": ver.fecha, "tipo": "verificacion",
                    "descripcion": f"{mag.nombre} — {ver.tipo.replace('_',' ').title()}",
                    "resultado": ver.resultado,
                    "realizado_por": ver.realizada_por or None,
                    "link": f"/verificaciones/{ver.id}/puntos",
                })

    # Mantenimientos
    for mant in eq.mantenimientos:
        f = mant.fecha_fin or mant.fecha_inicio or mant.fecha_programada
        if f:
            eventos.append({
                "fecha": f, "tipo": "mantenimiento",
                "descripcion": mant.titulo,
                "resultado": mant.estado,
                "realizado_por": mant.responsable_interno or mant.empresa_externa or None,
                "link": None,
            })

    # Cambios de estado — del historial_estados
    for h in eq.historial_estados:
        fecha_h = h.fecha.date() if hasattr(h.fecha, 'date') else h.fecha
        ant = h.estado_anterior.replace('_',' ').title() if h.estado_anterior else None
        nvo = h.estado_nuevo.replace('_',' ').title()
        desc = f"{ant} → {nvo}" if ant else nvo
        if h.motivo:
            desc += f" — {h.motivo}"
        eventos.append({
            "fecha": fecha_h, "tipo": "estado",
            "descripcion": desc,
            "resultado": h.estado_nuevo,
            "realizado_por": h.usuario.nombre if h.usuario else None,
            "link": None,
        })

    eventos.sort(key=lambda e: e["fecha"], reverse=True)

    class Ev:
        def __init__(self, d):
            for k, v in d.items(): setattr(self, k, v)
    return [Ev(e) for e in eventos]

@router.get("/", response_class=HTMLResponse)
def lista(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    equipos = db.query(models.Equipo).order_by(models.Equipo.nombre).all()
    return T.TemplateResponse(request, "equipos/lista.html",
        {"usuario_actual": u, "equipos": equipos, "hoy": date.today()})

@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_page(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url="/equipos/")
    return T.TemplateResponse(request, "equipos/formulario.html",
        {"usuario_actual": u, "equipo": None, "error": None})

@router.post("/nuevo")
async def crear(request: Request, codigo: str = Form(...), nombre: str = Form(...),
    descripcion: str = Form(""), marca: str = Form(""), modelo: str = Form(""),
    numero_serie: str = Form(""), numero_inventario: str = Form(""),
    fecha_adquisicion: str = Form(""), costo: str = Form(""),
    area: str = Form(""), ubicacion: str = Form(""), responsable: str = Form(""),
    foto: UploadFile = File(None), manual: UploadFile = File(None),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login", status_code=303)
    if u.rol == "solo_lectura": return RedirectResponse(url="/equipos/", status_code=303)
    if db.query(models.Equipo).filter(models.Equipo.codigo == codigo).first():
        return T.TemplateResponse(request, "equipos/formulario.html",
            {"usuario_actual": u, "equipo": None, "error": f"Código '{codigo}' ya existe"})
    def _save(f, prefix):
        if not f or not f.filename: return None
        ext = os.path.splitext(f.filename)[1]
        n = f"static/uploads/{prefix}_{uuid.uuid4()}{ext}"
        with open(n, "wb") as fp: shutil.copyfileobj(f.file, fp)
        return f"/{n}"
    eq = models.Equipo(
        codigo=codigo, nombre=nombre, descripcion=descripcion or None,
        marca=marca or None, modelo=modelo or None,
        numero_serie=numero_serie or None, numero_inventario=numero_inventario or None,
        fecha_adquisicion=date.fromisoformat(fecha_adquisicion) if fecha_adquisicion else None,
        costo=float(costo) if costo else None,
        area=area or None, ubicacion=ubicacion or None, responsable=responsable or None,
        foto_path=_save(foto, "foto"), manual_path=_save(manual, "manual"),
        estado="en_espera_calibracion")
    db.add(eq); db.flush()
    db.add(models.HistorialEstado(equipo_id=eq.id, usuario_id=u.id,
        estado_nuevo="en_espera_calibracion", motivo="Registro inicial del equipo"))
    db.commit()
    return RedirectResponse(url=f"/equipos/{eq.id}", status_code=303)

@router.get("/{eid}", response_class=HTMLResponse)
def detalle(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    hoy = date.today()
    pf, pm = _prox(eq)
    dias = (pf - hoy).days if pf else None
    uc = None
    for mag in eq.magnitudes:
        if mag.activa and mag.calibraciones:
            lc = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
            if uc is None or lc.fecha_calibracion > uc: uc = lc.fecha_calibracion

    # Próxima verificación (la más próxima entre todas las magnitudes activas)
    prox_verif = None
    for mag in eq.magnitudes:
        if not mag.activa: continue
        plan = mag.plan_verificacion
        if not plan or not plan.activo or not plan.frecuencia_meses: continue
        verifs = plan.verificaciones
        if verifs:
            pv = verifs[0].fecha + relativedelta(months=plan.frecuencia_meses)
        elif mag.calibraciones:
            primera = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
            pv = primera.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
        else:
            continue
        if prox_verif is None or pv < prox_verif:
            prox_verif = pv
    prox_verif_dias = (prox_verif - hoy).days if prox_verif else None

    # Próximo mantenimiento programado
    prox_mant = None
    for mant in eq.mantenimientos:
        if mant.fecha_programada and mant.estado == "programado":
            fd = mant.fecha_programada
            if hasattr(fd, 'date'): fd = fd.date()
            if prox_mant is None or fd < prox_mant:
                prox_mant = fd
    prox_mant_dias = (prox_mant - hoy).days if prox_mant else None

    return T.TemplateResponse(request, "equipos/detalle.html", {
        "usuario_actual": u, "equipo": eq, "hoy": hoy,
        "prox_fecha": pf, "prox_mag": pm, "dias": dias,
        "ultima_cal": uc, "estados": ESTADOS,
        "historial_eventos": _historial_unificado(eq),
        "prox_verif": prox_verif, "prox_verif_dias": prox_verif_dias,
        "prox_mant": prox_mant, "prox_mant_dias": prox_mant_dias,
    })

@router.get("/{eid}/editar", response_class=HTMLResponse)
def editar_page(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura": return RedirectResponse(url=f"/equipos/{eid}")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    return T.TemplateResponse(request, "equipos/formulario.html",
        {"usuario_actual": u, "equipo": eq, "error": None})

@router.post("/{eid}/editar")
async def editar(eid: int, request: Request,
    codigo: str = Form(...), nombre: str = Form(...),
    descripcion: str = Form(""), marca: str = Form(""), modelo: str = Form(""),
    numero_serie: str = Form(""), numero_inventario: str = Form(""),
    fecha_adquisicion: str = Form(""), costo: str = Form(""),
    area: str = Form(""), ubicacion: str = Form(""), responsable: str = Form(""),
    foto: UploadFile = File(None), manual: UploadFile = File(None),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login", status_code=303)
    if u.rol == "solo_lectura": return RedirectResponse(url=f"/equipos/{eid}", status_code=303)
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    def _save(f, prefix):
        if not f or not f.filename: return None
        ext = os.path.splitext(f.filename)[1]
        n = f"static/uploads/{prefix}_{uuid.uuid4()}{ext}"
        with open(n, "wb") as fp: shutil.copyfileobj(f.file, fp)
        return f"/{n}"
    fp = _save(foto, "foto"); mp = _save(manual, "manual")
    if fp: eq.foto_path = fp
    if mp: eq.manual_path = mp
    eq.codigo=codigo; eq.nombre=nombre; eq.descripcion=descripcion or None
    eq.marca=marca or None; eq.modelo=modelo or None
    eq.numero_serie=numero_serie or None; eq.numero_inventario=numero_inventario or None
    eq.fecha_adquisicion=date.fromisoformat(fecha_adquisicion) if fecha_adquisicion else None
    eq.costo=float(costo) if costo else None
    eq.area=area or None; eq.ubicacion=ubicacion or None; eq.responsable=responsable or None
    db.commit()
    return RedirectResponse(url=f"/equipos/{eid}", status_code=303)

@router.post("/{eid}/estado")
def cambiar_estado(eid: int, request: Request,
    nuevo_estado: str = Form(...), motivo: str = Form(""),
    db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u: return RedirectResponse(url="/usuarios/login", status_code=303)
    if u.rol == "solo_lectura": return RedirectResponse(url=f"/equipos/{eid}", status_code=303)
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq: raise HTTPException(status_code=404)
    ant = eq.estado; eq.estado = nuevo_estado
    if nuevo_estado == "operativo":
        eq.apto_para_uso = True; eq.confirmacion_metrologica = True
    db.add(models.HistorialEstado(equipo_id=eid, usuario_id=u.id,
        estado_anterior=ant, estado_nuevo=nuevo_estado, motivo=motivo or None))
    db.commit()
    return RedirectResponse(url=f"/equipos/{eid}", status_code=303)
