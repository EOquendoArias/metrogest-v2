"""
Lógica de negocio de las verificaciones intermedias — separada del router
por la misma razón que services/analisis_service.py: que
routers/verificaciones.py se limite a parsear la petición HTTP y traducir
el resultado a una respuesta, sin mezclar ahí el cálculo de desviación,
la recalculación del resultado agregado y los efectos de la firma.
"""
import uuid
from datetime import date, datetime
from dateutil.relativedelta import relativedelta

import models
import utils.firma_electronica as firma
from utils.validar_archivo import (guardar_archivo_validado, EXTENSIONES_DOCUMENTO,
                                    EXTENSIONES_IMAGEN, MAX_TAMANO_DOCUMENTO_BYTES)

EXTENSIONES_ARCHIVO_VERIF = EXTENSIONES_DOCUMENTO | EXTENSIONES_IMAGEN


def obtener_magnitud(db, mid: int):
    return db.query(models.MagnitudEquipo).filter(models.MagnitudEquipo.id == mid).first()


def obtener_plan(db, mid: int):
    return db.query(models.PlanVerificacion).filter(models.PlanVerificacion.magnitud_id == mid).first()


def obtener_verificacion(db, vid: int):
    return db.query(models.VerificacionIntermedia).filter(models.VerificacionIntermedia.id == vid).first()


def guardar_plan(db, mid, mag, activo, frecuencia_meses, procedimiento,
                  patron_referencia, umbral_alerta_pct, umbral_fuera_pct,
                  justificacion_no_aplica, aprobado_por_nombre,
                  aprobado_por_cargo, fecha_aprobacion):
    plan = obtener_plan(db, mid)
    hace = (activo == "true")
    # frecuencia_meses tiene NOT NULL en la BD; cuando no aplica conservamos el valor
    # anterior o usamos 12 como placeholder (se ignora en la lógica cuando activo=False)
    if hace:
        frec = int(frecuencia_meses) if frecuencia_meses else 12
    else:
        frec = (plan.frecuencia_meses if plan and plan.frecuencia_meses else 12)
    fapb = date.fromisoformat(fecha_aprobacion) if fecha_aprobacion else None
    v = dict(
        magnitud_id=mid, equipo_id=mag.equipo_id,
        activo=hace,
        frecuencia_meses=frec,
        procedimiento=procedimiento or None,
        patron_referencia=patron_referencia or None,
        umbral_alerta_pct=umbral_alerta_pct,
        umbral_fuera_pct=umbral_fuera_pct,
        justificacion_no_aplica=justificacion_no_aplica or None,
        aprobado_por_nombre=aprobado_por_nombre or None,
        aprobado_por_cargo=aprobado_por_cargo or None,
        fecha_aprobacion=fapb,
    )
    if plan:
        for k, val in v.items(): setattr(plan, k, val)
    else:
        plan = models.PlanVerificacion(**v)
        db.add(plan)
    db.commit()
    return plan


def datos_historial(db, mag, plan):
    verifs = plan.verificaciones if plan else []
    hoy = date.today()
    proxima = None
    if plan and verifs:
        ultima_ver = verifs[0]
        proxima = ultima_ver.fecha + relativedelta(months=plan.frecuencia_meses)
    elif plan and mag.calibraciones:
        primera_cal = sorted(mag.calibraciones, key=lambda c: c.fecha_calibracion)[0]
        proxima = primera_cal.fecha_calibracion + relativedelta(months=plan.frecuencia_meses)
    dias = (proxima - hoy).days if proxima else None
    return verifs, hoy, proxima, dias


def crear_verificacion(db, mid, mag, plan, fecha, tipo, realizada_por,
                        patron_usado, observaciones, archivo):
    ap = None
    if archivo and archivo.filename:
        n = f"static/certificados/verif_{uuid.uuid4()}"
        ruta = guardar_archivo_validado(archivo, n, EXTENSIONES_ARCHIVO_VERIF, MAX_TAMANO_DOCUMENTO_BYTES)
        ap = f"/{ruta}"
    fv = date.fromisoformat(fecha)
    ver = models.VerificacionIntermedia(
        plan_id=plan.id, equipo_id=mag.equipo_id, magnitud_id=mid,
        fecha=fv, proxima_verificacion=fv + relativedelta(months=plan.frecuencia_meses),
        tipo=tipo, realizada_por=realizada_por or None,
        patron_usado=patron_usado or plan.patron_referencia or None,
        observaciones=observaciones or None, archivo_path=ap, resultado="pendiente")
    db.add(ver)
    db.commit()
    db.refresh(ver)
    return ver


def construir_punto_verificacion(ver, numero_punto, valor_patron, valor_indicado,
                                  tolerancia_inf, tolerancia_sup, observacion):
    """Misma lógica de cálculo (error, desviación %, resultado ok/alerta/fuera)
    que usa tanto agregar un punto solo como el lote."""
    err = round(valor_indicado - valor_patron, 8)
    emp = ver.magnitud.emp_valor if ver.magnitud else None
    ti = float(tolerancia_inf) if tolerancia_inf else (-abs(emp) if emp else None)
    ts = float(tolerancia_sup) if tolerancia_sup else (abs(emp) if emp else None)
    desv = round(abs(err) / abs(emp) * 100, 2) if emp else None
    ua = ver.plan.umbral_alerta_pct if ver.plan else 70
    uf = ver.plan.umbral_fuera_pct if ver.plan else 100
    res = ("fuera" if desv and desv >= uf else "alerta" if desv and desv >= ua else "ok") if desv is not None else None
    return models.PuntoVerificacion(verificacion_id=ver.id, numero_punto=numero_punto,
        valor_patron=valor_patron, valor_indicado=valor_indicado, error=err,
        tolerancia_inf=ti, tolerancia_sup=ts, desviacion_pct=desv,
        resultado=res, observacion=observacion or None)


def recalcular_resultado_verificacion(db, ver):
    pts = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.verificacion_id == ver.id,
        models.PuntoVerificacion.eliminado == False).all()
    rs = [p.resultado for p in pts if p.resultado]
    ds = [p.desviacion_pct for p in pts if p.desviacion_pct is not None]
    ver.max_desviacion_pct = max(ds) if ds else None
    ver.resultado = "reprobado" if "fuera" in rs else "alerta" if "alerta" in rs else "aprobado" if rs else "pendiente"


def _contar_puntos_activos(db, vid: int) -> int:
    return db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.verificacion_id == vid,
        models.PuntoVerificacion.eliminado == False).count()


def agregar_punto(db, ver, valor_patron, valor_indicado, tolerancia_inf,
                   tolerancia_sup, observacion):
    n = _contar_puntos_activos(db, ver.id)
    db.add(construir_punto_verificacion(ver, n + 1, valor_patron, valor_indicado,
                                         tolerancia_inf, tolerancia_sup, observacion))
    db.flush()
    recalcular_resultado_verificacion(db, ver)
    db.commit()


def agregar_puntos_lote(db, ver, valor_patron, valor_indicado, tolerancia_inf,
                         tolerancia_sup, observacion):
    """Varias filas de puntos en un solo envío — mismo espíritu que el lote
    de análisis de calibración. Retorna cuántas filas se agregaron."""
    n = _contar_puntos_activos(db, ver.id)
    agregados = 0
    for i in range(len(valor_patron)):
        vp = (valor_patron[i] or "").strip()
        vi = (valor_indicado[i] if i < len(valor_indicado) else "").strip()
        if not vp or not vi:
            continue
        agregados += 1
        db.add(construir_punto_verificacion(
            ver, n + agregados, float(vp), float(vi),
            (tolerancia_inf[i] if i < len(tolerancia_inf) else "").strip(),
            (tolerancia_sup[i] if i < len(tolerancia_sup) else "").strip(),
            (observacion[i] if i < len(observacion) else "").strip(),
        ))
    if agregados:
        db.flush()
        recalcular_resultado_verificacion(db, ver)
        db.commit()
    return agregados


def eliminar_punto(db, vid: int, pid: int, usuario_id: int):
    p = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.id == pid,
        models.PuntoVerificacion.eliminado == False).first()
    if not p:
        return False
    p.eliminado = True
    p.eliminado_en = datetime.now()
    p.eliminado_por_id = usuario_id
    db.flush()
    pts = db.query(models.PuntoVerificacion).filter(
        models.PuntoVerificacion.verificacion_id == vid,
        models.PuntoVerificacion.eliminado == False
    ).order_by(models.PuntoVerificacion.numero_punto).all()
    for i, pt in enumerate(pts):
        pt.numero_punto = i + 1
    # Bug encontrado en la Fase 2.2 (docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md
    # ítem 5): a diferencia de agregar_punto/agregar_puntos_lote, esta
    # función no recalculaba `resultado` tras eliminar un punto — si el
    # punto eliminado era el único "fuera" o "alerta", la verificación
    # quedaba marcada reprobada/en alerta indefinidamente aunque los puntos
    # restantes estuvieran todos ok.
    ver = db.query(models.VerificacionIntermedia).filter(
        models.VerificacionIntermedia.id == vid).first()
    if ver:
        recalcular_resultado_verificacion(db, ver)
    db.commit()
    return True


def cerrar_verificacion(db, request, u, ver, accion_tomada, observaciones, password):
    """Firma electrónica + guardado de la acción tomada y observaciones
    finales de la verificación. Retorna (ok: bool, error: str | None).

    Guardia agregada en la Fase 2.2 (docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md
    ítem 5), mismo patrón que la guardia anti-reaprobación de
    services/analisis_service.py::aprobar_calibracion tras el hallazgo de
    PQ-7: sin esto, un segundo POST a este endpoint (petición directa o
    pestaña vieja del navegador) podía re-firmar una verificación ya
    cerrada, sobrescribiendo accion_tomada/observaciones sin aviso.
    """
    if ver.accion_tomada is not None:
        return False, "Esta verificación ya fue cerrada — no se puede volver a cerrar."

    ok, error = firma.verificar_y_firmar(db, request, u, password,
        "verificaciones_intermedias", ver.id, "cerrar_verificacion")
    if not ok:
        return False, error
    ver.accion_tomada = accion_tomada
    if observaciones:
        ver.observaciones = observaciones
    db.commit()
    return True, None
