"""
Dashboard — Panel de control principal de MetroGest
"""
import asyncio
import io
from datetime import date, datetime, timedelta, timezone
from functools import partial
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload
from database import get_db
import models, auth
from utils.orm_snapshot import snapshot
from utils.pdf_executor import pool as _pdf_pool

router = APIRouter()
T = Jinja2Templates(directory="templates")


def _filas_y_totales(db: Session, hoy: date):
    """
    Detalle por equipo ('filas') y los totales que faltan para los exportadores
    del dashboard (costo_anio, proximos_60). Reutiliza la misma lógica ya
    probada del listado general (routers/auditoria.py) en vez de duplicarla.
    """
    from routers.auditoria import _datos as _datos_listado

    filas = sorted(_datos_listado(db, hoy), key=lambda d: (d["dias_cal"] or 9999))
    proximos_60 = sum(1 for d in filas if d["dias_cal"] is not None and 0 <= d["dias_cal"] <= 60)
    costo_anio = db.query(func.coalesce(func.sum(models.Calibracion.costo), 0)).filter(
        func.extract("year", models.Calibracion.fecha_calibracion) == hoy.year
    ).scalar()
    return filas, proximos_60, costo_anio

# Caché en proceso — el dashboard no necesita exactitud al segundo, y recorre
# todos los equipos con sus magnitudes/calibraciones/verificaciones/mantenimientos.
# Evita recalcular en cada reload/export dentro de la misma ventana de tiempo.
CACHE_TTL_SEGUNDOS = 60
_cache = {"datos": None, "hoy": None, "expira": None}
# Caché aparte para las filas de detalle que solo usan los exportadores
# (PDF/Excel) — antes se recalculaban SIN caché en cada export, recorriendo
# los 1,600 equipos otra vez encima del cálculo ya cacheado de KPIs. Ver
# ADR-001 en docs/arquitectura/DECISIONES.md.
_cache_filas = {"filas": None, "hoy": None, "expira": None}


def _calcular_datos_cacheado(db: Session, hoy: date) -> dict:
    ahora = datetime.now(timezone.utc)
    if (_cache["datos"] is not None and _cache["hoy"] == hoy
            and _cache["expira"] and ahora < _cache["expira"]):
        return _cache["datos"]
    datos = _calcular_datos(db, hoy)
    _cache["datos"] = datos
    _cache["hoy"] = hoy
    _cache["expira"] = ahora + timedelta(seconds=CACHE_TTL_SEGUNDOS)
    return datos


def _filas_y_totales_cacheado(db: Session, hoy: date):
    """Como _filas_y_totales, pero cacheado — y a propósito cachea el
    resultado ya convertido a snapshot plano (nunca objetos ORM vivos): un
    objeto ORM cacheado de una petición anterior queda atado a una sesión ya
    cerrada, y aunque SQLAlchemy tolera leer atributos ya cargados en un
    objeto "detached", es un riesgo innecesario de arrastrar entre
    peticiones. El resto del módulo (`_cache` de KPIs) ya sigue esta misma
    regla: solo se cachean datos planos. Ver ADR-001."""
    ahora = datetime.now(timezone.utc)
    if (_cache_filas["filas"] is not None and _cache_filas["hoy"] == hoy
            and _cache_filas["expira"] and ahora < _cache_filas["expira"]):
        return _cache_filas["filas"]
    filas, proximos_60, costo_anio = _filas_y_totales(db, hoy)
    filas_snap = [{**f, "equipo": snapshot(f["equipo"])} for f in filas]
    resultado = (filas_snap, proximos_60, costo_anio)
    _cache_filas["filas"] = resultado
    _cache_filas["hoy"] = hoy
    _cache_filas["expira"] = ahora + timedelta(seconds=CACHE_TTL_SEGUNDOS)
    return resultado


def _calcular_datos(db: Session, hoy: date) -> dict:
    """Calcula todos los indicadores del dashboard."""
    from dateutil.relativedelta import relativedelta

    equipos = (
        db.query(models.Equipo)
        .filter(models.Equipo.estado != "dado_de_baja")
        .options(
            selectinload(models.Equipo.magnitudes)
                .selectinload(models.MagnitudEquipo.calibraciones),
            selectinload(models.Equipo.magnitudes)
                .selectinload(models.MagnitudEquipo.plan_verificacion)
                .selectinload(models.PlanVerificacion.verificaciones),
            selectinload(models.Equipo.mantenimientos),
        )
        .order_by(models.Equipo.nombre).all()
    )

    total       = len(equipos)
    operativos  = 0
    monitoreados= 0
    cal_vencidas= 0
    cal_30      = 0
    por_area    = {}
    verif_vencidas   = 0
    verif_proximas   = 0
    mant_programados = 0
    proximas_actividades = []
    rango_fin = hoy + timedelta(days=30)

    for eq in equipos:
        if eq.estado == "operativo":
            operativos += 1

        area = eq.area or "Sin área"
        por_area[area] = por_area.get(area, 0) + 1

        # ── Calibraciones ──────────────────────────────────────────────
        proxima_cal = None
        for mag in eq.magnitudes:
            if not mag.activa or not mag.calibraciones:
                continue
            monitoreados_set = True
            ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
            if ul.proxima_calibracion:
                pc = ul.proxima_calibracion
                # normalizar a date
                if hasattr(pc, 'date'): pc = pc.date()
                if proxima_cal is None or pc < proxima_cal:
                    proxima_cal = pc
                # Agregar a proximas_actividades si vencida O próxima 30d
                if pc <= rango_fin:
                    dias = (pc - hoy).days
                    proximas_actividades.append({
                        "tipo":      "calibracion",
                        "titulo":    eq.nombre,
                        "codigo":    eq.codigo,
                        "detalle":   mag.nombre,
                        "fecha":     pc,
                        "dias":      dias,
                        "equipo_id": eq.id,
                        "magnitud_id": mag.id,
                        "icono":     "fa-certificate",
                        "color":     "var(--primary)",
                        "vencida":   dias < 0,
                    })

        # Contar monitoreados
        for mag in eq.magnitudes:
            if mag.activa and mag.calibraciones:
                monitoreados += 1
                break

        if proxima_cal:
            d = (proxima_cal - hoy).days
            if d < 0:
                cal_vencidas += 1
            elif d <= 30:
                cal_30 += 1

        # ── Verificaciones ─────────────────────────────────────────────
        for mag in eq.magnitudes:
            if not mag.activa or not mag.plan_verificacion:
                continue
            plan = mag.plan_verificacion
            if not plan.activo or not plan.frecuencia_meses:
                continue
            verifs = plan.verificaciones
            if verifs:
                prox_v = verifs[0].fecha + relativedelta(months=plan.frecuencia_meses)
            elif mag.calibraciones:
                primera = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
                prox_v = primera.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
            else:
                continue
            if hasattr(prox_v, 'date'): prox_v = prox_v.date()
            dias_v = (prox_v - hoy).days
            if dias_v < 0:
                verif_vencidas += 1
            elif dias_v <= 30:
                verif_proximas += 1
            # Agregar a proximas_actividades si vencida O próxima 30d
            if prox_v <= rango_fin:
                proximas_actividades.append({
                    "tipo":      "verificacion",
                    "titulo":    eq.nombre,
                    "codigo":    eq.codigo,
                    "detalle":   mag.nombre,
                    "fecha":     prox_v,
                    "dias":      dias_v,
                    "equipo_id": eq.id,
                    "magnitud_id": mag.id,
                    "icono":     "fa-check-double",
                    "color":     "var(--success)",
                    "vencida":   dias_v < 0,
                })

        # ── Mantenimientos ─────────────────────────────────────────────
        for mant in eq.mantenimientos:
            if mant.estado != "programado" or not mant.fecha_programada:
                continue
            fd = mant.fecha_programada
            if hasattr(fd, 'date'): fd = fd.date()
            dias_m = (fd - hoy).days
            if 0 <= dias_m <= 60:
                mant_programados += 1
            if fd <= rango_fin:
                proximas_actividades.append({
                    "tipo":      "mantenimiento",
                    "titulo":    eq.nombre,
                    "codigo":    eq.codigo,
                    "detalle":   mant.titulo or mant.tipo or "Mantenimiento",
                    "fecha":     fd,
                    "dias":      dias_m,
                    "equipo_id": eq.id,
                    "mantenimiento_id": mant.id,
                    "icono":     "fa-wrench",
                    "color":     "var(--warning)",
                    "vencida":   dias_m < 0,
                })

    # Ordenar: vencidas primero (más recientes al tope), luego próximas por fecha
    proximas_actividades.sort(key=lambda a: (not a["vencida"], a["fecha"]))

    # Alertas críticas = vencidas + próximas en 7 días
    alertas = [a for a in proximas_actividades if a["dias"] <= 7]
    alertas_count = len(alertas)

    # KPI compuesto
    total_alertas = cal_vencidas + verif_vencidas
    pct_cal = round(((monitoreados - cal_vencidas) / monitoreados * 100)) if monitoreados > 0 else 100

    return {
        "total":                 total,
        "operativos":            operativos,
        "monitoreados":          monitoreados,
        "cal_vencidas":          cal_vencidas,
        "cal_30":                cal_30,
        "verif_vencidas":        verif_vencidas,
        "verif_proximas":        verif_proximas,
        "mant_programados":      mant_programados,
        "pct_cal":               pct_cal,
        "total_alertas":         total_alertas,
        "alertas_count":         alertas_count,
        "por_area":              dict(sorted(por_area.items(), key=lambda x: x[1], reverse=True)),
        "proximas_actividades":  proximas_actividades[:20],
        "alertas":               alertas[:10],
        # retrocompatibilidad con template anterior
        "vencidos":              cal_vencidas,
        "criticos_30":           cal_30,
        "verif_pendientes":      verif_vencidas + verif_proximas,
    }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    hoy = date.today()
    datos = _calcular_datos_cacheado(db, hoy)
    lic = auth.get_licencia_info()
    return T.TemplateResponse(request, "dashboard/dashboard.html", {
        "usuario_actual": u,
        "hoy": hoy,
        "licencia": lic,
        **datos,
    })


def _datos_export_snapshot(db: Session, hoy: date) -> dict:
    """Arma el dict `datos` que consumen los generadores de PDF/Excel del
    dashboard. `_filas_y_totales_cacheado` ya devuelve las filas como
    snapshot plano (picklable) — necesario para poder mandar `datos` a un
    proceso hijo vía ProcessPoolExecutor. Ver ADR-001."""
    datos = _calcular_datos_cacheado(db, hoy)
    filas, proximos_60, costo_anio = _filas_y_totales_cacheado(db, hoy)
    return {**datos, "filas": filas, "proximos_60": proximos_60, "costo_anio": costo_anio}


@router.get("/pdf")
async def exportar_pdf(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    # Verificar licencia para exportar
    from licencia import puede_escribir
    if not puede_escribir():
        return RedirectResponse(url="/dashboard/")

    hoy = date.today()
    datos = _datos_export_snapshot(db, hoy)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()

    from utils.pdf_dashboard import generar_pdf_dashboard
    loop = asyncio.get_running_loop()
    pdf_bytes = await loop.run_in_executor(
        _pdf_pool,
        partial(generar_pdf_dashboard, datos, hoy, snapshot(u), snapshot(config)),
    )
    nombre = f"dashboard_metrogest_{hoy.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(io.BytesIO(pdf_bytes), media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})


@router.get("/excel")
async def exportar_excel(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    from licencia import puede_escribir
    if not puede_escribir():
        return RedirectResponse(url="/dashboard/")

    hoy = date.today()
    datos = _datos_export_snapshot(db, hoy)
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()

    from utils.excel_dashboard import generar_excel_dashboard
    loop = asyncio.get_running_loop()
    excel_bytes = await loop.run_in_executor(
        _pdf_pool,
        partial(generar_excel_dashboard, datos, hoy, snapshot(config)),
    )
    nombre = f"equipos_metrogest_{hoy.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre}"})
