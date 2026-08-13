import io
from datetime import date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload
from dateutil.relativedelta import relativedelta
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")


def _calcular_verif(eq, hoy):
    """Calcula verif_proxima, verif_dias y verif_estado para un equipo."""
    mags_activas = [m for m in eq.magnitudes if m.activa]
    planes_activos = [m.plan_verificacion for m in mags_activas
                      if m.plan_verificacion and m.plan_verificacion.activo]

    if not any(m.plan_verificacion for m in mags_activas):
        return None, None, "sin_plan"

    if not planes_activos:
        return None, None, "no_aplica"

    verif_proxima = None
    for mag in mags_activas:
        plan = mag.plan_verificacion
        if not plan or not plan.activo or not plan.frecuencia_meses:
            continue
        verifs = plan.verificaciones  # ya ordenadas por fecha desc
        if verifs:
            pv = verifs[0].fecha + relativedelta(months=plan.frecuencia_meses)
        elif mag.calibraciones:
            primera = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
            pv = primera.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
        else:
            continue
        if verif_proxima is None or pv < verif_proxima:
            verif_proxima = pv

    if verif_proxima is None:
        return None, None, "sin_plan"

    verif_dias = (verif_proxima - hoy).days

    if verif_dias < 0:
        verif_estado = "vencida"
    elif verif_dias <= 30:
        verif_estado = "pendiente"
    else:
        verif_estado = "al_dia"

    return verif_proxima, verif_dias, verif_estado


def _datos(db, hoy):
    # selectinload evita N+1 queries al recorrer 1,600 equipos (antes esta
    # función cargaba magnitudes/calibraciones/verificaciones/mantenimientos
    # perezosamente, una consulta por relación por equipo). Mismas opciones
    # que ya usa routers/dashboard.py:_calcular_datos — ver ADR-001.
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
    out = []
    for eq in equipos:
        uc = pc = dc = None
        for mag in eq.magnitudes:
            if not mag.activa or not mag.calibraciones:
                continue
            ul = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[-1]
            if uc is None or ul.fecha_calibracion > uc:
                uc = ul.fecha_calibracion
            if ul.proxima_calibracion and (pc is None or ul.proxima_calibracion < pc):
                pc = ul.proxima_calibracion
        if pc:
            dc = (pc - hoy).days

        mants = sorted([m for m in eq.mantenimientos if m.fecha_fin],
                       key=lambda m: m.fecha_fin, reverse=True)

        verif_proxima, verif_dias, verif_estado = _calcular_verif(eq, hoy)

        out.append({
            "equipo":        eq,
            "ultima_cal":    uc,
            "proxima_cal":   pc,
            "dias_cal":      dc,
            "ultimo_mant":   mants[0].fecha_fin if mants else None,
            "verif_proxima": verif_proxima,
            "verif_dias":    verif_dias,
            "verif_estado":  verif_estado,
        })
    return out


@router.get("/", response_class=HTMLResponse)
def resumen(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    hoy = date.today()
    datos = sorted(_datos(db, hoy), key=lambda d: (d["dias_cal"] or 9999))
    return T.TemplateResponse(request, "auditoria/resumen.html", {
        "usuario_actual":     u,
        "datos":              datos,
        "hoy":                hoy,
        "vencidos":           sum(1 for d in datos if d["dias_cal"] is not None and d["dias_cal"] < 0),
        "criticos":           sum(1 for d in datos if d["dias_cal"] is not None and 0 <= d["dias_cal"] <= 30),
        "total":              len(datos),
        "verif_vencidas":     sum(1 for d in datos if d["verif_estado"] == "vencida"),
        "verif_pendientes_30":sum(1 for d in datos if d["verif_estado"] == "pendiente"),
    })


@router.get("/pdf")
def exportar_pdf(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    hoy = date.today()
    datos = sorted(_datos(db, hoy), key=lambda d: (d["dias_cal"] or 9999))
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.pdf_docs import generar_pdf_listado_general
    pdf_bytes = generar_pdf_listado_general(datos, hoy, u, config)
    nombre = f"listado_general_metrogest_{hoy.strftime('%Y%m%d')}.pdf"
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )


@router.get("/excel")
def exportar_excel(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    hoy = date.today()
    datos = sorted(_datos(db, hoy), key=lambda d: (d["dias_cal"] or 9999))
    config = db.query(models.ConfigLaboratorio).first() or models.ConfigLaboratorio()
    from utils.excel_dashboard import generar_excel_listado
    excel_bytes = generar_excel_listado(datos, hoy, config)
    nombre = f"listado_general_metrogest_{hoy.strftime('%Y%m%d')}.xlsx"
    return StreamingResponse(
        io.BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={nombre}"},
    )
