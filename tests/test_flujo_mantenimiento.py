"""
Mantenimiento (preventivo/correctivo) y su efecto sobre el estado del
equipo — Fase 2.2, ítem 6 (docs/PROJECT_PLAN.md §2.2, punto 4 /
docs/calidad/COBERTURA.md): "Afecta el estado del equipo vía
requiere_calibracion/afecta_medicion, sin verificación automatizada."
Antes de este archivo, ni `mantenimientos.py` ni `plan_mantenimiento.py`
tenían ningún test.

Regla de negocio confirmada leyendo `routers/mantenimientos.py::crear`
(no documentada antes en ningún sitio, así que se deja explícita aquí):
un mantenimiento con `requiere_calibracion=true` solo mueve el equipo a
"en_mantenimiento" si el equipo estaba "operativo" en ese momento — si ya
estaba en cualquier otro estado (en espera de calibración, ya en
mantenimiento, fuera de servicio, etc.), el mantenimiento se registra
igual pero el estado del equipo no cambia. `test_mantenimiento_...
_en_equipo_no_operativo_no_cambia_estado` documenta ese comportamiento
con un test, para que un cambio futuro que lo altere sea una decisión
consciente, no un efecto secundario accidental.
"""
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


def _crear_equipo(db, codigo, estado="operativo"):
    eq = models.Equipo(codigo=codigo, nombre="Equipo mantenimiento", estado=estado)
    db.add(eq)
    db.commit()
    return eq


# ═══════════════════════════════════════════════════════════════════════
# Efecto sobre el estado del equipo
# ═══════════════════════════════════════════════════════════════════════

def test_mantenimiento_que_requiere_calibracion_pone_el_equipo_en_mantenimiento(client, db):
    eq = _crear_equipo(db, "EQ-MANT-1", estado="operativo")
    operador = _crear_usuario(db, "mant_flujo1@test.com")
    _login(client, "mant_flujo1@test.com")

    r = client.post(f"/mantenimientos/equipo/{eq.id}/nuevo", data={
        "tipo": "correctivo", "origen": "interno", "titulo": "Falla de sensor",
        "requiere_calibracion": "true", "afecta_medicion": "true",
    }, follow_redirects=False)
    assert r.status_code == 302

    mant = db.query(models.Mantenimiento).filter_by(equipo_id=eq.id).one()
    assert mant.requiere_calibracion is True
    assert mant.afecta_medicion is True
    assert mant.titulo == "Falla de sensor"

    db.refresh(eq)
    assert eq.estado == "en_mantenimiento"
    hist = db.query(models.HistorialEstado).filter_by(equipo_id=eq.id).one()
    assert hist.estado_anterior == "operativo"
    assert hist.estado_nuevo == "en_mantenimiento"
    assert hist.usuario_id == operador.id
    assert "Falla de sensor" in hist.motivo


def test_mantenimiento_sin_requerir_calibracion_no_cambia_el_estado_del_equipo(client, db):
    eq = _crear_equipo(db, "EQ-MANT-2", estado="operativo")
    _crear_usuario(db, "mant_flujo2@test.com")
    _login(client, "mant_flujo2@test.com")

    r = client.post(f"/mantenimientos/equipo/{eq.id}/nuevo", data={
        "tipo": "preventivo", "origen": "interno", "titulo": "Limpieza rutinaria",
    }, follow_redirects=False)
    assert r.status_code == 302

    db.refresh(eq)
    assert eq.estado == "operativo"
    assert db.query(models.HistorialEstado).filter_by(equipo_id=eq.id).count() == 0


def test_mantenimiento_que_requiere_calibracion_en_equipo_no_operativo_no_cambia_estado(client, db):
    """Documenta el comportamiento real: la transición a 'en_mantenimiento'
    solo aplica cuando el equipo viene de 'operativo' — no de cualquier
    otro estado."""
    eq = _crear_equipo(db, "EQ-MANT-3", estado="en_espera_calibracion")
    _crear_usuario(db, "mant_flujo3@test.com")
    _login(client, "mant_flujo3@test.com")

    r = client.post(f"/mantenimientos/equipo/{eq.id}/nuevo", data={
        "tipo": "correctivo", "origen": "interno", "titulo": "Ajuste previo a calibración",
        "requiere_calibracion": "true",
    }, follow_redirects=False)
    assert r.status_code == 302

    mant = db.query(models.Mantenimiento).filter_by(equipo_id=eq.id).one()
    assert mant.requiere_calibracion is True  # se registró igual

    db.refresh(eq)
    assert eq.estado == "en_espera_calibracion"  # pero el estado no cambió
    assert db.query(models.HistorialEstado).filter_by(equipo_id=eq.id).count() == 0


# ═══════════════════════════════════════════════════════════════════════
# Plan de mantenimiento preventivo (upsert)
# ═══════════════════════════════════════════════════════════════════════

def test_plan_de_mantenimiento_se_crea_y_se_puede_actualizar_sin_duplicar(client, db):
    eq = _crear_equipo(db, "EQ-MANT-4")
    _crear_usuario(db, "mant_plan@test.com")
    _login(client, "mant_plan@test.com")

    r = client.post(f"/plan-mantenimiento/equipo/{eq.id}", data={
        "frecuencia_meses": "6", "tipo": "preventivo", "responsable": "Juan Pérez",
    }, follow_redirects=False)
    assert r.status_code == 302
    plan = db.query(models.PlanMantenimiento).filter_by(equipo_id=eq.id).one()
    assert plan.frecuencia_meses == 6

    r = client.post(f"/plan-mantenimiento/equipo/{eq.id}", data={
        "frecuencia_meses": "3", "tipo": "preventivo", "responsable": "María Gómez",
    }, follow_redirects=False)
    assert r.status_code == 302

    assert db.query(models.PlanMantenimiento).filter_by(equipo_id=eq.id).count() == 1
    db.refresh(plan)
    assert plan.frecuencia_meses == 3
    assert plan.responsable == "María Gómez"
