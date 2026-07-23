"""
Búsqueda global — barra de búsqueda en el sidebar que consulta equipos y
certificados de calibración por texto, para no depender de navegar por
el árbol de menús cuando se conoce el código, nombre o número de certificado.
"""
from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session, selectinload
from database import get_db
import models, auth

router = APIRouter()

LIMITE_EQUIPOS = 8
LIMITE_CERTIFICADOS = 5


@router.get("/api")
def buscar(q: str, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or not q or len(q.strip()) < 2:
        return JSONResponse([])

    like = f"%{q.strip()}%"
    resultados = []

    equipos = (db.query(models.Equipo)
               .filter(or_(models.Equipo.nombre.ilike(like),
                           models.Equipo.codigo.ilike(like),
                           models.Equipo.marca.ilike(like),
                           models.Equipo.modelo.ilike(like),
                           models.Equipo.numero_serie.ilike(like)))
               .order_by(models.Equipo.nombre)
               .limit(LIMITE_EQUIPOS).all())
    for e in equipos:
        resultados.append({
            "tipo": "equipo", "icono": "fa-toolbox",
            "titulo": f"{e.nombre} ({e.codigo})",
            "subtitulo": e.area or "Sin área",
            "url": f"/equipos/{e.id}",
        })

    certificados = (db.query(models.Calibracion)
                    .options(selectinload(models.Calibracion.magnitud))
                    .filter(models.Calibracion.numero_certificado.ilike(like))
                    .order_by(models.Calibracion.fecha_calibracion.desc())
                    .limit(LIMITE_CERTIFICADOS).all())
    for c in certificados:
        eq_nombre = c.magnitud.equipo.nombre if c.magnitud and c.magnitud.equipo else ""
        resultados.append({
            "tipo": "certificado", "icono": "fa-certificate",
            "titulo": c.numero_certificado,
            "subtitulo": f"{eq_nombre} — {c.fecha_calibracion.strftime('%d/%m/%Y')}" if eq_nombre else "",
            "url": f"/analisis/{c.id}",
        })

    return JSONResponse(resultados)
