"""
Ciclo de vida de licencia — Fase 2.2, ítem 3 (docs/calidad/COBERTURA.md
hallazgo #5 / OQ-A6): "Ciclo de vida de licencia sin ningún test. Afecta
directamente la facturación: un bug silencioso aquí puede dejar a un
cliente pagando sin acceso, o con acceso sin haber pagado." Antes de este
archivo, ninguno de los 7 archivos de `tests/` tocaba `licencia.py` ni
`LicenciaMiddleware` (`main.py`) en absoluto.

Los 4 estados reales del sistema, según `licencia.py` + `LicenciaMiddleware`:
- **Sin licencia** (no existe `licencia.json`, o la firma HMAC no valida):
  cualquier ruta fuera de `RUTAS_LIBRES` redirige a `/sin-licencia`.
- **Vencida** (`vence` en el pasado): las lecturas (GET) siguen funcionando
  — modo solo lectura — pero cualquier escritura (POST/PUT/DELETE/PATCH)
  redirige a `/licencia-vencida` antes de llegar al router.
- **Activa**: funciona todo con normalidad.
- **"Por vencer"**: no es un estado propio del middleware — es un banner
  informativo en `dashboard.html`, visible solo para `administrador` y
  solo si quedan ≤30 días (`licencia.dias`).

Aislamiento: estos tests NUNCA tocan el `licencia.json` real del proyecto
(existe y pertenece a la instalación real de Edison — CLAUDE.md prohíbe
tocar datos reales sin necesidad). La fixture `licencia_controlada`
redirige `licencia._ARCHIVO` a un archivo temporal por test.
"""
import json

import auth
import licencia as lic
import models
import pytest


# ── Fixtures y helpers ──────────────────────────────────────────────────

@pytest.fixture()
def licencia_controlada(tmp_path, monkeypatch):
    ruta = tmp_path / "licencia_test.json"
    monkeypatch.setattr(lic, "_ARCHIVO", ruta)
    lic.invalidar_cache()
    yield ruta
    lic.invalidar_cache()


def _escribir_licencia(ruta, vence: str, modulos=None, cliente="Cliente de prueba"):
    datos = lic.generar_licencia(cliente, vence, modulos or [])
    ruta.write_text(json.dumps(datos), encoding="utf-8")
    lic.invalidar_cache()


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


# ═══════════════════════════════════════════════════════════════════════
# Bloque A — Sin licencia
# ═══════════════════════════════════════════════════════════════════════

def test_sin_licencia_redirige_rutas_protegidas(client, db, licencia_controlada):
    _crear_usuario(db, "sinlic1@test.com", "administrador")
    _login(client, "sinlic1@test.com")
    # licencia_controlada apunta a un archivo que no existe todavía -> sin_licencia() == True

    r = client.get("/equipos/", follow_redirects=False)

    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/sin-licencia"


def test_sin_licencia_responde_403_json_si_accept_json(client, db, licencia_controlada):
    _crear_usuario(db, "sinlic2@test.com", "administrador")
    _login(client, "sinlic2@test.com")

    r = client.get("/equipos/", headers={"accept": "application/json"}, follow_redirects=False)

    assert r.status_code == 403
    assert r.json()["error"] == "Sin licencia"


def test_sin_licencia_permite_llegar_a_la_pagina_de_aviso(client, db, licencia_controlada):
    """RUTAS_LIBRES incluye /sin-licencia explícitamente — si no, un usuario
    sin licencia quedaría en un bucle de redirects sin poder ver ni el
    aviso."""
    _crear_usuario(db, "sinlic3@test.com", "administrador")
    _login(client, "sinlic3@test.com")

    r = client.get("/sin-licencia", follow_redirects=False)

    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Bloque B — Licencia vencida (modo solo lectura)
# ═══════════════════════════════════════════════════════════════════════

def test_licencia_vencida_permite_lectura(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2020-01-01")
    _crear_usuario(db, "vencida1@test.com", "administrador")
    _login(client, "vencida1@test.com")

    r = client.get("/equipos/", follow_redirects=False)

    assert r.status_code == 200


def test_licencia_vencida_bloquea_escritura_y_no_crea_el_registro(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2020-01-01")
    _crear_usuario(db, "vencida2@test.com", "administrador")
    _login(client, "vencida2@test.com")

    r = client.post("/equipos/nuevo", data={"codigo": "EQ-LIC-1", "nombre": "Intento"},
                     follow_redirects=False)

    assert r.status_code in (302, 307)
    assert r.headers["location"] == "/licencia-vencida"
    assert db.query(models.Equipo).filter_by(codigo="EQ-LIC-1").count() == 0


def test_licencia_vencida_responde_403_json_en_escritura_si_accept_json(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2020-01-01")
    _crear_usuario(db, "vencida3@test.com", "administrador")
    _login(client, "vencida3@test.com")

    r = client.post("/equipos/nuevo", data={"codigo": "EQ-LIC-2", "nombre": "Intento"},
                     headers={"accept": "application/json"}, follow_redirects=False)

    assert r.status_code == 403
    assert "vencida" in r.json()["error"].lower()


def test_licencia_vencida_permite_llegar_a_la_pagina_de_aviso(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2020-01-01")
    _crear_usuario(db, "vencida4@test.com", "administrador")
    _login(client, "vencida4@test.com")

    r = client.get("/licencia-vencida", follow_redirects=False)

    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════
# Bloque C — Licencia activa (control positivo)
# ═══════════════════════════════════════════════════════════════════════

def test_licencia_activa_permite_lectura_y_escritura(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2099-12-31")
    _crear_usuario(db, "activa1@test.com", "administrador")
    _login(client, "activa1@test.com")

    r_get = client.get("/equipos/", follow_redirects=False)
    assert r_get.status_code == 200

    r_post = client.post("/equipos/nuevo", data={"codigo": "EQ-LIC-3", "nombre": "Equipo válido"},
                          follow_redirects=False)
    assert r_post.status_code == 303
    assert db.query(models.Equipo).filter_by(codigo="EQ-LIC-3").count() == 1


# ═══════════════════════════════════════════════════════════════════════
# Bloque D — Banner "por vencer" (dashboard, solo administrador, ≤30 días)
# ═══════════════════════════════════════════════════════════════════════

def test_banner_renovacion_aparece_para_administrador_con_30_dias_o_menos(client, db, licencia_controlada):
    from datetime import date, timedelta
    vence = (date.today() + timedelta(days=15)).isoformat()
    _escribir_licencia(licencia_controlada, vence=vence)
    _crear_usuario(db, "banner_admin@test.com", "administrador")
    _login(client, "banner_admin@test.com")

    r = client.get("/dashboard/")

    assert r.status_code == 200
    assert 'id="mg-lic-banner"' in r.text


def test_banner_renovacion_no_aparece_si_faltan_mas_de_30_dias(client, db, licencia_controlada):
    from datetime import date, timedelta
    vence = (date.today() + timedelta(days=90)).isoformat()
    _escribir_licencia(licencia_controlada, vence=vence)
    _crear_usuario(db, "banner_lejos@test.com", "administrador")
    _login(client, "banner_lejos@test.com")

    r = client.get("/dashboard/")

    assert r.status_code == 200
    assert 'id="mg-lic-banner"' not in r.text


def test_banner_renovacion_no_aparece_para_operador_aunque_este_por_vencer(client, db, licencia_controlada):
    """El banner de renovación es información de facturación — a propósito
    solo la ve `administrador`, no cualquier rol con acceso de escritura."""
    from datetime import date, timedelta
    vence = (date.today() + timedelta(days=5)).isoformat()
    _escribir_licencia(licencia_controlada, vence=vence)
    _crear_usuario(db, "banner_operador@test.com", "operador")
    _login(client, "banner_operador@test.com")

    r = client.get("/dashboard/")

    assert r.status_code == 200
    assert 'id="mg-lic-banner"' not in r.text


# ═══════════════════════════════════════════════════════════════════════
# Bloque E — Módulo premium (avanzado_ilac)
# ═══════════════════════════════════════════════════════════════════════

def test_modulo_avanzado_no_incluido_redirige_a_periodo_estandar(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2099-12-31", modulos=[])  # sin el módulo
    eq = models.Equipo(codigo="EQ-LIC-MOD1", nombre="Equipo", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Masa", activa=True)
    db.add(mag); db.commit()
    _crear_usuario(db, "modulo_no@test.com", "administrador")
    _login(client, "modulo_no@test.com")

    r = client.get(f"/ilac/deriva/{mag.id}", follow_redirects=False)

    assert r.status_code in (302, 307)
    assert r.headers["location"] == f"/ilac/periodo/{mag.id}"


def test_modulo_avanzado_incluido_permite_acceder(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2099-12-31", modulos=["avanzado_ilac"])
    eq = models.Equipo(codigo="EQ-LIC-MOD2", nombre="Equipo", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Masa", activa=True)
    db.add(mag); db.commit()
    _crear_usuario(db, "modulo_si@test.com", "administrador")
    _login(client, "modulo_si@test.com")

    r = client.get(f"/ilac/deriva/{mag.id}", follow_redirects=False)

    assert r.status_code == 200
