"""
utils/escalera.py — Método de escalera (M4, ILAC-G24 método 1 "staircase")
==========================================================================
Ajuste automático del intervalo según el resultado de la última calibración:
  - Conforme   → sube un paso (equipo demostró estabilidad)
  - No conforme→ baja un paso (hay que vigilar más de cerca)

El "paso" se deriva de porcentaje_escalera (default 80% → paso del 20%).
"""
from utils.deriva import _consumo_tolerancia

FACTOR_DEFAULT         = 0.80    # 80% → paso del 20%
TOPE_MAXIMO_MESES      = 60
TOPE_SIN_JUSTIFICACION = 18
INTERVALO_MINIMO_MESES = 1


def _conforme(cal):
    """True si la calibración quedó dentro de tolerancia (peor punto r < 1)."""
    r = _consumo_tolerancia(cal)
    if r is None:
        return None
    return r < 1.0


def analizar_escalera(magnitud, config_ilac=None) -> dict:
    """
    Aplica el método de escalera y recomienda el siguiente intervalo.
    Estados: 'insuficiente', 'sube', 'baja'.
    """
    cals = sorted(magnitud.calibraciones, key=lambda c: c.fecha_calibracion)
    serie = []
    for c in cals:
        conf = _conforme(c)
        if conf is None:
            continue
        serie.append({"cal": c, "fecha": c.fecha_calibracion, "conforme": conf,
                      "r": _consumo_tolerancia(c)})

    n = len(serie)
    intervalo_actual = (config_ilac.intervalo_actual_meses if config_ilac else 12) or 12
    factor = FACTOR_DEFAULT
    if config_ilac and config_ilac.porcentaje_escalera:
        factor = config_ilac.porcentaje_escalera / 100.0
    paso = round((1 - factor) * 100)     # % del paso, p.ej. 20
    tope_max = TOPE_MAXIMO_MESES
    if config_ilac and config_ilac.intervalo_maximo_meses:
        tope_max = min(config_ilac.intervalo_maximo_meses, TOPE_MAXIMO_MESES)

    base = {
        "n_calibraciones":  n,
        "serie":            serie,
        "intervalo_actual": intervalo_actual,
        "paso_pct":         paso,
        "tope_sin_justif":  TOPE_SIN_JUSTIFICACION,
        "tope_max":         tope_max,
        "requiere_justificacion": False,
    }

    if n < 1:
        base.update({
            "estado": "insuficiente",
            "mensaje": ("El método de escalera necesita al menos una calibración con "
                        "resultado registrado para ajustar el intervalo."),
            "intervalo_sugerido": intervalo_actual,
            "streak": 0, "conforme_ultimo": None,
        })
        return base

    ultimo = serie[-1]
    # Racha: cuántas calibraciones seguidas (desde el final) tienen el mismo resultado
    streak = 0
    for s in reversed(serie):
        if s["conforme"] == ultimo["conforme"]:
            streak += 1
        else:
            break

    if ultimo["conforme"]:
        sugerido = round(intervalo_actual * (1 + (1 - factor)))     # sube un paso
        estado = "sube"
        mensaje = (f"La última calibración fue conforme "
                   f"({streak} conforme{'s' if streak != 1 else ''} seguida{'s' if streak != 1 else ''}). "
                   f"El método de escalera amplía el intervalo un paso del {paso}%: "
                   f"de {intervalo_actual} a {max(1, min(sugerido, tope_max))} meses.")
    else:
        sugerido = round(intervalo_actual * factor)                 # baja un paso
        estado = "baja"
        mensaje = (f"La última calibración salió NO conforme. El método de escalera "
                   f"reduce el intervalo un paso del {paso}%: "
                   f"de {intervalo_actual} a {max(1, min(sugerido, tope_max))} meses, "
                   f"para vigilar el equipo más de cerca.")

    sugerido = max(INTERVALO_MINIMO_MESES, min(sugerido, tope_max))
    base.update({
        "estado": estado,
        "mensaje": mensaje,
        "streak": streak,
        "conforme_ultimo": ultimo["conforme"],
        "intervalo_sugerido": sugerido,
        "requiere_justificacion": sugerido > TOPE_SIN_JUSTIFICACION,
    })
    return base
