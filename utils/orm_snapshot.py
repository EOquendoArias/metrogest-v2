"""
Snapshot de objetos SQLAlchemy para mandarlos a un ProcessPoolExecutor.

Los generadores de PDF/Excel (utils/pdf_analisis.py, utils/pdf_dashboard.py,
utils/excel_dashboard.py, utils/pdf_docs.py) reciben objetos ORM (Calibracion,
Equipo, MagnitudEquipo, ConfigLaboratorio, Usuario...) y navegan sus
relaciones (`cal.magnitud.equipo`, etc.). Esos objetos están atados a una
Session de SQLAlchemy y no se pueden mandar tal cual a otro proceso — ni son
picklables de forma confiable, ni tendrían sesión viva del otro lado.

`snapshot(obj)` copia cualquier instancia ya cargada (columnas escalares +
relaciones ya cargadas, recursivamente) a un `SimpleNamespace` desconectado
de la sesión, con los mismos nombres de atributo — así el código existente
de los generadores (`eq.nombre`, `cal.magnitud.equipo.codigo`, etc.) sigue
funcionando sin cambios, ahora sobre datos planos y picklables.

Importante: solo copia relaciones que YA estén cargadas en el momento de
llamar a `snapshot()` (`sqlalchemy.inspect(obj).unloaded`). No dispara
lazy-loads nuevos a propósito, para que el costo de queries sea explícito y
predecible — quien llama a `snapshot()` debe tocar antes cualquier relación
que el generador vaya a necesitar (ej. `_ = cal.magnitud and cal.magnitud.equipo`)
mientras la sesión sigue abierta, en el hilo/proceso principal.
"""
from datetime import date, datetime, time
from decimal import Decimal
from types import SimpleNamespace

from sqlalchemy import inspect as sa_inspect

_ESCALARES = (str, int, float, bool, bytes, Decimal, date, datetime, time, type(None))


def snapshot(obj, _seen=None):
    """Convierte `obj` (instancia ORM, lista de instancias, o valor plano ya
    escalar) en algo seguro de picklear y mandar a otro proceso."""
    if isinstance(obj, _ESCALARES):
        return obj

    if _seen is None:
        _seen = {}

    if isinstance(obj, (list, tuple)):
        return [snapshot(o, _seen) for o in obj]

    insp = None
    try:
        insp = sa_inspect(obj)
    except Exception:
        pass

    if insp is None or not getattr(insp, "mapper", None):
        # No es una instancia ORM reconocida (ej. dict ya plano) — se deja igual.
        return obj

    if id(obj) in _seen:
        return _seen[id(obj)]

    ns = SimpleNamespace()
    _seen[id(obj)] = ns

    # A propósito NO se atrapa DetachedInstanceError aquí: si una columna no
    # se puede leer, es mejor que falle ruidosamente ahora (error 500 visible
    # en pruebas) a que el documento generado quede con un dato faltante sin
    # que nadie se entere — este software genera evidencia para auditorías.
    for attr in insp.mapper.column_attrs:
        setattr(ns, attr.key, getattr(obj, attr.key))

    unloaded = insp.unloaded
    for rel in insp.mapper.relationships:
        if rel.key in unloaded:
            continue  # no cargada: no se dispara un lazy-load nuevo aquí
        setattr(ns, rel.key, snapshot(getattr(obj, rel.key), _seen))

    return ns
