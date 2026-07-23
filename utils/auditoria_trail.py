"""
Rastro de auditoría automático.

Se engancha a nivel de SQLAlchemy (eventos before_flush/after_flush de Session)
en vez de requerir que cada endpoint llame a una función de logging. Así se
audita cualquier escritura sobre las tablas listadas en TABLAS_AUDITADAS, sin
depender de que cada router lo recuerde — el mismo tipo de hueco que se
encontró con el control de acceso por rol en los 18 endpoints.

Basado en el patrón documentado de SQLAlchemy para "version history":
https://docs.sqlalchemy.org/en/20/orm/session_events.html
"""
import json
from contextvars import ContextVar
from datetime import date, datetime

from sqlalchemy import event, inspect
from sqlalchemy.orm import Session

# Tabla -> columnas que se ocultan en el rastro (nunca se guarda el valor real)
TABLAS_AUDITADAS = {
    "usuarios":                   {"hashed_password"},
    "config_laboratorio":         set(),
    "equipos":                    set(),
    "magnitudes_equipo":          set(),
    "calibraciones":              set(),
    "puntos_calibracion":         set(),
    "evaluaciones_riesgo":        set(),
    "config_ilac":                set(),
    "planes_verificacion":        set(),
    "verificaciones_intermedias": set(),
    "puntos_verificacion":        set(),
    "planes_mantenimiento":       set(),
    "mantenimientos":             set(),
    "config_notificaciones":      set(),
}

# Usuario autenticado de la petición actual — lo setea AuditoriaContextMiddleware
# en main.py. Un ContextVar sobrevive el salto al threadpool donde corren los
# endpoints síncronos (anyio copia el contexto al lanzar el hilo).
usuario_actual_id: ContextVar[int | None] = ContextVar("usuario_actual_id", default=None)


def _serializar(valor):
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, (bool, int, float, str)):
        return valor
    return str(valor)


def _es_auditable(obj) -> bool:
    tabla = getattr(obj, "__tablename__", None)
    return tabla in TABLAS_AUDITADAS


def _fila_a_dict(obj) -> dict:
    ocultos = TABLAS_AUDITADAS.get(obj.__tablename__, set())
    mapper = inspect(obj).mapper
    return {
        c.key: ("***" if c.key in ocultos else _serializar(getattr(obj, c.key)))
        for c in mapper.column_attrs
    }


def _registrar_modificaciones(session, obj):
    from models import RegistroAuditoria

    tabla = obj.__tablename__
    ocultos = TABLAS_AUDITADAS.get(tabla, set())
    uid = usuario_actual_id.get()
    estado = inspect(obj)

    for attr in estado.mapper.column_attrs:
        campo = attr.key
        hist = estado.attrs[campo].history
        if not hist.has_changes():
            continue
        anterior = hist.deleted[0] if hist.deleted else None
        nuevo = hist.added[0] if hist.added else None
        if anterior == nuevo:
            continue
        session.add(RegistroAuditoria(
            tabla=tabla, registro_id=obj.id, accion="modificar", campo=campo,
            valor_anterior="***" if campo in ocultos else str(_serializar(anterior)),
            valor_nuevo="***" if campo in ocultos else str(_serializar(nuevo)),
            usuario_id=uid,
        ))


def _registrar_eliminacion(session, obj):
    from models import RegistroAuditoria

    uid = usuario_actual_id.get()
    session.add(RegistroAuditoria(
        tabla=obj.__tablename__, registro_id=obj.id, accion="eliminar",
        valor_anterior=json.dumps(_fila_a_dict(obj), ensure_ascii=False),
        usuario_id=uid,
    ))


@event.listens_for(Session, "before_flush")
def _before_flush(session, flush_context, instances):
    # Las altas necesitan el id generado por la BD -> se registran en after_flush.
    nuevos = [obj for obj in session.new if _es_auditable(obj)]
    if nuevos:
        session.info.setdefault("_audit_nuevos", []).extend(nuevos)

    for obj in list(session.dirty):
        if _es_auditable(obj):
            _registrar_modificaciones(session, obj)

    for obj in list(session.deleted):
        if _es_auditable(obj):
            _registrar_eliminacion(session, obj)


@event.listens_for(Session, "after_flush")
def _after_flush(session, flush_context):
    from models import RegistroAuditoria

    nuevos = session.info.pop("_audit_nuevos", None)
    if not nuevos:
        return
    uid = usuario_actual_id.get()
    # INSERT por Core directo sobre la misma conexión/transacción, sin pasar por
    # el ORM: dentro de after_flush no se puede volver a hacer session.flush()
    # (SQLAlchemy lo rechaza con "Session is already flushing").
    conn = session.connection()
    for obj in nuevos:
        conn.execute(RegistroAuditoria.__table__.insert().values(
            tabla=obj.__tablename__, registro_id=obj.id, accion="crear",
            valor_nuevo=json.dumps(_fila_a_dict(obj), ensure_ascii=False),
            usuario_id=uid,
        ))
