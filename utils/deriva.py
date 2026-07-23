"""
utils/deriva.py — Análisis de deriva (M1, ILAC-G24 método de carta de control)
==============================================================================
Estudia cómo el error de un equipo se acerca a su EMP calibración tras
calibración, calcula el ritmo de deriva y estima el intervalo óptimo antes
de que el equipo salga de tolerancia.

Concepto clave: "consumo de tolerancia" r = (|error| + U) / EMP del peor punto.
  r = 0.0  → error nulo
  r = 1.0  → justo en el límite (EMP)
  r > 1.0  → fuera de tolerancia
Se rastrea r a lo largo del tiempo y se proyecta cuándo llegará a 1.0.
"""

# ── Parámetros del método ─────────────────────────────────────────────────────
TOPE_MAXIMO_MESES        = 60    # tope absoluto para métodos avanzados
TOPE_SIN_JUSTIFICACION   = 18    # arriba de esto se exige justificación escrita
INTERVALO_MINIMO_MESES   = 1
SAFETY_DEFAULT           = 0.80  # recalibrar al 80% del tiempo estimado hasta el EMP


def _meses_entre(d1, d2) -> float:
    """Meses (con decimales) entre dos fechas."""
    return (d2 - d1).days / 30.4375


def _consumo_tolerancia(cal, usar_u_global: bool = True):
    """
    Fracción de tolerancia consumida por una calibración = su peor punto.
    r = max_p (|error_p| + U_p) / |EMP_p|.   Devuelve None si no hay datos usables.
    """
    usar_u  = getattr(cal, "usar_incertidumbre", usar_u_global)
    mag_emp = cal.magnitud.emp_valor if cal.magnitud else None
    peor = None
    for p in cal.puntos:
        emp = p.emp_punto if p.emp_punto else mag_emp
        if not emp or p.error is None:
            continue
        u = (p.incertidumbre or 0) if usar_u else 0
        r = (abs(p.error) + u) / abs(emp)
        if peor is None or r > peor:
            peor = r
    return peor


def _regresion_lineal(xs, ys):
    """Mínimos cuadrados simple. Retorna (pendiente, intercepto, r2)."""
    n = len(xs)
    if n < 2:
        return 0.0, (ys[0] if ys else 0.0), 0.0
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    if sxx == 0:
        return 0.0, my, 0.0
    b = sxy / sxx
    a = my - b * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 1.0
    return b, a, r2


def _armar_grafica(xs, ys, serie, pendiente, intercepto, t_last, intervalo_sugerido) -> dict:
    """Prepara los datos para Chart.js (consumo de tolerancia en % vs meses)."""
    puntos = [
        {"x": round(x, 2), "y": round(y * 100, 2), "fecha": s["fecha"].strftime("%d/%m/%Y")}
        for x, y, s in zip(xs, ys, serie)
    ]
    x_fin = t_last + max(intervalo_sugerido, 1)
    linea = [
        {"x": 0,               "y": round(intercepto * 100, 2)},
        {"x": round(x_fin, 2), "y": round((intercepto + pendiente * x_fin) * 100, 2)},
    ]
    x_next = t_last + intervalo_sugerido
    y_next = (intercepto + pendiente * x_next) * 100
    return {
        "puntos":     puntos,
        "linea":      linea,
        "x_proximo":  round(x_next, 2),
        "y_proximo":  round(max(y_next, 0), 2),
        "limite":     100.0,
    }


def analizar_deriva(magnitud, config_ilac=None) -> dict:
    """
    Analiza la deriva de una magnitud y recomienda un intervalo.
    Retorna un dict con estado, mensaje, intervalo_sugerido y datos de gráfica.

    Estados posibles:
      - "insuficiente" : menos de 3 calibraciones utilizables
      - "estable"      : sin deriva hacia el EMP → puede ampliarse
      - "deriva"       : deriva normal → intervalo calculado con margen de seguridad
      - "deriva_alta"  : la tendencia ya cruzó (o está por cruzar) el EMP → mínimo
      - "fuera"        : la última calibración salió de tolerancia → mínimo + revisión
    """
    cals = sorted(magnitud.calibraciones, key=lambda c: c.fecha_calibracion)
    serie = []
    for c in cals:
        r = _consumo_tolerancia(c)
        if r is None:
            continue
        serie.append({"cal": c, "fecha": c.fecha_calibracion, "r": r})

    n = len(serie)
    intervalo_actual = (config_ilac.intervalo_actual_meses if config_ilac else 12) or 12
    tope_max = TOPE_MAXIMO_MESES
    if config_ilac and config_ilac.intervalo_maximo_meses:
        tope_max = min(config_ilac.intervalo_maximo_meses, TOPE_MAXIMO_MESES)

    base = {
        "n_calibraciones":  n,
        "serie":            serie,
        "intervalo_actual": intervalo_actual,
        "safety_pct":       round(SAFETY_DEFAULT * 100),
        "tope_sin_justif":  TOPE_SIN_JUSTIFICACION,
        "tope_max":         tope_max,
        "requiere_justificacion": False,
    }

    # ── Datos insuficientes ───────────────────────────────────────────────────
    if n < 3:
        base.update({
            "estado": "insuficiente",
            "mensaje": (f"Se necesitan al menos 3 calibraciones con datos para analizar "
                        f"la deriva. Actualmente hay {n} utilizable(s). Sigue registrando "
                        f"calibraciones y el análisis se activará automáticamente."),
            "intervalo_sugerido": intervalo_actual,
            "pendiente": 0.0, "r2": 0.0, "r_last": serie[-1]["r"] if serie else 0.0,
            "meses_hasta_emp": None, "grafica": None,
        })
        return base

    # ── Serie temporal (meses desde la primera calibración) ───────────────────
    t0 = serie[0]["fecha"]
    xs = [_meses_entre(t0, s["fecha"]) for s in serie]
    ys = [s["r"] for s in serie]
    pendiente, intercepto, r2 = _regresion_lineal(xs, ys)
    r_last = ys[-1]
    t_last = xs[-1]

    # ── La última calibración salió de tolerancia ─────────────────────────────
    if r_last >= 1.0:
        base.update({
            "estado": "fuera",
            "mensaje": ("El equipo salió de tolerancia en la última calibración: consumió "
                        "el 100% o más de su EMP. Se recomienda el intervalo mínimo y una "
                        "revisión técnica del equipo antes de seguir usándolo."),
            "pendiente": pendiente, "r2": r2, "r_last": r_last, "meses_hasta_emp": 0.0,
            "intervalo_sugerido": INTERVALO_MINIMO_MESES,
            "grafica": _armar_grafica(xs, ys, serie, pendiente, intercepto, t_last, INTERVALO_MINIMO_MESES),
        })
        return base

    # ── Deriva hacia el EMP ───────────────────────────────────────────────────
    if pendiente > 1e-9:
        x_emp = (1.0 - intercepto) / pendiente          # mes (desde 1ª cal) donde toca EMP
        meses_hasta_emp = x_emp - t_last
        if meses_hasta_emp <= 0:
            base.update({
                "estado": "deriva_alta",
                "mensaje": ("La tendencia de deriva ya alcanzó el EMP. El equipo está al "
                            "límite de su tolerancia; se recomienda el intervalo mínimo y "
                            "vigilancia estrecha."),
                "pendiente": pendiente, "r2": r2, "r_last": r_last, "meses_hasta_emp": 0.0,
                "intervalo_sugerido": INTERVALO_MINIMO_MESES,
                "grafica": _armar_grafica(xs, ys, serie, pendiente, intercepto, t_last, INTERVALO_MINIMO_MESES),
            })
            return base

        sugerido_raw = meses_hasta_emp * SAFETY_DEFAULT
        sugerido = max(INTERVALO_MINIMO_MESES, min(round(sugerido_raw), tope_max))
        estado = "deriva" if sugerido >= intervalo_actual else "deriva_alta"
        mensaje = (f"El equipo consume su tolerancia a un ritmo de {pendiente*100:.2f}% "
                   f"por mes. A ese ritmo alcanzaría el EMP en ~{meses_hasta_emp:.0f} meses. "
                   f"Aplicando un margen de seguridad del {round((1-SAFETY_DEFAULT)*100)}%, "
                   f"el intervalo recomendado es de {sugerido} meses.")
    else:
        # Pendiente <= 0: estable o mejorando
        meses_hasta_emp = None
        sugerido = max(INTERVALO_MINIMO_MESES, min(tope_max, tope_max))
        estado = "estable"
        mensaje = ("El equipo es muy estable: no muestra deriva hacia su EMP en todo el "
                   "histórico. El intervalo puede ampliarse con seguridad (se exige "
                   "justificación escrita por encima de 18 meses).")

    base.update({
        "estado": estado,
        "mensaje": mensaje,
        "pendiente": pendiente,
        "r2": r2,
        "r_last": r_last,
        "meses_hasta_emp": meses_hasta_emp,
        "intervalo_sugerido": sugerido,
        "requiere_justificacion": sugerido > TOPE_SIN_JUSTIFICACION,
        "grafica": _armar_grafica(xs, ys, serie, pendiente, intercepto, t_last, sugerido),
    })
    return base
