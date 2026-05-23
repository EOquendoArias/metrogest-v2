"""
Calendario — Vista mensual + lista lateral de actividades programadas
"""
from datetime import date, timedelta
import calendar as cal_lib
from dateutil.relativedelta import relativedelta
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")

MESES = ["","Enero","Febrero","Marzo","Abril","Mayo","Junio",
         "Julio","Agosto","Septiembre","Octubre","Noviembre","Diciembre"]


def _proxima_verif(mag):
    """Calcula la próxima verificación de una magnitud."""
    plan = mag.plan_verificacion
    if not plan or not plan.activo or not plan.frecuencia_meses:
        return None
    verifs = plan.verificaciones
    if verifs:
        return verifs[0].fecha + relativedelta(months=plan.frecuencia_meses)
    elif mag.calibraciones:
        primera = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
        return primera.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
    return None


def _get_actividades(db: Session, año: int, mes: int) -> list:
    """Obtiene actividades del mes. Incluye vencidas del mes anterior."""
    inicio = date(año, mes, 1)
    fin    = inicio + relativedelta(months=1) - timedelta(days=1)
    hoy    = date.today()
    actividades = []

    equipos = db.query(models.Equipo).filter(
        models.Equipo.estado != "dado_de_baja"
    ).all()

    for eq in equipos:
        for mag in eq.magnitudes:
            if not mag.activa:
                continue

            # Calibración próxima
            for cal in mag.calibraciones:
                if cal.proxima_calibracion and inicio <= cal.proxima_calibracion <= fin:
                    dias = (cal.proxima_calibracion - hoy).days
                    actividades.append({
                        "fecha":      cal.proxima_calibracion,
                        "tipo":       "calibracion",
                        "titulo":     eq.nombre,
                        "codigo":     eq.codigo,
                        "detalle":    f"{mag.nombre} — Cert. {cal.numero_certificado or '—'}",
                        "magnitud":   mag.nombre,
                        "equipo_id":  eq.id,
                        "color":      "#1a4f8a",
                        "icono":      "fa-certificate",
                        "vencida":    dias < 0,
                    })

            # Verificación próxima
            prox_v = _proxima_verif(mag)
            if prox_v and inicio <= prox_v <= fin:
                dias = (prox_v - hoy).days
                actividades.append({
                    "fecha":      prox_v,
                    "tipo":       "verificacion",
                    "titulo":     eq.nombre,
                    "codigo":     eq.codigo,
                    "detalle":    f"Verificación — {mag.nombre}",
                    "magnitud":   mag.nombre,
                    "equipo_id":  eq.id,
                    "color":      "#16a34a",
                    "icono":      "fa-check-double",
                    "vencida":    dias < 0,
                })

        # Mantenimientos programados (registrados)
        for mant in eq.mantenimientos:
            if (mant.fecha_programada and inicio <= mant.fecha_programada <= fin
                    and mant.estado == "programado"):
                dias = (mant.fecha_programada - hoy).days
                actividades.append({
                    "fecha":      mant.fecha_programada,
                    "tipo":       "mantenimiento",
                    "titulo":     eq.nombre,
                    "codigo":     eq.codigo,
                    "detalle":    mant.titulo,
                    "magnitud":   "",
                    "equipo_id":  eq.id,
                    "color":      "#d97706",
                    "icono":      "fa-wrench",
                    "vencida":    dias < 0,
                })

        # Próximo mantenimiento desde plan preventivo
        if hasattr(eq, 'plan_mantenimiento') and eq.plan_mantenimiento and eq.plan_mantenimiento.activo:
            plan_m = eq.plan_mantenimiento
            mants_ok = sorted([m for m in eq.mantenimientos if m.fecha_fin],
                               key=lambda m: m.fecha_fin, reverse=True)
            if mants_ok:
                prox_m = mants_ok[0].fecha_fin + relativedelta(months=plan_m.frecuencia_meses)
            else:
                prox_m = None
                for mag in eq.magnitudes:
                    if mag.activa and mag.calibraciones:
                        ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
                        prox_m = ul.fecha_calibracion + relativedelta(months=plan_m.frecuencia_meses)
                        break
            if prox_m and inicio <= prox_m <= fin:
                dias = (prox_m - hoy).days
                actividades.append({
                    "fecha":      prox_m,
                    "tipo":       "mantenimiento",
                    "titulo":     eq.nombre,
                    "codigo":     eq.codigo,
                    "detalle":    f"Mantenimiento preventivo — {plan_m.tipo.title()}",
                    "magnitud":   "",
                    "equipo_id":  eq.id,
                    "color":      "#d97706",
                    "icono":      "fa-wrench",
                    "vencida":    dias < 0,
                })

    # Normalize all fechas to date objects (SQLAlchemy might return datetime)
    for act in actividades:
        if hasattr(act["fecha"], 'date'):
            act["fecha"] = act["fecha"].date()
    actividades.sort(key=lambda a: a["fecha"])
    return actividades


def _get_proximas_y_vencidas(db: Session, hoy: date, n: int = 15) -> list:
    """
    Lista lateral: vencidas (últimos 30 días) + próximas (60 días).
    Ordenadas: primero vencidas más recientes, luego próximas.
    """
    desde = hoy - timedelta(days=30)
    hasta = hoy + timedelta(days=60)

    equipos = db.query(models.Equipo).filter(
        models.Equipo.estado != "dado_de_baja"
    ).all()

    items = []
    for eq in equipos:
        for mag in eq.magnitudes:
            if not mag.activa:
                continue
            # Calibración
            for cal in mag.calibraciones:
                if cal.proxima_calibracion and desde <= cal.proxima_calibracion <= hasta:
                    dias = (cal.proxima_calibracion - hoy).days
                    items.append({
                        "fecha":     cal.proxima_calibracion,
                        "tipo":      "calibracion",
                        "titulo":    eq.nombre,
                        "codigo":    eq.codigo,
                        "detalle":   mag.nombre,
                        "equipo_id": eq.id,
                        "color":     "#1a4f8a",
                        "icono":     "fa-certificate",
                        "dias":      dias,
                        "vencida":   dias < 0,
                    })
            # Verificación
            prox_v = _proxima_verif(mag)
            if prox_v and desde <= prox_v <= hasta:
                dias = (prox_v - hoy).days
                items.append({
                    "fecha":     prox_v,
                    "tipo":      "verificacion",
                    "titulo":    eq.nombre,
                    "codigo":    eq.codigo,
                    "detalle":   mag.nombre,
                    "equipo_id": eq.id,
                    "color":     "#16a34a",
                    "icono":     "fa-check-double",
                    "dias":      dias,
                    "vencida":   dias < 0,
                })

        # Mantenimientos registrados
        for mant in eq.mantenimientos:
            if (mant.fecha_programada and desde <= mant.fecha_programada <= hasta
                    and mant.estado == "programado"):
                dias = (mant.fecha_programada - hoy).days
                items.append({
                    "fecha":     mant.fecha_programada,
                    "tipo":      "mantenimiento",
                    "titulo":    eq.nombre,
                    "codigo":    eq.codigo,
                    "detalle":   mant.titulo,
                    "equipo_id": eq.id,
                    "color":     "#d97706",
                    "icono":     "fa-wrench",
                    "dias":      dias,
                    "vencida":   dias < 0,
                })

        # Plan mantenimiento preventivo
        if hasattr(eq, 'plan_mantenimiento') and eq.plan_mantenimiento and eq.plan_mantenimiento.activo:
            plan_m = eq.plan_mantenimiento
            mants_ok = sorted([m for m in eq.mantenimientos if m.fecha_fin],
                               key=lambda m: m.fecha_fin, reverse=True)
            if mants_ok:
                prox_m = mants_ok[0].fecha_fin + relativedelta(months=plan_m.frecuencia_meses)
            else:
                prox_m = None
                for mag in eq.magnitudes:
                    if mag.activa and mag.calibraciones:
                        ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
                        prox_m = ul.fecha_calibracion + relativedelta(months=plan_m.frecuencia_meses)
                        break
            if prox_m and desde <= prox_m <= hasta:
                dias = (prox_m - hoy).days
                items.append({
                    "fecha":     prox_m,
                    "tipo":      "mantenimiento",
                    "titulo":    eq.nombre,
                    "codigo":    eq.codigo,
                    "detalle":   f"Preventivo — {plan_m.tipo.title()}",
                    "equipo_id": eq.id,
                    "color":     "#d97706",
                    "icono":     "fa-wrench",
                    "dias":      dias,
                    "vencida":   dias < 0,
                })

    # Normalize all fechas to date objects
    for item in items:
        if hasattr(item["fecha"], 'date'):
            item["fecha"] = item["fecha"].date()
    # Recalculate dias after normalization
    for item in items:
        item["dias"] = (item["fecha"] - hoy).days
        item["vencida"] = item["dias"] < 0

    # Ordenar: vencidas primero (más recientes al tope), luego próximas
    vencidas  = sorted([i for i in items if i["vencida"]],  key=lambda x: x["dias"], reverse=True)
    proximas  = sorted([i for i in items if not i["vencida"]], key=lambda x: x["dias"])
    return (vencidas + proximas)[:n]


def _build_calendario(año: int, mes: int, actividades: list) -> list:
    cal = cal_lib.monthcalendar(año, mes)
    semanas = []
    for semana in cal:
        dias = []
        for dia in semana:
            if dia == 0:
                dias.append({"dia": None, "actividades": []})
            else:
                d = date(año, mes, dia)
                acts = [a for a in actividades if a["fecha"] == d]
                dias.append({"dia": dia, "fecha": d, "actividades": acts})
        semanas.append(dias)
    return semanas


@router.get("/", response_class=HTMLResponse)
def calendario(request: Request, db: Session = Depends(get_db),
               año: int = None, mes: int = None):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")

    hoy  = date.today()
    año  = año  or hoy.year
    mes  = mes  or hoy.month

    mes_actual   = date(año, mes, 1)
    mes_anterior = mes_actual - relativedelta(months=1)
    mes_siguiente= mes_actual + relativedelta(months=1)

    actividades = _get_actividades(db, año, mes)
    semanas     = _build_calendario(año, mes, actividades)
    proximas    = _get_proximas_y_vencidas(db, hoy)

    vencidas_count = sum(1 for a in proximas if a["vencida"])

    return T.TemplateResponse(request, "calendario/calendario.html", {
        "usuario_actual":  u,
        "hoy":             hoy,
        "año": año, "mes": mes,
        "nombre_mes":      MESES[mes],
        "semanas":         semanas,
        "actividades":     actividades,
        "proximas":        proximas,
        "vencidas_count":  vencidas_count,
        "mes_anterior":    mes_anterior,
        "mes_siguiente":   mes_siguiente,
        "total_mes":       len(actividades),
    })
