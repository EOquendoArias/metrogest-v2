"""
RBAC ampliado — Fase 2.2, ítem 2 (docs/calidad/COBERTURA.md hallazgo #2):
"RBAC solo se verificó en 2 de 82 endpoints [...] los otros 16 (y los ~30
endpoints POST adicionales) no tienen evidencia automatizada de que el
control de rol aplique ahí."

Antes de este archivo, `test_rbac.py` cubría 2 endpoints (`analisis/metodo`,
`ilac/riesgo`) y `test_flujo_aprobacion_calibracion.py` cubría
`analisis/aprobar`. Este archivo audita el resto de los 36 endpoints de
escritura reales (`@router.post`) encontrados en `routers/`.

Hallazgo positivo de la auditoría de código previa a escribir estos tests
(no esperado de antemano): a diferencia de lo que sugería el hallazgo
original de `test_rbac.py` ("18 endpoints estaban desprotegidos"), **los 36
endpoints de escritura actuales sí tienen guardia de rol en el código** —
`u.rol == "solo_lectura"` en la mayoría, o `u.rol != "administrador"` en los
que son exclusivos de administrador (usuarios, notificaciones,
config_lab). Lo que faltaba no era la guardia, sino la evidencia
automatizada de que funciona — que es lo que agrega este archivo.

Patrón de cada test: intentar la escritura con el rol que debería ser
rechazado, y confirmar que la base de datos no cambió (no solo que hubo un
redirect — cualquier código de error también redirige, así que el redirect
por sí solo no prueba nada).
"""
from datetime import date

import auth
import models


# ── Helpers compartidos ────────────────────────────────────────────────────

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


def _crear_equipo(db, codigo, estado="en_espera_calibracion"):
    eq = models.Equipo(codigo=codigo, nombre="Equipo RBAC", estado=estado)
    db.add(eq)
    db.commit()
    return eq


def _crear_magnitud(db, equipo, nombre="Magnitud RBAC", emp_valor=0.5):
    mag = models.MagnitudEquipo(equipo_id=equipo.id, nombre=nombre,
                                 emp_valor=emp_valor, activa=True)
    db.add(mag)
    db.commit()
    return mag


def _crear_plan_verificacion(db, mag, equipo):
    plan = models.PlanVerificacion(magnitud_id=mag.id, equipo_id=equipo.id,
                                    frecuencia_meses=6, activo=True)
    db.add(plan)
    db.commit()
    return plan


def _crear_verificacion(db, plan, equipo, mag):
    ver = models.VerificacionIntermedia(plan_id=plan.id, equipo_id=equipo.id,
                                         magnitud_id=mag.id, fecha=date(2026, 1, 1),
                                         resultado="pendiente")
    db.add(ver)
    db.commit()
    return ver


# ═══════════════════════════════════════════════════════════════════════
# Bloque 1 — Endpoints bloqueados para solo_lectura (RBAC "de escritura")
# ═══════════════════════════════════════════════════════════════════════

def test_solo_lectura_no_puede_crear_equipo(client, db):
    _crear_usuario(db, "eq_solo_lectura@test.com", "solo_lectura")
    _login(client, "eq_solo_lectura@test.com")

    client.post("/equipos/nuevo", data={"codigo": "EQ-RBAC-A1", "nombre": "Intento"},
                follow_redirects=False)

    assert db.query(models.Equipo).filter_by(codigo="EQ-RBAC-A1").count() == 0


def test_solo_lectura_no_puede_editar_equipo(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A2")
    _crear_usuario(db, "eq_solo_lectura2@test.com", "solo_lectura")
    _login(client, "eq_solo_lectura2@test.com")

    client.post(f"/equipos/{eq.id}/editar",
                data={"codigo": eq.codigo, "nombre": "Nombre alterado"},
                follow_redirects=False)

    db.refresh(eq)
    assert eq.nombre == "Equipo RBAC"


def test_solo_lectura_no_puede_cambiar_estado_de_equipo(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A3")
    _crear_usuario(db, "eq_solo_lectura3@test.com", "solo_lectura")
    _login(client, "eq_solo_lectura3@test.com")

    client.post(f"/equipos/{eq.id}/estado", data={"nuevo_estado": "fuera_de_servicio"},
                follow_redirects=False)

    db.refresh(eq)
    assert eq.estado == "en_espera_calibracion"


def test_solo_lectura_no_puede_crear_magnitud(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A4")
    _crear_usuario(db, "mag_solo_lectura@test.com", "solo_lectura")
    _login(client, "mag_solo_lectura@test.com")

    client.post(f"/magnitudes/equipo/{eq.id}/nueva", data={"nombre": "Intento"},
                follow_redirects=False)

    assert db.query(models.MagnitudEquipo).filter_by(equipo_id=eq.id).count() == 0


def test_solo_lectura_no_puede_editar_magnitud(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A5")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "mag_solo_lectura2@test.com", "solo_lectura")
    _login(client, "mag_solo_lectura2@test.com")

    client.post(f"/magnitudes/{mag.id}/editar", data={"nombre": "Nombre alterado"},
                follow_redirects=False)

    db.refresh(mag)
    assert mag.nombre == "Magnitud RBAC"


def test_solo_lectura_no_puede_desactivar_magnitud(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A6")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "mag_solo_lectura3@test.com", "solo_lectura")
    _login(client, "mag_solo_lectura3@test.com")

    client.post(f"/magnitudes/{mag.id}/desactivar", data={"motivo": "intento"},
                follow_redirects=False)

    db.refresh(mag)
    assert mag.activa is True


def test_solo_lectura_no_puede_registrar_calibracion(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A7")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "cal_solo_lectura@test.com", "solo_lectura")
    _login(client, "cal_solo_lectura@test.com")

    client.post(f"/calibraciones/magnitud/{mag.id}/nueva",
                data={"fecha_calibracion": "2026-01-01"}, follow_redirects=False)

    assert db.query(models.Calibracion).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_guardar_plan_de_verificacion(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A8")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "verplan_solo_lectura@test.com", "solo_lectura")
    _login(client, "verplan_solo_lectura@test.com")

    client.post(f"/verificaciones/plan/{mag.id}", data={"frecuencia_meses": "6"},
                follow_redirects=False)

    assert db.query(models.PlanVerificacion).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_crear_verificacion_intermedia(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A9")
    mag = _crear_magnitud(db, eq)
    plan = _crear_plan_verificacion(db, mag, eq)
    _crear_usuario(db, "vernueva_solo_lectura@test.com", "solo_lectura")
    _login(client, "vernueva_solo_lectura@test.com")

    client.post(f"/verificaciones/nueva/{mag.id}", data={"fecha": "2026-01-01"},
                follow_redirects=False)

    assert db.query(models.VerificacionIntermedia).filter_by(plan_id=plan.id).count() == 0


def test_solo_lectura_no_puede_agregar_punto_de_verificacion(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A10")
    mag = _crear_magnitud(db, eq)
    plan = _crear_plan_verificacion(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "verpunto_solo_lectura@test.com", "solo_lectura")
    _login(client, "verpunto_solo_lectura@test.com")

    client.post(f"/verificaciones/{ver.id}/punto",
                data={"valor_patron": "10", "valor_indicado": "10.1"},
                follow_redirects=False)

    assert db.query(models.PuntoVerificacion).filter_by(verificacion_id=ver.id).count() == 0


def test_solo_lectura_no_puede_cerrar_verificacion(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A11")
    mag = _crear_magnitud(db, eq)
    plan = _crear_plan_verificacion(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "vercerrar_solo_lectura@test.com", "solo_lectura")
    _login(client, "vercerrar_solo_lectura@test.com")

    client.post(f"/verificaciones/{ver.id}/cerrar",
                data={"accion_tomada": "ninguna", "password": "ClaveTest123"},
                follow_redirects=False)

    db.refresh(ver)
    assert ver.resultado == "pendiente"


def test_solo_lectura_no_puede_eliminar_punto_de_verificacion(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A12")
    mag = _crear_magnitud(db, eq)
    plan = _crear_plan_verificacion(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    punto = models.PuntoVerificacion(verificacion_id=ver.id, numero_punto=1, valor_patron=10)
    db.add(punto)
    db.commit()
    _crear_usuario(db, "verelim_solo_lectura@test.com", "solo_lectura")
    _login(client, "verelim_solo_lectura@test.com")

    client.post(f"/verificaciones/{ver.id}/punto/{punto.id}/eliminar", follow_redirects=False)

    db.refresh(punto)
    assert punto.eliminado is False


def test_solo_lectura_no_puede_crear_mantenimiento(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A13")
    _crear_usuario(db, "mant_solo_lectura@test.com", "solo_lectura")
    _login(client, "mant_solo_lectura@test.com")

    client.post(f"/mantenimientos/equipo/{eq.id}/nuevo",
                data={"tipo": "preventivo", "origen": "interno", "titulo": "Intento"},
                follow_redirects=False)

    assert db.query(models.Mantenimiento).filter_by(equipo_id=eq.id).count() == 0


def test_solo_lectura_no_puede_guardar_plan_de_mantenimiento(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A14")
    _crear_usuario(db, "planmant_solo_lectura@test.com", "solo_lectura")
    _login(client, "planmant_solo_lectura@test.com")

    client.post(f"/plan-mantenimiento/equipo/{eq.id}", data={"frecuencia_meses": "6"},
                follow_redirects=False)

    assert db.query(models.PlanMantenimiento).filter_by(equipo_id=eq.id).count() == 0


def test_solo_lectura_no_puede_guardar_periodo_ilac_estandar(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A15")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "ilacperiodo_solo_lectura@test.com", "solo_lectura")
    _login(client, "ilacperiodo_solo_lectura@test.com")

    client.post(f"/ilac/periodo/{mag.id}/guardar", data={"intervalo": "12"},
                follow_redirects=False)

    assert db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_aplicar_deriva_m1(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A16")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "ilacderiva_solo_lectura@test.com", "solo_lectura")
    _login(client, "ilacderiva_solo_lectura@test.com")

    client.post(f"/ilac/deriva/{mag.id}/aplicar", data={"intervalo": "12"},
                follow_redirects=False)

    assert db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_aplicar_escalera_m4(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A17")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "ilacescalera_solo_lectura@test.com", "solo_lectura")
    _login(client, "ilacescalera_solo_lectura@test.com")

    client.post(f"/ilac/escalera/{mag.id}/aplicar", data={"intervalo": "12"},
                follow_redirects=False)

    assert db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_aplicar_caja_negra_m2(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A18")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "ilaccaja_solo_lectura@test.com", "solo_lectura")
    _login(client, "ilaccaja_solo_lectura@test.com")

    client.post(f"/ilac/caja-negra/{mag.id}/aplicar", data={"intervalo": "12"},
                follow_redirects=False)

    assert db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).count() == 0


def test_solo_lectura_no_puede_aplicar_horas_de_uso_m3(client, db):
    eq = _crear_equipo(db, "EQ-RBAC-A19")
    mag = _crear_magnitud(db, eq)
    _crear_usuario(db, "ilachoras_solo_lectura@test.com", "solo_lectura")
    _login(client, "ilachoras_solo_lectura@test.com")

    client.post(f"/ilac/horas/{mag.id}/aplicar",
                data={"limite": "100", "horas_mes": "10", "intervalo": "12"},
                follow_redirects=False)

    assert db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).count() == 0


# ═══════════════════════════════════════════════════════════════════════
# Bloque 2 — Endpoints exclusivos de administrador (operador también bloqueado)
# ═══════════════════════════════════════════════════════════════════════
#
# Estos usan un criterio distinto (`rol != "administrador"`, no
# `rol == "solo_lectura"`) — un `operador` normal, que sí puede escribir en
# casi todo el resto del sistema, NO debería poder aquí. Es el caso donde
# confundir los dos criterios de RBAC sería más fácil de introducir por
# accidente, así que se prueba explícitamente con `operador`, no solo con
# `solo_lectura`.

def test_operador_no_puede_crear_usuarios(client, db):
    _crear_usuario(db, "creador_operador@test.com", "operador")
    _login(client, "creador_operador@test.com")

    client.post("/usuarios/nuevo", data={
        "nombre": "Intruso", "email": "intruso_rbac@test.com", "password": "Clave12345",
    }, follow_redirects=False)

    assert db.query(models.Usuario).filter_by(email="intruso_rbac@test.com").count() == 0


def test_operador_no_puede_cambiar_password_de_otro_usuario(client, db):
    victima = _crear_usuario(db, "victima_rbac@test.com", "operador", password="ClaveOriginal1")
    _crear_usuario(db, "atacante_operador@test.com", "operador")
    _login(client, "atacante_operador@test.com")

    client.post(f"/usuarios/{victima.id}/cambiar-password",
                data={"nueva_password": "ClaveForzada1"}, follow_redirects=False)

    db.refresh(victima)
    assert auth.verificar_password("ClaveOriginal1", victima.hashed_password)


def test_operador_no_puede_desactivar_a_otro_usuario(client, db):
    victima = _crear_usuario(db, "victima_toggle@test.com", "operador")
    _crear_usuario(db, "atacante_operador2@test.com", "operador")
    _login(client, "atacante_operador2@test.com")

    client.post(f"/usuarios/{victima.id}/toggle-activo", follow_redirects=False)

    db.refresh(victima)
    assert victima.activo is True


def test_operador_no_puede_guardar_config_de_notificaciones(client, db):
    _crear_usuario(db, "notif_operador@test.com", "operador")
    _login(client, "notif_operador@test.com")

    client.post("/notificaciones/guardar",
                data={"email_destinatario": "intruso@test.com"}, follow_redirects=False)

    cfg = db.query(models.ConfigNotificaciones).first()
    assert cfg is None or cfg.email_destinatario != "intruso@test.com"


def test_operador_no_puede_enviar_email_de_prueba(client, db):
    _crear_usuario(db, "notifprueba_operador@test.com", "operador")
    _login(client, "notifprueba_operador@test.com")

    r = client.post("/notificaciones/prueba", follow_redirects=False)

    assert r.status_code == 403


def test_operador_no_puede_guardar_configuracion_del_laboratorio(client, db):
    _crear_usuario(db, "configlab_operador@test.com", "operador")
    _login(client, "configlab_operador@test.com")

    client.post("/config-lab/guardar", data={"nombre": "Laboratorio Intruso"},
                follow_redirects=False)

    cfg = db.query(models.ConfigLaboratorio).first()
    assert cfg is None or cfg.nombre != "Laboratorio Intruso"


# ═══════════════════════════════════════════════════════════════════════
# Bloque 3 — Confirmar que administrador SÍ puede (la guardia no es
# demasiado estricta) + regla de negocio de auto-desactivación
# ═══════════════════════════════════════════════════════════════════════

def test_administrador_si_puede_crear_usuarios(client, db):
    _crear_usuario(db, "admin_creador@test.com", "administrador")
    _login(client, "admin_creador@test.com")

    client.post("/usuarios/nuevo", data={
        "nombre": "Nuevo Usuario", "email": "nuevo_valido_rbac@test.com",
        "password": "Clave12345",
    }, follow_redirects=False)

    assert db.query(models.Usuario).filter_by(email="nuevo_valido_rbac@test.com").count() == 1


def test_administrador_no_puede_desactivarse_a_si_mismo(client, db):
    """Regla de negocio distinta del RBAC: incluso un administrador válido
    no puede desactivar su propia cuenta (routers/usuarios.py línea 142) —
    evita que el único admin activo se bloquee a sí mismo por accidente."""
    admin = _crear_usuario(db, "admin_autoblock@test.com", "administrador")
    _login(client, "admin_autoblock@test.com")

    client.post(f"/usuarios/{admin.id}/toggle-activo", follow_redirects=False)

    db.refresh(admin)
    assert admin.activo is True
