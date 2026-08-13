"""
Flujo de onboarding completo — Fase 2.2, ítem 4 (docs/PROJECT_PLAN.md §2.2,
punto 2 / docs/calidad/COBERTURA.md): "equipo → magnitud → evaluación ILAC
→ calibración", el flujo de negocio insignia del sistema — es literalmente
cómo empieza la vida de cada equipo en MetroGest. Antes de este archivo,
ninguno de los 4 pasos tenía un test que los recorriera encadenados: cada
uno se probaba (si acaso) de forma aislada.

Este archivo cubre, todo vía HTTP real (`TestClient`, no funciones sueltas):
- El camino feliz completo, verificando que cada paso deja el dato
  correcto Y enlazado correctamente al siguiente (mismo equipo_id/
  magnitud_id de principio a fin) — no solo que cada POST individual
  "funciona".
- Las reglas de negocio propias del paso ILAC (§5.1 de la evaluación de
  riesgo, ver routers/ilac.py) que no tenían ningún test: bloqueo cuando
  el intervalo adoptado supera al sugerido sin justificación explícita, y
  la protección contra reediciones accidentales de una evaluación ya
  guardada (exige `confirmar_edicion=si` explícito).
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


# ═══════════════════════════════════════════════════════════════════════
# Camino feliz completo
# ═══════════════════════════════════════════════════════════════════════

def test_flujo_completo_equipo_magnitud_ilac_calibracion(client, db):
    operador = _crear_usuario(db, "onboarding1@test.com")
    _login(client, "onboarding1@test.com")

    # 1) Alta de equipo
    r = client.post("/equipos/nuevo", data={
        "codigo": "EQ-ONB-1", "nombre": "Balanza analítica", "marca": "Mettler",
        "area": "Producción",
    }, follow_redirects=False)
    assert r.status_code == 303
    eq = db.query(models.Equipo).filter_by(codigo="EQ-ONB-1").one()
    assert eq.estado == "en_espera_calibracion"
    hist_alta = db.query(models.HistorialEstado).filter_by(equipo_id=eq.id).one()
    assert hist_alta.estado_nuevo == "en_espera_calibracion"
    assert "Registro inicial" in hist_alta.motivo

    # 2) Alta de magnitud sobre ese equipo
    r = client.post(f"/magnitudes/equipo/{eq.id}/nueva", data={
        "nombre": "Masa", "unidad": "g", "emp_valor": "0.5", "emp_texto": "±0.5 g",
    }, follow_redirects=False)
    assert r.status_code == 302
    mag = db.query(models.MagnitudEquipo).filter_by(equipo_id=eq.id, nombre="Masa").one()
    assert mag.emp_valor == 0.5

    # 3) Evaluación de riesgo ILAC — todos los factores en su valor por
    # defecto (3) debe sugerir 12 meses, según utils/calculos.py (ya
    # probado en test_calculos.py como función pura; aquí se confirma que
    # el endpoint completo, con firma electrónica incluida, llega al mismo
    # resultado y lo persiste correctamente).
    r = client.post(f"/ilac/riesgo/{mag.id}", data={
        "evaluado_por": operador.nombre, "password": "ClaveTest123",
    }, follow_redirects=False)
    assert r.status_code == 302
    assert "error" not in r.headers.get("location", "")

    ev = db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).one()
    assert ev.puntuacion_total == 3.0
    assert ev.intervalo_sugerido_meses == 12
    assert ev.intervalo_adoptado_meses == 12  # sin override -> adopta el sugerido

    ci = db.query(models.ConfigILAC).filter_by(magnitud_id=mag.id).one()
    assert ci.intervalo_inicial_meses == 12
    assert ci.intervalo_actual_meses == 12

    firma_riesgo = db.query(models.FirmaElectronica).filter_by(
        tabla="magnitudes_equipo", registro_id=mag.id).one()
    assert firma_riesgo.usuario_id == operador.id

    # 4) Registro de la primera calibración sobre esa magnitud
    r = client.post(f"/calibraciones/magnitud/{mag.id}/nueva", data={
        "fecha_calibracion": "2026-01-15", "numero_certificado": "CERT-ONB-1",
        "laboratorio": "Lab Externo S.A.S.",
    }, follow_redirects=False)
    assert r.status_code == 302

    cal = db.query(models.Calibracion).filter_by(magnitud_id=mag.id).one()
    assert cal.equipo_id == eq.id  # mismo equipo de punta a punta
    assert cal.resultado == "pendiente"
    assert cal.numero_certificado == "CERT-ONB-1"
    assert cal.fecha_calibracion == date(2026, 1, 15)


# ═══════════════════════════════════════════════════════════════════════
# Reglas de negocio del paso ILAC (routers/ilac.py, §5.1)
# ═══════════════════════════════════════════════════════════════════════

def _crear_equipo_y_magnitud(db, codigo):
    eq = models.Equipo(codigo=codigo, nombre="Equipo ILAC", estado="en_espera_calibracion")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Temperatura", activa=True)
    db.add(mag); db.commit()
    return eq, mag


def test_ilac_riesgo_bloquea_adoptado_mayor_al_sugerido_sin_justificacion(client, db):
    eq, mag = _crear_equipo_y_magnitud(db, "EQ-ONB-2")
    _crear_usuario(db, "ilacbloqueo@test.com")
    _login(client, "ilacbloqueo@test.com")

    # Sugerido con factores por defecto = 12; se intenta adoptar 18 sin justificar
    r = client.post(f"/ilac/riesgo/{mag.id}", data={
        "intervalo_adoptado_meses": "18", "password": "ClaveTest123",
    }, follow_redirects=False)

    assert r.status_code == 302
    assert "error_exceso=1" in r.headers["location"]
    assert db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).count() == 0


def test_ilac_riesgo_permite_adoptado_mayor_al_sugerido_con_justificacion(client, db):
    eq, mag = _crear_equipo_y_magnitud(db, "EQ-ONB-3")
    _crear_usuario(db, "ilacjustif@test.com")
    _login(client, "ilacjustif@test.com")

    r = client.post(f"/ilac/riesgo/{mag.id}", data={
        "intervalo_adoptado_meses": "18",
        "justificacion_exceso": "Historial de estabilidad de 3 años sin desviaciones",
        "password": "ClaveTest123",
    }, follow_redirects=False)

    assert r.status_code == 302
    assert "error" not in r.headers["location"]
    ev = db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).one()
    assert ev.intervalo_adoptado_meses == 18
    assert ev.intervalo_sugerido_meses == 12


def test_ilac_riesgo_reeditar_sin_confirmar_no_sobreescribe(client, db):
    eq, mag = _crear_equipo_y_magnitud(db, "EQ-ONB-4")
    _crear_usuario(db, "ilacreedit1@test.com")
    _login(client, "ilacreedit1@test.com")

    client.post(f"/ilac/riesgo/{mag.id}",
                data={"evaluado_por": "Primer evaluador", "password": "ClaveTest123"},
                follow_redirects=False)

    r = client.post(f"/ilac/riesgo/{mag.id}",
                     data={"evaluado_por": "Segundo evaluador", "password": "ClaveTest123"},
                     follow_redirects=False)

    assert r.status_code == 302
    assert "requiere_confirmacion=1" in r.headers["location"]
    ev = db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).one()
    assert ev.evaluado_por == "Primer evaluador"


def test_ilac_riesgo_reeditar_con_confirmar_si_sobreescribe(client, db):
    eq, mag = _crear_equipo_y_magnitud(db, "EQ-ONB-5")
    _crear_usuario(db, "ilacreedit2@test.com")
    _login(client, "ilacreedit2@test.com")

    client.post(f"/ilac/riesgo/{mag.id}",
                data={"evaluado_por": "Primer evaluador", "password": "ClaveTest123"},
                follow_redirects=False)

    r = client.post(f"/ilac/riesgo/{mag.id}", data={
        "evaluado_por": "Segundo evaluador", "confirmar_edicion": "si",
        "password": "ClaveTest123",
    }, follow_redirects=False)

    assert r.status_code == 302
    assert "requiere_confirmacion" not in r.headers["location"]
    ev = db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).one()
    assert ev.evaluado_por == "Segundo evaluador"
    # Sigue existiendo una sola fila — no se duplicó
    assert db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=mag.id).count() == 1
