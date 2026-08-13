"""
Verificación intermedia con puntos y cierre — Fase 2.2, ítem 5
(docs/PROJECT_PLAN.md §2.2 punto 3 / docs/calidad/COBERTURA.md): ciclo
completo "plan → registro de puntos → cierre con acción correctiva", sin
ningún test antes de este archivo.

También cierra un gap señalado explícitamente en
`docs/calidad/validacion_farma/OQ_CALIFICACION_OPERACIONAL.md` (OQ-B2):
"Verificación intermedia con desviación entre umbral de alerta y umbral
fuera de tolerancia -> Resultado = alerta (amarillo) [...] Ninguna
identificada — gap de prueba automatizada".

Al construir estos tests se encontró un bug real en
`services/verificaciones_service.py::eliminar_punto` (corregido en el
mismo cambio, ver commit): a diferencia de `agregar_punto`/
`agregar_puntos_lote`, no recalculaba el campo agregado `resultado` de la
verificación tras eliminar un punto — si el punto eliminado era el único
"fuera" o "alerta", la verificación quedaba con ese resultado
indefinidamente aunque los puntos restantes estuvieran todos dentro de
tolerancia. `test_eliminar_el_unico_punto_fuera_recalcula_el_resultado`
prueba directamente el arreglo.

Segundo hallazgo, confirmado con Edison y corregido en el mismo cambio:
igual que ocurría con `POST /analisis/{cid}/aprobar` antes del hallazgo de
PQ-7 (ver `docs/calidad/PLAN_PRUEBAS_CARGA.md` §7),
`POST /verificaciones/{vid}/cerrar` no tenía guardia contra re-cierre — la
plantilla siempre muestra el formulario de cierre, sin ocultarlo cuando
`accion_tomada` ya está definido. Se agregó la misma guardia en
`services/verificaciones_service.py::cerrar_verificacion`, validada en
`test_recerrar_una_verificacion_ya_cerrada_es_rechazada_por_http`.
"""
from datetime import date

import auth
import models


def _crear_usuario(db, email, rol="operador", password="ClaveTest123"):
    u = models.Usuario(nombre=f"Usuario {rol}", email=email, rol=rol,
                        hashed_password=auth.hash_password(password))
    db.add(u)
    db.commit()
    return u


def _login(client, email, password="ClaveTest123"):
    r = client.post("/usuarios/login", data={"email": email, "password": password},
                     follow_redirects=False)
    assert r.status_code in (302, 303), f"login falló: {r.status_code} {r.text[:200]}"


def _crear_equipo_magnitud(db, codigo, emp_valor=1.0):
    eq = models.Equipo(codigo=codigo, nombre="Equipo verificación", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Presión", emp_valor=emp_valor, activa=True)
    db.add(mag); db.commit()
    return eq, mag


def _crear_plan(db, mag, eq, umbral_alerta_pct=70.0, umbral_fuera_pct=100.0):
    plan = models.PlanVerificacion(magnitud_id=mag.id, equipo_id=eq.id, frecuencia_meses=6,
                                    activo=True, umbral_alerta_pct=umbral_alerta_pct,
                                    umbral_fuera_pct=umbral_fuera_pct)
    db.add(plan); db.commit()
    return plan


def _crear_verificacion(db, plan, eq, mag):
    ver = models.VerificacionIntermedia(plan_id=plan.id, equipo_id=eq.id, magnitud_id=mag.id,
                                         fecha=date(2026, 1, 1), resultado="pendiente")
    db.add(ver); db.commit()
    return ver


# ═══════════════════════════════════════════════════════════════════════
# Camino feliz completo (plan -> nueva -> puntos -> cerrar), vía HTTP
# ═══════════════════════════════════════════════════════════════════════

def test_flujo_completo_plan_puntos_cerrar_con_puntos_dentro_de_tolerancia(client, db):
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-1")
    operador = _crear_usuario(db, "ver_flujo1@test.com")
    _login(client, "ver_flujo1@test.com")

    # 1) Plan de verificación
    r = client.post(f"/verificaciones/plan/{mag.id}",
                     data={"frecuencia_meses": "6", "activo": "true"}, follow_redirects=False)
    assert r.status_code == 302
    plan = db.query(models.PlanVerificacion).filter_by(magnitud_id=mag.id).one()
    assert plan.frecuencia_meses == 6

    # 2) Nueva verificación programada
    r = client.post(f"/verificaciones/nueva/{mag.id}", data={"fecha": "2026-02-01"},
                     follow_redirects=False)
    assert r.status_code == 302
    ver = db.query(models.VerificacionIntermedia).filter_by(plan_id=plan.id).one()
    assert ver.equipo_id == eq.id and ver.magnitud_id == mag.id

    # 3) Puntos en lote, todos dentro de tolerancia (emp=1.0 -> desv chica)
    r = client.post(f"/verificaciones/{ver.id}/puntos/lote", data={
        "valor_patron":   ["10", "20"],
        "valor_indicado": ["10.02", "20.03"],
        "tolerancia_inf": ["", ""], "tolerancia_sup": ["", ""], "observacion": ["", ""],
    }, follow_redirects=False)
    assert r.status_code == 303
    db.refresh(ver)
    assert ver.resultado == "aprobado"
    assert db.query(models.PuntoVerificacion).filter_by(
        verificacion_id=ver.id, eliminado=False).count() == 2

    # 4) Cierre con firma electrónica
    r = client.post(f"/verificaciones/{ver.id}/cerrar", data={
        "accion_tomada": "ninguna", "observaciones": "Sin novedad",
        "password": "ClaveTest123",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "error" not in r.headers.get("location", "")

    db.refresh(ver)
    assert ver.accion_tomada == "ninguna"
    assert ver.observaciones == "Sin novedad"
    firma_row = db.query(models.FirmaElectronica).filter_by(
        tabla="verificaciones_intermedias", registro_id=ver.id).one()
    assert firma_row.usuario_id == operador.id


# ═══════════════════════════════════════════════════════════════════════
# Umbrales — el gap señalado en OQ-B2
# ═══════════════════════════════════════════════════════════════════════

def test_punto_en_zona_de_alerta_marca_la_verificacion_como_alerta(client, db):
    """OQ-B2: desviación entre el umbral de alerta (70%) y el umbral fuera
    de tolerancia (100%) debe dar resultado='alerta', ni aprobado ni
    reprobado."""
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-2", emp_valor=1.0)
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_alerta@test.com")
    _login(client, "ver_alerta@test.com")

    # error=0.8, emp=1.0 -> desviación 80% (>=70 y <100 -> alerta)
    r = client.post(f"/verificaciones/{ver.id}/punto",
                     data={"valor_patron": "10", "valor_indicado": "10.8"},
                     follow_redirects=False)
    assert r.status_code == 302

    db.refresh(ver)
    assert ver.resultado == "alerta"
    punto = db.query(models.PuntoVerificacion).filter_by(verificacion_id=ver.id).one()
    assert punto.resultado == "alerta"
    assert punto.desviacion_pct == 80.0


def test_punto_fuera_de_tolerancia_marca_la_verificacion_como_reprobada(client, db):
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-3", emp_valor=1.0)
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_fuera@test.com")
    _login(client, "ver_fuera@test.com")

    # error=1.2, emp=1.0 -> desviación 120% (>=100 -> fuera)
    r = client.post(f"/verificaciones/{ver.id}/punto",
                     data={"valor_patron": "10", "valor_indicado": "11.2"},
                     follow_redirects=False)
    assert r.status_code == 302

    db.refresh(ver)
    assert ver.resultado == "reprobado"


def test_un_solo_punto_fuera_entre_varios_ok_reprueba_toda_la_verificacion(client, db):
    """recalcular_resultado_verificacion (services/verificaciones_service.py):
    basta un punto 'fuera' entre varios 'ok' para que el resultado agregado
    sea 'reprobado' — no se promedia ni se ignora por mayoría."""
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-4", emp_valor=1.0)
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_mixto@test.com")
    _login(client, "ver_mixto@test.com")

    client.post(f"/verificaciones/{ver.id}/puntos/lote", data={
        "valor_patron":   ["10", "20", "30"],
        "valor_indicado": ["10.02", "20.03", "31.2"],  # el tercero: error=1.2 -> fuera
        "tolerancia_inf": ["", "", ""], "tolerancia_sup": ["", "", ""],
        "observacion": ["", "", ""],
    }, follow_redirects=False)

    db.refresh(ver)
    assert ver.resultado == "reprobado"


# ═══════════════════════════════════════════════════════════════════════
# Eliminar punto recalcula el resultado agregado (bug corregido en este cambio)
# ═══════════════════════════════════════════════════════════════════════

def test_eliminar_el_unico_punto_fuera_recalcula_el_resultado(client, db):
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-5", emp_valor=1.0)
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_elimina@test.com")
    _login(client, "ver_elimina@test.com")

    client.post(f"/verificaciones/{ver.id}/puntos/lote", data={
        "valor_patron":   ["10", "20"],
        "valor_indicado": ["10.02", "21.2"],  # el segundo: error=1.2 -> fuera
        "tolerancia_inf": ["", ""], "tolerancia_sup": ["", ""], "observacion": ["", ""],
    }, follow_redirects=False)
    db.refresh(ver)
    assert ver.resultado == "reprobado"  # confirma el estado previo a eliminar

    punto_fuera = db.query(models.PuntoVerificacion).filter_by(
        verificacion_id=ver.id, resultado="fuera").one()

    r = client.post(f"/verificaciones/{ver.id}/punto/{punto_fuera.id}/eliminar",
                     follow_redirects=False)
    assert r.status_code == 302

    db.refresh(ver)
    assert ver.resultado == "aprobado", (
        "tras eliminar el único punto 'fuera', el resultado agregado debía "
        "recalcularse a partir de los puntos restantes (todos ok), no quedar "
        "'reprobado' de forma obsoleta"
    )


# ═══════════════════════════════════════════════════════════════════════
# Challenge test de firma electrónica en el cierre (mismo patrón OQ-A4)
# ═══════════════════════════════════════════════════════════════════════

def test_cerrar_con_password_incorrecta_no_guarda_la_accion_tomada(client, db):
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-6")
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_passmala@test.com")
    _login(client, "ver_passmala@test.com")

    r = client.post(f"/verificaciones/{ver.id}/cerrar",
                     data={"accion_tomada": "calibracion_anticipada", "password": "clave-mala"},
                     follow_redirects=False)

    assert r.status_code == 303
    assert "error_firma=1" in r.headers["location"]
    db.refresh(ver)
    assert ver.accion_tomada is None
    assert db.query(models.FirmaElectronica).filter_by(
        tabla="verificaciones_intermedias", registro_id=ver.id).count() == 0


def test_recerrar_una_verificacion_ya_cerrada_es_rechazada_por_http(client, db):
    eq, mag = _crear_equipo_magnitud(db, "EQ-VER-7")
    plan = _crear_plan(db, mag, eq)
    ver = _crear_verificacion(db, plan, eq, mag)
    _crear_usuario(db, "ver_recerrar@test.com")
    _login(client, "ver_recerrar@test.com")

    r1 = client.post(f"/verificaciones/{ver.id}/cerrar",
                      data={"accion_tomada": "ninguna", "password": "ClaveTest123"},
                      follow_redirects=False)
    assert r1.status_code == 302
    assert "error" not in r1.headers.get("location", "")

    r2 = client.post(f"/verificaciones/{ver.id}/cerrar", data={
        "accion_tomada": "calibracion_anticipada", "password": "ClaveTest123",
    }, follow_redirects=False)
    assert r2.status_code == 303
    assert "error_firma=1" in r2.headers["location"], (
        "la guardia anti-recierre no está bloqueando el reintento por HTTP"
    )

    db.refresh(ver)
    assert ver.accion_tomada == "ninguna"  # no se sobrescribió con el segundo intento
    assert db.query(models.FirmaElectronica).filter_by(
        tabla="verificaciones_intermedias", registro_id=ver.id).count() == 1
