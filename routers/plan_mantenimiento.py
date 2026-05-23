"""
Plan de mantenimiento preventivo por equipo.
"""
from datetime import date
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Form, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")


def _proxima_desde_plan(equipo, plan) -> date | None:
    """Calcula la próxima fecha de mantenimiento preventivo."""
    if not plan or not plan.frecuencia_meses:
        return None
    # Desde el último mantenimiento registrado
    mants = sorted([m for m in equipo.mantenimientos if m.fecha_fin],
                   key=lambda m: m.fecha_fin, reverse=True)
    if mants:
        return mants[0].fecha_fin + relativedelta(months=plan.frecuencia_meses)
    # Desde la última calibración si no hay mantenimientos
    for mag in equipo.magnitudes:
        if mag.activa and mag.calibraciones:
            ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
            return ul.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
    return None


def _sugerencia_frecuencia(equipo) -> int:
    """Sugiere la frecuencia de mantenimiento = mitad del período de calibración."""
    for mag in equipo.magnitudes:
        if mag.activa and mag.config_ilac:
            intervalo = mag.config_ilac.intervalo_actual_meses or 12
            return max(1, intervalo // 2)
    return 6  # default


@router.get("/equipo/{eid}", response_class=HTMLResponse)
def plan_page(eid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq:
        raise HTTPException(status_code=404)

    plan = db.query(models.PlanMantenimiento).filter(
        models.PlanMantenimiento.equipo_id == eid).first()

    proxima = _proxima_desde_plan(eq, plan)
    sugerencia = _sugerencia_frecuencia(eq)
    hoy = date.today()
    dias = (proxima - hoy).days if proxima else None

    return T.TemplateResponse(request, "mantenimientos/plan.html", {
        "usuario_actual": u,
        "equipo": eq,
        "plan": plan,
        "proxima": proxima,
        "dias": dias,
        "hoy": hoy,
        "sugerencia": sugerencia,
    })


@router.post("/equipo/{eid}")
def guardar_plan(eid: int, request: Request,
    frecuencia_meses: int = Form(...),
    tipo: str = Form("preventivo"),
    responsable: str = Form(""),
    descripcion: str = Form(""),
    activo: str = Form("true"),
    db: Session = Depends(get_db)):

    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol == "solo_lectura":
        return RedirectResponse(url=f"/plan-mantenimiento/equipo/{eid}")
    eq = db.query(models.Equipo).filter(models.Equipo.id == eid).first()
    if not eq:
        raise HTTPException(status_code=404)

    plan = db.query(models.PlanMantenimiento).filter(
        models.PlanMantenimiento.equipo_id == eid).first()

    vals = dict(
        equipo_id=eid,
        frecuencia_meses=frecuencia_meses,
        tipo=tipo,
        responsable=responsable or None,
        descripcion=descripcion or None,
        activo=(activo == "true"),
    )
    if plan:
        for k, v in vals.items():
            setattr(plan, k, v)
    else:
        plan = models.PlanMantenimiento(**vals)
        db.add(plan)
    db.commit()
    return RedirectResponse(url=f"/plan-mantenimiento/equipo/{eid}", status_code=302)
