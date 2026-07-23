from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")

PAGE_SIZE = 50

ACCIONES_LABEL = {"crear": "Creación", "modificar": "Modificación", "eliminar": "Eliminación"}


@router.get("/", response_class=HTMLResponse)
def lista(request: Request, db: Session = Depends(get_db),
          page: int = 1, tabla: str = "", usuario_id: int = 0, accion: str = ""):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")

    query = db.query(models.RegistroAuditoria)
    if tabla:
        query = query.filter(models.RegistroAuditoria.tabla == tabla)
    if usuario_id:
        query = query.filter(models.RegistroAuditoria.usuario_id == usuario_id)
    if accion:
        query = query.filter(models.RegistroAuditoria.accion == accion)

    total = query.count()
    total_paginas = max(1, -(-total // PAGE_SIZE))
    page = min(max(1, page), total_paginas)

    registros = (query.order_by(models.RegistroAuditoria.fecha.desc())
                 .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all())

    tablas_disponibles = sorted(
        t for (t,) in db.query(models.RegistroAuditoria.tabla).distinct().all()
    )
    usuarios_disponibles = db.query(models.Usuario).order_by(models.Usuario.nombre).all()

    return T.TemplateResponse(request, "registro_auditoria/lista.html", {
        "usuario_actual": u, "registros": registros,
        "page": page, "total_paginas": total_paginas, "total": total,
        "tabla_filtro": tabla, "usuario_filtro": usuario_id, "accion_filtro": accion,
        "tablas_disponibles": tablas_disponibles, "usuarios_disponibles": usuarios_disponibles,
        "acciones_label": ACCIONES_LABEL,
    })


ACCIONES_FIRMA_LABEL = {
    "aprobar_calibracion":               "Aprobar calibración",
    "cerrar_verificacion":               "Cerrar verificación intermedia",
    "definir_intervalo_ilac_riesgo":     "Definir intervalo ILAC — Evaluación de riesgo (§5.1)",
    "definir_intervalo_ilac_estandar":   "Definir intervalo ILAC — Período estándar",
    "definir_intervalo_ilac_deriva":     "Definir intervalo ILAC — M1 Análisis de deriva",
    "definir_intervalo_ilac_escalera":   "Definir intervalo ILAC — M4 Escalera",
    "definir_intervalo_ilac_caja_negra": "Definir intervalo ILAC — M2 Caja negra",
    "definir_intervalo_ilac_horas":      "Definir intervalo ILAC — M3 Horas de uso",
    "cambiar_estado_equipo":             "Cambiar estado de equipo",
}


@router.get("/firmas", response_class=HTMLResponse)
def firmas(request: Request, db: Session = Depends(get_db),
           page: int = 1, accion: str = "", usuario_id: int = 0):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")

    query = db.query(models.FirmaElectronica)
    if accion:
        query = query.filter(models.FirmaElectronica.accion == accion)
    if usuario_id:
        query = query.filter(models.FirmaElectronica.usuario_id == usuario_id)

    total = query.count()
    total_paginas = max(1, -(-total // PAGE_SIZE))
    page = min(max(1, page), total_paginas)

    firmas = (query.order_by(models.FirmaElectronica.fecha.desc())
              .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE).all())

    usuarios_disponibles = db.query(models.Usuario).order_by(models.Usuario.nombre).all()

    return T.TemplateResponse(request, "registro_auditoria/firmas.html", {
        "usuario_actual": u, "firmas": firmas,
        "page": page, "total_paginas": total_paginas, "total": total,
        "accion_filtro": accion, "usuario_filtro": usuario_id,
        "usuarios_disponibles": usuarios_disponibles,
        "acciones_label": ACCIONES_FIRMA_LABEL,
    })
