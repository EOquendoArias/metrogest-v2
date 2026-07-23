"""
Control de acceso por rol, a nivel HTTP real (no solo la función). Cubre
dos de los 18 endpoints que estaban desprotegidos antes de la corrección
(routers/analisis.py, routers/ilac.py): "solo_lectura" no debe poder
escribir, "operador" sí.
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


def _crear_calibracion_de_prueba(db):
    equipo = models.Equipo(codigo="EQ-RBAC-1", nombre="Equipo RBAC", estado="operativo")
    db.add(equipo); db.commit()
    magnitud = models.MagnitudEquipo(equipo_id=equipo.id, nombre="Temperatura", activa=True)
    db.add(magnitud); db.commit()
    cal = models.Calibracion(magnitud_id=magnitud.id, equipo_id=equipo.id,
                              fecha_calibracion=date(2025, 1, 1), resultado="pendiente",
                              metodo_analisis="regresion")
    db.add(cal); db.commit()
    return equipo, magnitud, cal


def test_solo_lectura_no_puede_cambiar_metodo_de_analisis(client, db):
    _, _, cal = _crear_calibracion_de_prueba(db)
    _crear_usuario(db, "solo_lectura@test.com", "solo_lectura")
    _login(client, "solo_lectura@test.com")

    client.post(f"/analisis/{cal.id}/metodo", data={"metodo": "lagrange"})

    db.refresh(cal)
    assert cal.metodo_analisis == "regresion", (
        "un usuario solo_lectura no debería poder cambiar el método de análisis"
    )


def test_operador_si_puede_cambiar_metodo_de_analisis(client, db):
    _, _, cal = _crear_calibracion_de_prueba(db)
    _crear_usuario(db, "operador@test.com", "operador")
    _login(client, "operador@test.com")

    client.post(f"/analisis/{cal.id}/metodo", data={"metodo": "lagrange"})

    db.refresh(cal)
    assert cal.metodo_analisis == "lagrange"


def test_solo_lectura_no_puede_guardar_evaluacion_de_riesgo_ilac(client, db):
    equipo = models.Equipo(codigo="EQ-RBAC-2", nombre="Equipo RBAC 2", estado="operativo")
    db.add(equipo); db.commit()
    magnitud = models.MagnitudEquipo(equipo_id=equipo.id, nombre="Masa", activa=True)
    db.add(magnitud); db.commit()

    _crear_usuario(db, "solo_lectura2@test.com", "solo_lectura")
    _login(client, "solo_lectura2@test.com")

    client.post(f"/ilac/riesgo/{magnitud.id}", data={"intervalo_adoptado_meses": "12"})

    assert db.query(models.EvaluacionRiesgo).filter_by(magnitud_id=magnitud.id).count() == 0


def test_sin_sesion_redirige_a_login(client):
    r = client.get("/dashboard/", follow_redirects=False)
    assert r.status_code in (302, 307)
    assert "/usuarios/login" in r.headers["location"]
