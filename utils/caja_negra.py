"""
utils/caja_negra.py — Método de caja negra (M2, ILAC-G24 método 4 "in-service checking")
========================================================================================
Usa las verificaciones intermedias (chequeos rápidos entre calibraciones) como
evidencia de estabilidad. Si el equipo se mantiene conforme en las verificaciones,
la calibración completa puede espaciarse; si falla, se adelanta.
"""
FACTOR_PASO            = 0.20    # paso del 20% para ampliar/reducir
MIN_VERIF_AMPLIAR      = 2       # verificaciones conformes mínimas para ampliar
TOPE_MAXIMO_MESES      = 60
TOPE_SIN_JUSTIFICACION = 18
INTERVALO_MINIMO_MESES = 1

_CONFORMES = {"aprobado", "conforme", "ok", "aprobada"}


def _clasificar(v, umbral_alerta, umbral_fuera):
    """Retorna ('conforme'|'alerta'|'no_conforme') para una verificación."""
    desv = v.max_desviacion_pct
    res  = (v.resultado or "").lower()
    if res in _CONFORMES or (desv is not None and desv < umbral_fuera):
        if desv is not None and desv >= umbral_alerta:
            return "alerta"
        return "conforme"
    return "no_conforme"


def analizar_caja_negra(verifs, config_ilac=None, plan=None) -> dict:
    """
    Recomienda intervalo según las verificaciones intermedias.
    `verifs` = lista de VerificacionIntermedia de la magnitud.
    Estados: 'sin_datos', 'ampliar', 'mantener', 'reducir'.
    """
    umbral_alerta = plan.umbral_alerta_pct if plan and plan.umbral_alerta_pct else 70.0
    umbral_fuera  = plan.umbral_fuera_pct  if plan and plan.umbral_fuera_pct  else 100.0

    verifs = sorted(verifs or [], key=lambda v: v.fecha)
    serie = []
    for v in verifs:
        estado_v = _clasificar(v, umbral_alerta, umbral_fuera)
        serie.append({"verif": v, "fecha": v.fecha, "estado": estado_v,
                      "desv": v.max_desviacion_pct})

    n = len(serie)
    intervalo_actual = (config_ilac.intervalo_actual_meses if config_ilac else 12) or 12
    tope_max = TOPE_MAXIMO_MESES
    if config_ilac and config_ilac.intervalo_maximo_meses:
        tope_max = min(config_ilac.intervalo_maximo_meses, TOPE_MAXIMO_MESES)

    n_conf   = sum(1 for s in serie if s["estado"] == "conforme")
    n_alerta = sum(1 for s in serie if s["estado"] == "alerta")
    n_fuera  = sum(1 for s in serie if s["estado"] == "no_conforme")

    base = {
        "n_verificaciones": n,
        "serie":            serie,
        "intervalo_actual": intervalo_actual,
        "n_conforme": n_conf, "n_alerta": n_alerta, "n_fuera": n_fuera,
        "umbral_alerta": umbral_alerta, "umbral_fuera": umbral_fuera,
        "tope_sin_justif": TOPE_SIN_JUSTIFICACION, "tope_max": tope_max,
        "requiere_justificacion": False,
    }

    if n == 0:
        base.update({
            "estado": "sin_datos",
            "mensaje": ("Este método usa las verificaciones intermedias como evidencia. "
                        "Aún no hay verificaciones registradas para esta magnitud; "
                        "regístralas para poder espaciar la calibración con respaldo técnico."),
            "intervalo_sugerido": intervalo_actual,
        })
        return base

    if n_fuera > 0:
        sugerido = round(intervalo_actual * (1 - FACTOR_PASO))
        estado, mensaje = "reducir", (
            f"{n_fuera} verificación(es) salieron fuera de tolerancia. Se recomienda "
            f"reducir el intervalo de {intervalo_actual} a {max(1, sugerido)} meses "
            f"y revisar el equipo.")
    elif n >= MIN_VERIF_AMPLIAR and n_alerta == 0:
        sugerido = round(intervalo_actual * (1 + FACTOR_PASO))
        estado, mensaje = "ampliar", (
            f"{n_conf} verificación(es) conformes con margen holgado (bajo el "
            f"{umbral_alerta:.0f}% del EMP). El equipo está bien vigilado: la calibración "
            f"completa puede espaciarse de {intervalo_actual} a {min(sugerido, tope_max)} meses.")
    else:
        sugerido = intervalo_actual
        estado, mensaje = "mantener", (
            f"Hay {n} verificación(es), {n_alerta} en zona de alerta. Se recomienda "
            f"mantener el intervalo en {intervalo_actual} meses hasta acumular más "
            f"evidencia con margen holgado.")

    sugerido = max(INTERVALO_MINIMO_MESES, min(sugerido, tope_max))
    base.update({
        "estado": estado, "mensaje": mensaje,
        "intervalo_sugerido": sugerido,
        "requiere_justificacion": sugerido > TOPE_SIN_JUSTIFICACION,
    })
    return base
