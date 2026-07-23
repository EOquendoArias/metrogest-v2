"""
utils/interpolacion.py
======================
Interpolación de Lagrange para análisis de calibración metrológica.
La curva pasa exactamente por todos los puntos registrados.
"""
import numpy as np


def lagrange_interpolation(x_points, y_points, x_eval):
    """
    Interpolación polinomial de Lagrange.

    Parámetros
    ----------
    x_points : list[float]  — Valores patrón (puntos conocidos)
    y_points : list[float]  — Errores medidos en cada punto (vi - vp)
    x_eval   : float | list[float] — Punto(s) donde evaluar

    Retorna
    -------
    float | list[float]  — Error interpolado en x_eval
    """
    x = np.array(x_points, dtype=float)
    y = np.array(y_points, dtype=float)
    n = len(x)

    def _L(xi: float) -> float:
        result = 0.0
        for i in range(n):
            term = float(y[i])
            for j in range(n):
                if i == j:
                    continue
                denom = float(x[i] - x[j])
                if abs(denom) < 1e-14:
                    return float("nan")   # puntos duplicados → singularidad
                term *= (xi - float(x[j])) / denom
            result += term
        return result

    iterable = hasattr(x_eval, "__iter__") and not isinstance(x_eval, (str, bytes))
    if iterable:
        return [_L(xi) for xi in x_eval]
    return _L(float(x_eval))


def lagrange_curva(x_points, y_points, n_eval: int = 80) -> dict:
    """
    Calcula la curva de Lagrange en *n_eval* puntos uniformes sobre el rango.

    Retorna
    -------
    {"x": [...], "y": [...]}  — listas para graficar (Chart.js)
    """
    xa = np.array(x_points, dtype=float)
    if len(xa) < 2:
        # Con un solo punto no tiene sentido trazar curva
        return {"x": list(xa), "y": list(np.array(y_points, dtype=float))}

    xmin, xmax = float(xa.min()), float(xa.max())
    span    = xmax - xmin if xmax > xmin else 1.0
    padding = span * 0.03

    x_eval = np.linspace(xmin - padding, xmax + padding, n_eval).tolist()
    y_eval = lagrange_interpolation(x_points, y_points, x_eval)

    # Filtrar NaN (ocurren si hay puntos patrón duplicados)
    x_clean, y_clean = [], []
    for xv, yv in zip(x_eval, y_eval):
        if isinstance(yv, float) and yv == yv:   # not NaN
            x_clean.append(round(xv, 10))
            y_clean.append(round(yv, 10))

    return {"x": x_clean, "y": y_clean}


def calcular_ecuacion_lagrange(x_points, y_points) -> dict:
    """
    Calcula los coeficientes del polinomio equivalente al de Lagrange usando
    numpy.polyfit con grado (n-1).  Por el teorema de unicidad de interpolación
    polinomial, el resultado es algebraicamente idéntico a la forma de Lagrange.

    Retorna un dict con:
      - grado            : int
      - coeficientes     : list[float]  (mayor grado primero)
      - ecuacion         : str   — "Y = a·X^n + b·X^(n-1) + …"
      - ecuacion_excel   : str   — "=(a*A1^n)+(b*A1^(n-1))+…"  listo para pegar
    """
    x = np.array(x_points, dtype=float)
    y = np.array(y_points, dtype=float)
    n = len(x)
    grado = n - 1

    if n == 0:
        return {"grado": 0, "coeficientes": [], "ecuacion": "Y = 0", "ecuacion_excel": "=0"}

    coefs = np.polyfit(x, y, grado).tolist()

    # ── Helpers de formato ───────────────────────────────────────────────────

    def _fmt_num(v: float, sig: int = 6) -> str:
        """Número con sig dígitos significativos; notación científica con E mayúscula."""
        s = f"{v:.{sig}g}"
        if "e" in s:
            mantissa, exp_part = s.split("e")
            exp_int = int(exp_part)
            sign = "+" if exp_int >= 0 else ""
            s = f"{mantissa}E{sign}{exp_int}"
        return s

    def _fmt_excel_num(v: float) -> str:
        """Número en formato que Excel interpreta correctamente."""
        return _fmt_num(v, sig=7)

    # ── Ecuación en texto (para mostrar en la UI) ────────────────────────────
    partes_txt = []
    for i, c in enumerate(coefs):
        exp = grado - i
        if abs(c) < 1e-14:
            continue
        signo = "+" if c >= 0 else "-"
        val   = _fmt_num(abs(c))
        if exp == 0:
            partes_txt.append(f"{signo}{val}")
        elif exp == 1:
            partes_txt.append(f"{signo}{val}*X")
        else:
            partes_txt.append(f"{signo}{val}*X^{exp}")

    if partes_txt:
        primera = partes_txt[0]
        if primera.startswith("+"):
            primera = primera[1:]
        ecuacion_txt = "Y = " + primera + (" " + " ".join(partes_txt[1:]) if len(partes_txt) > 1 else "")
    else:
        ecuacion_txt = "Y = 0"

    # ── Ecuación en formato Excel ────────────────────────────────────────────
    partes_xls = []
    for i, c in enumerate(coefs):
        exp = grado - i
        if abs(c) < 1e-14:
            continue
        val = _fmt_excel_num(abs(c))
        if exp == 0:
            term = val
        elif exp == 1:
            term = f"({val}*A1)"
        else:
            term = f"({val}*A1^{exp})"
        partes_xls.append(("+" if c >= 0 else "-") + term)

    if partes_xls:
        primera_xls = partes_xls[0]
        if primera_xls.startswith("+"):
            primera_xls = primera_xls[1:]
        ecuacion_xls = "=" + primera_xls + "".join(partes_xls[1:])
    else:
        ecuacion_xls = "=0"

    return {
        "grado":          grado,
        "coeficientes":   coefs,
        "ecuacion":       ecuacion_txt,
        "ecuacion_excel": ecuacion_xls,
    }


def detectar_oscilacion(x_points, y_points, n_check: int = 200) -> bool:
    """
    Heurístico: ¿La curva de Lagrange oscila excesivamente entre puntos?
    Compara el rango de la curva con el rango de los errores.
    Retorna True si hay riesgo de oscilación de Runge.
    """
    if len(x_points) < 5:
        return False
    curva = lagrange_curva(x_points, y_points, n_eval=n_check)
    if not curva["y"]:
        return False
    rango_curva  = max(curva["y"]) - min(curva["y"])
    rango_puntos = max(y_points) - min(y_points) if y_points else 0
    # Oscilación si la curva es 5× más grande que el rango de errores medidos
    return rango_curva > max(abs(rango_puntos) * 5, 1e-12)
