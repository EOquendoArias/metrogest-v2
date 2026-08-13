"""
Generación de PDF/Excel — Fase 2.2, ítem 7, último de
docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md (docs/calidad/COBERTURA.md:
"Cero cobertura de generación de PDF/Excel [...] no solo falta medir su
rendimiento (ya cubierto en la Fase 2.3), falta una red de seguridad
funcional si un cambio de datos rompe un layout fijo").

No se prueban los 14 endpoints que generan PDF/Excel uno por uno — la
mayoría comparten la misma forma (cargar datos, snapshot, llamar a un
generador de utils/pdf_*.py) y el riesgo real no es "¿existe la ruta?"
sino dos cosas concretas:

1. Los que pasan por el `ProcessPoolExecutor` compartido (ver ADR-001 en
   docs/arquitectura/DECISIONES.md) — `dashboard/pdf`, `dashboard/excel`,
   `analisis/{cid}/pdf` — porque ahí es donde vive el riesgo real de
   arquitectura (snapshot picklable, subproceso separado); si algo se
   rompe ahí, se rompe para TODOS los documentos, no solo uno.
2. Que las exportaciones del dashboard respeten el mismo gate de licencia
   que el resto de la escritura (`puede_escribir()`, ver
   `tests/test_ciclo_vida_licencia.py`) — un detalle de negocio fácil de
   pasar por alto porque técnicamente es un GET, no un POST/PUT/DELETE.

El resto de los generadores síncronos (ILAC, verificación, mantenimiento)
se cubre con un representante de cada familia, más el caso 404 cuando
falta el dato que el PDF necesita (ej. evaluación ILAC sin registrar).
"""
import json
from datetime import date

import auth
import licencia as lic
import models
import pytest


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


# ═══════════════════════════════════════════════════════════════════════
# ProcessPoolExecutor (ADR-001) — dashboard y análisis de calibración
# ═══════════════════════════════════════════════════════════════════════

def test_pdf_de_analisis_de_calibracion_se_genera_correctamente(client, db):
    eq = models.Equipo(codigo="EQ-PDF-1", nombre="Equipo PDF", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Masa", emp_valor=0.5, activa=True)
    db.add(mag); db.commit()
    cal = models.Calibracion(magnitud_id=mag.id, equipo_id=eq.id,
                              fecha_calibracion=date(2026, 1, 1), resultado="pendiente",
                              numero_certificado="CERT-PDF-1")
    db.add(cal); db.commit()
    db.add_all([
        models.PuntoCalibracion(calibracion_id=cal.id, numero_punto=1,
                                 valor_patron=10, valor_indicado=10.1, error=0.1),
        models.PuntoCalibracion(calibracion_id=cal.id, numero_punto=2,
                                 valor_patron=20, valor_indicado=20.1, error=0.1),
    ])
    db.commit()
    _crear_usuario(db, "pdf_analisis@test.com")
    _login(client, "pdf_analisis@test.com")

    r = client.get(f"/analisis/{cal.id}/pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_pdf_y_excel_de_dashboard_requieren_licencia_activa(client, db, licencia_controlada):
    """Aunque son peticiones GET (no escriben nada), dashboard.py las
    condiciona explícitamente a `puede_escribir()` — con licencia vencida
    deben redirigir al dashboard en vez de entregar el archivo. Es el
    mismo mecanismo de licencia.py cubierto en test_ciclo_vida_licencia.py,
    aplicado aquí a una exportación en vez de a una escritura de datos."""
    _escribir_licencia(licencia_controlada, vence="2020-01-01")
    _crear_usuario(db, "pdf_dashboard_vencida@test.com", "administrador")
    _login(client, "pdf_dashboard_vencida@test.com")

    r_pdf = client.get("/dashboard/pdf", follow_redirects=False)
    assert r_pdf.status_code == 307  # RedirectResponse sin status_code explícito -> 307 (Starlette)
    assert r_pdf.headers["location"] == "/dashboard/"

    r_excel = client.get("/dashboard/excel", follow_redirects=False)
    assert r_excel.status_code == 307
    assert r_excel.headers["location"] == "/dashboard/"


def test_pdf_de_dashboard_se_genera_con_licencia_activa(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2099-12-31")
    _crear_usuario(db, "pdf_dashboard_activa@test.com", "administrador")
    _login(client, "pdf_dashboard_activa@test.com")

    r = client.get("/dashboard/pdf")

    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")


def test_excel_de_dashboard_se_genera_con_licencia_activa(client, db, licencia_controlada):
    _escribir_licencia(licencia_controlada, vence="2099-12-31")
    _crear_usuario(db, "excel_dashboard_activa@test.com", "administrador")
    _login(client, "excel_dashboard_activa@test.com")

    r = client.get("/dashboard/excel")

    assert r.status_code == 200
    assert r.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    assert r.content.startswith(b"PK")  # .xlsx es un zip


# ═══════════════════════════════════════════════════════════════════════
# Generadores síncronos — un representante por familia + caso 404
# ═══════════════════════════════════════════════════════════════════════

def test_pdf_de_evaluacion_ilac_se_genera_correctamente(client, db):
    eq = models.Equipo(codigo="EQ-PDF-2", nombre="Equipo PDF ILAC", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Temperatura", activa=True)
    db.add(mag); db.commit()
    ev = models.EvaluacionRiesgo(magnitud_id=mag.id, puntuacion_total=3.0,
                                  intervalo_sugerido_meses=12, intervalo_adoptado_meses=12,
                                  fecha_evaluacion=date(2026, 1, 1))
    db.add(ev); db.commit()
    _crear_usuario(db, "pdf_ilac@test.com")
    _login(client, "pdf_ilac@test.com")

    r = client.get(f"/ilac/riesgo/{mag.id}/pdf")

    assert r.status_code == 200
    assert r.content.startswith(b"%PDF")


def test_pdf_de_evaluacion_ilac_sin_evaluacion_registrada_da_404(client, db):
    eq = models.Equipo(codigo="EQ-PDF-3", nombre="Equipo sin evaluar", estado="operativo")
    db.add(eq); db.commit()
    mag = models.MagnitudEquipo(equipo_id=eq.id, nombre="Humedad", activa=True)
    db.add(mag); db.commit()
    _crear_usuario(db, "pdf_ilac_404@test.com")
    _login(client, "pdf_ilac_404@test.com")

    r = client.get(f"/ilac/riesgo/{mag.id}/pdf")

    assert r.status_code == 404


def test_pdf_sin_sesion_redirige_a_login(client):
    r = client.get("/analisis/1/pdf", follow_redirects=False)

    assert r.status_code in (302, 307)
    assert "/usuarios/login" in r.headers["location"]
