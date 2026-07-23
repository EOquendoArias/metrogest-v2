"""
utils/horas.py — Método por horas de uso (M3, ILAC-G24 método 3 "in-use time")
==============================================================================
El intervalo se define por horas de operación, no por calendario. El usuario
registra el límite de horas entre calibraciones, las horas acumuladas y un uso
estimado (horas/mes) para traducirlo a una fecha de próxima calibración.
"""
TOPE_MAXIMO_MESES      = 60
TOPE_SIN_JUSTIFICACION = 18
INTERVALO_MINIMO_MESES = 1


def analizar_horas(config_ilac=None, limite=None, acumuladas=None, horas_mes=None) -> dict:
    """
    Calcula el estado por horas de uso y el intervalo equivalente en meses.
    Los valores explícitos (del formulario) tienen prioridad sobre los guardados.
    Estados: 'sin_config', 'config_parcial', 'ok', 'proximo', 'vencido'.
    """
    if limite is None and config_ilac:
        limite = config_ilac.horas_uso_limite
    if acumuladas is None and config_ilac:
        acumuladas = config_ilac.horas_uso_acumuladas
    acumuladas = acumuladas or 0.0
    intervalo_actual = (config_ilac.intervalo_actual_meses if config_ilac else 12) or 12
    tope_max = TOPE_MAXIMO_MESES
    if config_ilac and config_ilac.intervalo_maximo_meses:
        tope_max = min(config_ilac.intervalo_maximo_meses, TOPE_MAXIMO_MESES)

    base = {
        "limite":           limite,
        "acumuladas":       acumuladas,
        "horas_mes":        horas_mes,
        "intervalo_actual": intervalo_actual,
        "tope_sin_justif":  TOPE_SIN_JUSTIFICACION,
        "tope_max":         tope_max,
        "requiere_justificacion": False,
        "intervalo_sugerido": intervalo_actual,
    }

    # Sin límite configurado → no se puede analizar todavía
    if not limite or limite <= 0:
        base.update({
            "estado": "sin_config",
            "mensaje": ("Define el límite de horas de operación entre calibraciones "
                        "para activar este método (por ejemplo, calibrar cada 2000 horas de uso)."),
        })
        return base

    restantes = max(0.0, limite - acumuladas)
    pct = min(100.0, (acumuladas / limite) * 100) if limite else 0.0
    base.update({"horas_restantes": round(restantes, 1), "pct_consumido": round(pct, 1)})

    # Estado por consumo de horas
    if acumuladas >= limite:
        estado = "vencido"
        estado_msg = "El equipo ya superó su límite de horas: debe recalibrarse."
    elif pct >= 80:
        estado = "proximo"
        estado_msg = f"El equipo consumió el {pct:.0f}% de sus horas; se acerca al límite."
    else:
        estado = "ok"
        estado_msg = f"El equipo lleva el {pct:.0f}% de sus horas de uso."

    # Traducción a meses (requiere tasa de uso)
    if horas_mes and horas_mes > 0:
        meses_equiv = restantes / horas_mes
        sugerido = max(INTERVALO_MINIMO_MESES, min(round(meses_equiv), tope_max))
        base.update({
            "estado": estado,
            "meses_equiv": round(meses_equiv, 1),
            "intervalo_total_meses": round(limite / horas_mes, 1),
            "intervalo_sugerido": sugerido,
            "requiere_justificacion": sugerido > TOPE_SIN_JUSTIFICACION,
            "mensaje": (f"{estado_msg} A un ritmo de {horas_mes:.0f} h/mes, quedan "
                        f"{restantes:.0f} horas ≈ {meses_equiv:.0f} meses hasta la próxima calibración."),
        })
    else:
        base.update({
            "estado": "config_parcial",
            "meses_equiv": None,
            "mensaje": (f"{estado_msg} Ingresa el uso estimado (horas por mes) para "
                        f"convertir las {restantes:.0f} horas restantes en una fecha de calibración."),
        })
    return base
