"""
Flujo de aprobación de calibración — de principio a fin, vía HTTP real.

Fase 2.2 (docs/PROJECT_PLAN.md §2.2), hallazgo #1 de docs/calidad/COBERTURA.md:
"POST /analisis/{cid}/aprobar combina el semáforo de conformidad, la firma
electrónica y el cambio de estado del equipo — es el evento de negocio
central del sistema y hoy depende enteramente de pruebas manuales."

Antes de este archivo, el único test que tocaba /analisis/{cid}/aprobar era
manual. Este archivo cubre:
- El camino feliz completo (puntos -> método -> aprobar) con sus efectos
  secundarios reales sobre el equipo, el historial y la firma electrónica.
- Los tres "challenge tests" de riesgo alto que ya estaban listados en
  OQ_CALIFICACION_OPERACIONAL.md (OQ-A4, OQ-A5) pero sin test automatizado
  para el endpoint completo, solo para la función de firma aislada.
- La guardia anti-reaprobación agregada en services/analisis_service.py
  tras el hallazgo de PQ-7 (docs/calidad/PLAN_PRUEBAS_CARGA.md §7) — hasta
  ahora solo se había validado que pytest no se rompiera, no que el
  endpoint HTTP la respete.
"""
from datetime import date

import auth
import models


def _crear_usuario(db, email, rol, password="ClaveTest123"):
    u = models.Usuario(nombre=f"Usuario {rol}", email=email, rol=rol,
                        hashed_password=auth.hash_password(password))
    db.add(u)
    db.commit()
    return u


def _login(client, email, password="ClaveTest123"):
    r = client.post("/usuarios/login", data={"email": email, "password": password},
                     follow_redirects=False)
    assert r.status_code in (302, 303), f"login falló: {r.status_code} {r.text[:200]}"


def _crear_equipo_con_magnitud(db, codigo="EQ-FLUJO-1"):
    equipo = models.Equipo(codigo=codigo, nombre="Balanza de prueba",
                            estado="en_espera_calibracion",
                            apto_para_uso=False, confirmacion_metrologica=False)
    db.add(equipo)
    db.commit()
    magnitud = models.MagnitudEquipo(equipo_id=equipo.id, nombre="Masa",
                                      emp_valor=0.5, activa=True)
    db.add(magnitud)
    db.commit()
    return equipo, magnitud


def _crear_calibracion_pendiente(db, magnitud, equipo, numero_certificado="CERT-001"):
    cal = models.Calibracion(magnitud_id=magnitud.id, equipo_id=equipo.id,
                              numero_certificado=numero_certificado,
                              fecha_calibracion=date(2026, 1, 1),
                              resultado="pendiente", metodo_analisis="regresion")
    db.add(cal)
    db.commit()
    return cal


def _agregar_puntos_via_http(client, cal_id):
    """Reproduce lo que hace el formulario de lote en la plantilla real:
    3 puntos dentro de tolerancia (EMP=0.5 heredado de la magnitud)."""
    r = client.post(f"/analisis/{cal_id}/puntos/lote", data={
        "valor_patron":   ["10", "20", "30"],
        "valor_indicado": ["10.1", "20.1", "29.9"],
        "incertidumbre":  ["0.05", "0.05", "0.05"],
        "tolerancia_inf": ["", "", ""],
        "tolerancia_sup": ["", "", ""],
        "emp_punto":      ["", "", ""],
        "observacion":    ["", "", ""],
    }, follow_redirects=False)
    assert r.status_code == 303


# ── Camino feliz completo ─────────────────────────────────────────────────

def test_flujo_completo_aprobacion_pone_equipo_operativo_y_deja_evidencia(client, db):
    equipo, magnitud = _crear_equipo_con_magnitud(db)
    cal = _crear_calibracion_pendiente(db, magnitud, equipo)
    operador = _crear_usuario(db, "operador_flujo@test.com", "operador")
    _login(client, "operador_flujo@test.com")

    _agregar_puntos_via_http(client, cal.id)
    assert db.query(models.PuntoCalibracion).filter_by(
        calibracion_id=cal.id, eliminado=False).count() == 3

    r = client.post(f"/analisis/{cal.id}/metodo", data={"metodo": "regresion"},
                     follow_redirects=False)
    assert r.status_code == 303

    r = client.post(f"/analisis/{cal.id}/aprobar", data={
        "obs_aprobacion": "Cumple especificaciones",
        "password": "ClaveTest123",
    }, follow_redirects=False)
    assert r.status_code == 303
    assert "error_firma" not in r.headers.get("location", "")

    db.refresh(cal)
    db.refresh(equipo)

    # Efecto sobre la calibración
    assert cal.resultado == "aprobado"
    assert cal.aprobado_por_id == operador.id
    assert cal.fecha_aprobacion is not None

    # Efecto sobre el equipo (el motivo de negocio de todo el flujo)
    assert equipo.estado == "operativo"
    assert equipo.apto_para_uso is True
    assert equipo.confirmacion_metrologica is True

    # Historial de estado con constancia de motivo y usuario
    hist = db.query(models.HistorialEstado).filter_by(equipo_id=equipo.id).one()
    assert hist.estado_anterior == "en_espera_calibracion"
    assert hist.estado_nuevo == "operativo"
    assert hist.usuario_id == operador.id
    assert "CERT-001" in hist.motivo

    # Firma electrónica registrada (Ley 527/1999) con su propio rastro de auditoría
    firma_row = db.query(models.FirmaElectronica).filter_by(
        tabla="calibraciones", registro_id=cal.id).one()
    assert firma_row.usuario_id == operador.id
    assert db.query(models.RegistroAuditoria).filter_by(
        tabla="firmas_electronicas", registro_id=firma_row.id, accion="crear").count() == 1


# ── Challenge tests de riesgo alto (ver OQ-A4, OQ-A5) ─────────────────────

def test_password_incorrecta_no_aprueba_ni_toca_el_equipo(client, db):
    equipo, magnitud = _crear_equipo_con_magnitud(db, "EQ-FLUJO-2")
    cal = _crear_calibracion_pendiente(db, magnitud, equipo, "CERT-002")
    _crear_usuario(db, "operador_flujo2@test.com", "operador")
    _login(client, "operador_flujo2@test.com")

    r = client.post(f"/analisis/{cal.id}/aprobar",
                     data={"obs_aprobacion": "", "password": "clave-incorrecta"},
                     follow_redirects=False)
    assert r.status_code == 303
    assert "error_firma=1" in r.headers["location"]

    db.refresh(cal)
    db.refresh(equipo)
    assert cal.resultado == "pendiente"
    assert cal.aprobado_por_id is None
    assert equipo.estado == "en_espera_calibracion"
    assert db.query(models.HistorialEstado).filter_by(equipo_id=equipo.id).count() == 0


def test_solo_lectura_no_puede_aprobar_calibracion(client, db):
    equipo, magnitud = _crear_equipo_con_magnitud(db, "EQ-FLUJO-3")
    cal = _crear_calibracion_pendiente(db, magnitud, equipo, "CERT-003")
    _crear_usuario(db, "lector_flujo@test.com", "solo_lectura")
    _login(client, "lector_flujo@test.com")

    client.post(f"/analisis/{cal.id}/aprobar",
                data={"obs_aprobacion": "", "password": "ClaveTest123"},
                follow_redirects=False)

    db.refresh(cal)
    assert cal.resultado == "pendiente"
    assert db.query(models.FirmaElectronica).filter_by(
        tabla="calibraciones", registro_id=cal.id).count() == 0


# ── Guardia anti-reaprobación (hallazgo de PQ-7, cerrado 12-ago-2026) ─────

def test_reaprobar_una_calibracion_ya_aprobada_es_rechazada_por_http(client, db):
    """Antes de la guardia, un POST directo (o una pestaña vieja) a este
    endpoint podía re-firmar una calibración ya aprobada sin aviso, según se
    descubrió al reconciliar la evidencia de auditoría de la Fase 2.3 (ver
    docs/calidad/PLAN_PRUEBAS_CARGA.md §7). Este test cierra el gap: hasta
    ahora la guardia solo tenía cobertura vía pytest de la función de
    servicio (implícita, no un test dedicado), no del endpoint HTTP."""
    equipo, magnitud = _crear_equipo_con_magnitud(db, "EQ-FLUJO-4")
    cal = _crear_calibracion_pendiente(db, magnitud, equipo, "CERT-004")
    operador = _crear_usuario(db, "operador_flujo4@test.com", "operador")
    _login(client, "operador_flujo4@test.com")

    r1 = client.post(f"/analisis/{cal.id}/aprobar",
                      data={"obs_aprobacion": "Primera aprobación",
                            "password": "ClaveTest123"},
                      follow_redirects=False)
    assert r1.status_code == 303
    assert "error_firma" not in r1.headers.get("location", "")

    db.refresh(cal)
    primera_fecha_aprobacion = cal.fecha_aprobacion
    assert cal.resultado == "aprobado"

    # Segundo POST — misma calibración, misma sesión, contraseña correcta
    r2 = client.post(f"/analisis/{cal.id}/aprobar",
                      data={"obs_aprobacion": "Reintento", "password": "ClaveTest123"},
                      follow_redirects=False)
    assert r2.status_code == 303
    assert "error_firma=1" in r2.headers["location"], (
        "la guardia anti-reaprobación no está bloqueando el reintento por HTTP"
    )

    db.refresh(cal)
    assert cal.fecha_aprobacion == primera_fecha_aprobacion, (
        "la reaprobación sobrescribió la fecha de la primera aprobación"
    )
    # Solo una firma electrónica registrada para esta calibración, no dos
    assert db.query(models.FirmaElectronica).filter_by(
        tabla="calibraciones", registro_id=cal.id).count() == 1
