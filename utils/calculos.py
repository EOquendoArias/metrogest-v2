import math
from sqlalchemy import func


def proxima_calibracion_por_equipo(db):
    """
    Devuelve {equipo_id: date|None}: la fecha de próxima calibración más cercana
    entre las magnitudes activas de cada equipo, según la última calibración
    registrada de cada magnitud (por fecha_calibracion).

    Calculado en 2-3 consultas agregadas en SQL en vez de recorrer en Python
    todas las magnitudes/calibraciones de cada equipo — evita el problema N+1
    que colapsa con miles de equipos (ver auditoría, hallazgo de rendimiento).
    """
    import models

    ultima_fecha = (
        db.query(models.Calibracion.magnitud_id,
                 func.max(models.Calibracion.fecha_calibracion).label("max_fecha"))
        .group_by(models.Calibracion.magnitud_id)
        .subquery()
    )
    ultima_cal = (
        db.query(models.Calibracion.magnitud_id,
                 models.Calibracion.proxima_calibracion.label("proxima"))
        .join(ultima_fecha,
              (models.Calibracion.magnitud_id == ultima_fecha.c.magnitud_id) &
              (models.Calibracion.fecha_calibracion == ultima_fecha.c.max_fecha))
        .subquery()
    )
    filas = (
        db.query(models.MagnitudEquipo.equipo_id,
                 func.min(ultima_cal.c.proxima).label("proxima"))
        .join(ultima_cal, ultima_cal.c.magnitud_id == models.MagnitudEquipo.id)
        .filter(models.MagnitudEquipo.activa == True)
        .group_by(models.MagnitudEquipo.equipo_id)
        .all()
    )
    return {equipo_id: proxima for equipo_id, proxima in filas}


def calcular_regresiones(puntos, max_grado=5):
    try:
        import numpy as np
    except ImportError:
        return []
    if len(puntos) < 2:
        return []
    x = [p.valor_patron for p in puntos]
    y = [p.valor_indicado for p in puntos]
    xa = np.array(x, dtype=float)
    ya = np.array(y, dtype=float)
    n = len(x)
    resultados = []
    for g in range(1, min(max_grado+1, n)):
        try:
            coef  = np.polyfit(xa, ya, g)
            yp    = np.polyval(coef, xa)
            ss_res = float(np.sum((ya-yp)**2))
            ss_tot = float(np.sum((ya-np.mean(ya))**2))
            r2 = 1 - ss_res/ss_tot if ss_tot > 0 else 1.0
            terms = []
            for i, c in enumerate(coef):
                e = g - i
                if abs(c) < 1e-15: continue
                s = f"{c:+.6g}"
                terms.append(s if e==0 else f"{s}·X" if e==1 else f"{s}·X^{e}")
            eq_str = "Y = " + " ".join(terms) if terms else "Y = 0"
            se = round(float(math.sqrt(ss_res/(n-g-1))), 6) if n > g+1 else None
            resultados.append({
                "grado": g, "coef": coef.tolist(), "r2": round(r2, 6),
                "ecuacion": eq_str, "y_pred": yp.tolist(),
                "residuales": (ya-yp).tolist(), "se": se,
            })
        except Exception:
            continue
    return sorted(resultados, key=lambda r: r["r2"], reverse=True)


def calcular_semaforo(error, incertidumbre, emp):
    """
    Semáforo de conformidad.
    Con incertidumbre: |error| + U <= EMP
    Sin incertidumbre: |error| <= EMP
    """
    if emp is None or error is None:
        return None
    return (abs(error) + (incertidumbre or 0)) <= abs(emp)


def calcular_intervalo_inicial(factores, fabricante_meses=None):
    """
    ILAC-G24 §5.1 — Intervalo inicial de recalibración.
    Tope máximo: 18 meses (enfoque mercado colombiano ISO 9001).
    Tendencia natural: 12 meses como valor más común.

    Escala ajustada:
    - Riesgo muy alto (avg <= 1.5) → 3 meses
    - Riesgo alto     (avg <= 2.0) → 6 meses
    - Riesgo medio    (avg <= 2.5) → 9 meses
    - Riesgo normal   (avg <= 3.0) → 12 meses  ← valor más frecuente
    - Riesgo bajo     (avg >  3.0) → 18 meses  ← tope máximo
    """
    if not factores:
        return 12
    avg = sum(factores) / len(factores)
    if   avg <= 1.5: base = 3
    elif avg <= 2.0: base = 6
    elif avg <= 2.5: base = 9
    elif avg <= 3.0: base = 12
    else:            base = 18   # tope — antes podía llegar a 36

    # Tope absoluto
    base = min(base, 18)

    # Respetar recomendación del fabricante si es más corta
    if fabricante_meses and fabricante_meses < base:
        base = fabricante_meses

    return base
