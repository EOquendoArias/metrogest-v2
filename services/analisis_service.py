"""
Lógica de negocio del análisis de resultados de calibración — separada del
router para que routers/analisis.py se limite a parsear la petición HTTP
y traducir el resultado a una respuesta (redirect/template), sin mezclar
ahí las reglas de cálculo, RBAC de datos y efectos secundarios sobre el
equipo.
"""
from datetime import datetime

import models
import utils.firma_electronica as firma
from utils.calculos import calcular_regresiones, calcular_semaforo


def obtener_calibracion(db, cid: int):
    return db.query(models.Calibracion).filter(models.Calibracion.id == cid).first()


def lagrange_para_template(cal, puntos):
    """
    Calcula curva, advertencia de oscilación y ecuación explícita de Lagrange.
    Retorna (curva_dict, warning_bool, ecuacion_dict | None).
    """
    metodo = getattr(cal, "metodo_analisis", "regresion") or "regresion"
    if metodo != "lagrange" or len(puntos) < 2:
        return None, False, None
    try:
        from utils.interpolacion import lagrange_curva, detectar_oscilacion, calcular_ecuacion_lagrange
        x_pts = [p.valor_patron for p in puntos]
        y_pts = [p.error if p.error is not None else 0.0 for p in puntos]
        curva = lagrange_curva(x_pts, y_pts)
        oscila = detectar_oscilacion(x_pts, y_pts) or len(puntos) > 8
        ecuacion = calcular_ecuacion_lagrange(x_pts, y_pts)
        return curva, oscila, ecuacion
    except Exception:
        return None, False, None


def datos_pagina_analisis(db, cal):
    """Arma todo lo derivado de la calibración que necesita la plantilla de
    análisis, más allá de lo que ya trae el propio objeto `cal`."""
    mag = cal.magnitud
    puntos = cal.puntos
    usar_u = cal.usar_incertidumbre if hasattr(cal, "usar_incertidumbre") else True

    for p in puntos:
        p.dentro_tolerancia = calcular_semaforo(
            p.error,
            p.incertidumbre if usar_u else None,
            p.emp_punto
        )

    metodo = getattr(cal, "metodo_analisis", "regresion") or "regresion"

    regs = []
    if len(puntos) >= 2 and mag and mag.tipo_instrumento != "discreto" and metodo == "regresion":
        regs = calcular_regresiones(puntos)

    hist = db.query(models.Calibracion).filter(
        models.Calibracion.magnitud_id == cal.magnitud_id,
        models.Calibracion.id != cal.id
    ).order_by(models.Calibracion.fecha_calibracion.desc()).limit(3).all()

    gs = cal.grado_regresion_sel
    mg = regs[0]["grado"] if regs and not gs else gs

    num_calibraciones = db.query(models.Calibracion).filter(
        models.Calibracion.magnitud_id == cal.magnitud_id
    ).count()
    es_segunda_o_posterior = num_calibraciones >= 2

    config_ilac = db.query(models.ConfigILAC).filter(
        models.ConfigILAC.magnitud_id == cal.magnitud_id
    ).first() if mag else None

    lagrange_curve, lagrange_warning, lagrange_ecuacion = lagrange_para_template(cal, puntos)

    return {
        "magnitud":                mag,
        "equipo":                  mag.equipo if mag else None,
        "puntos":                  puntos,
        "regresiones":             regs,
        "mejor_grado":             mg,
        "grado_sel":               gs,
        "historico":               hist,
        "emp":                     mag.emp_valor if mag else None,
        "usar_incertidumbre":      usar_u,
        "ok":                      sum(1 for p in puntos if p.dentro_tolerancia is True),
        "fail":                    sum(1 for p in puntos if p.dentro_tolerancia is False),
        "aprobado":                cal.resultado == "aprobado",
        "aprobado_por":            cal.aprobado_por,
        "fecha_aprobacion":        cal.fecha_aprobacion,
        "es_segunda_o_posterior":  es_segunda_o_posterior,
        "config_ilac":             config_ilac,
        "metodo_analisis":         metodo,
        "lagrange_curve":          lagrange_curve,
        "lagrange_warning":        lagrange_warning,
        "lagrange_ecuacion":       lagrange_ecuacion,
    }


def toggle_incertidumbre(db, cal, usar: bool):
    if cal and hasattr(cal, "usar_incertidumbre"):
        cal.usar_incertidumbre = usar
        db.commit()


def seleccionar_metodo(db, cal, metodo: str):
    if cal and metodo in ("regresion", "lagrange"):
        cal.metodo_analisis = metodo
        db.commit()


def construir_punto(cal, numero_punto, valor_patron, valor_indicado,
                     incertidumbre, tolerancia_inf, tolerancia_sup,
                     emp_punto, observacion):
    """Misma lógica de cálculo (error, EMP, tolerancias, semáforo) que usa
    tanto agregar un punto solo como el lote — para no duplicarla."""
    usar_u = cal.usar_incertidumbre if hasattr(cal, "usar_incertidumbre") else True
    err = round(valor_indicado - valor_patron, 8)
    u_val = float(incertidumbre) if incertidumbre and usar_u else None
    emp_p = float(emp_punto) if emp_punto else (cal.magnitud.emp_valor if cal.magnitud else None)
    ti = float(tolerancia_inf) if tolerancia_inf else (-abs(emp_p) if emp_p else None)
    ts = float(tolerancia_sup) if tolerancia_sup else (abs(emp_p) if emp_p else None)
    dentro = calcular_semaforo(err, u_val, emp_p)
    aeu = round(abs(err) + (u_val or 0), 8)
    return models.PuntoCalibracion(
        calibracion_id=cal.id, numero_punto=numero_punto,
        valor_patron=valor_patron, valor_indicado=valor_indicado, error=err,
        tolerancia_inf=ti, tolerancia_sup=ts,
        incertidumbre=float(incertidumbre) if incertidumbre else None,
        abs_error_mas_u=aeu, emp_punto=emp_p,
        dentro_tolerancia=dentro, observacion=observacion or None)


def _contar_puntos_activos(db, cid: int) -> int:
    return db.query(models.PuntoCalibracion).filter(
        models.PuntoCalibracion.calibracion_id == cid,
        models.PuntoCalibracion.eliminado == False).count()


def agregar_punto(db, cal, valor_patron, valor_indicado, incertidumbre,
                   tolerancia_inf, tolerancia_sup, emp_punto, observacion):
    n = _contar_puntos_activos(db, cal.id)
    db.add(construir_punto(cal, n + 1, valor_patron, valor_indicado,
                            incertidumbre, tolerancia_inf, tolerancia_sup,
                            emp_punto, observacion))
    db.commit()


def agregar_puntos_lote(db, cal, valor_patron, valor_indicado, incertidumbre,
                         tolerancia_inf, tolerancia_sup, emp_punto, observacion):
    """Varias filas de puntos en un solo envío — antes había que agregar los
    puntos de a uno, con una recarga de página por cada uno (10-13 clics para
    una calibración típica). Retorna cuántas filas realmente se agregaron."""
    n = _contar_puntos_activos(db, cal.id)
    agregados = 0
    for i in range(len(valor_patron)):
        vp = (valor_patron[i] or "").strip()
        vi = (valor_indicado[i] if i < len(valor_indicado) else "").strip()
        if not vp or not vi:
            continue  # fila vacía (dejada así a propósito) — se ignora, no es error
        agregados += 1
        db.add(construir_punto(
            cal, n + agregados, float(vp), float(vi),
            (incertidumbre[i] if i < len(incertidumbre) else "").strip(),
            (tolerancia_inf[i] if i < len(tolerancia_inf) else "").strip(),
            (tolerancia_sup[i] if i < len(tolerancia_sup) else "").strip(),
            (emp_punto[i] if i < len(emp_punto) else "").strip(),
            (observacion[i] if i < len(observacion) else "").strip(),
        ))
    if agregados:
        db.commit()
    return agregados


def eliminar_punto(db, cid: int, pid: int, usuario_id: int):
    p = db.query(models.PuntoCalibracion).filter(
        models.PuntoCalibracion.id == pid,
        models.PuntoCalibracion.eliminado == False).first()
    if not p:
        return False
    p.eliminado = True
    p.eliminado_en = datetime.now()
    p.eliminado_por_id = usuario_id
    db.flush()
    for i, pt in enumerate(db.query(models.PuntoCalibracion).filter(
        models.PuntoCalibracion.calibracion_id == cid,
        models.PuntoCalibracion.eliminado == False
    ).order_by(models.PuntoCalibracion.numero_punto).all()):
        pt.numero_punto = i + 1
    db.commit()
    return True


def seleccionar_regresion(db, cal, grado: int):
    if cal:
        cal.grado_regresion_sel = grado
        cal.metodo_analisis = "regresion"  # asegurar que el método sea regresion
        db.commit()


def aprobar_calibracion(db, request, u, cal, obs_aprobacion: str, password: str):
    """Firma electrónica + efectos secundarios de aprobar una calibración
    (poner el equipo operativo y dejar constancia en su historial de estado).
    Retorna (ok: bool, error: str | None)."""
    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "calibraciones", cal.id, "aprobar_calibracion")
    if not ok:
        return False, error

    cal.resultado = "aprobado"
    cal.aprobado_por_id = u.id
    cal.fecha_aprobacion = datetime.now()
    eq = db.query(models.Equipo).filter(models.Equipo.id == cal.equipo_id).first()
    if eq:
        ant = eq.estado
        eq.estado = "operativo"
        eq.apto_para_uso = True
        eq.confirmacion_metrologica = True
        db.add(models.HistorialEstado(
            equipo_id=eq.id, usuario_id=u.id,
            estado_anterior=ant, estado_nuevo="operativo",
            motivo=f"Calibración aprobada — {cal.numero_certificado or cal.id}. {obs_aprobacion}"))
    db.commit()
    return True, None
