"""
locustfile.py — Prueba de carga/concurrencia de MetroGest v2 (Fase 2.3)
=========================================================================
Ver `docs/calidad/PLAN_PRUEBAS_CARGA.md` para el diseño completo (mezcla de
tareas, riesgos identificados, criterios de aceptación).

Requisitos antes de correr esto:
  1. Una instancia de MetroGest corriendo contra una BD de prueba/staging
     (nunca la de un cliente real) — arrancada normalmente con `iniciar.bat`
     o `uvicorn main:app` apuntando a esa BD vía su propio `.env`.
  2. Esa BD ya sembrada con `python seed_carga_masiva.py` (genera también
     `usuarios_carga.json` con las credenciales que este archivo consume).
  3. La variable de entorno `CARGA_DATABASE_URL` apuntando a esa MISMA BD de
     prueba — este archivo la usa solo para LEER ids de equipos/calibraciones
     (nunca escribe por SQL directo; las escrituras pasan por HTTP como
     cualquier usuario real).

Uso:
    export CARGA_DATABASE_URL=postgresql+psycopg2://user:pass@host/metrogest_carga
    locust -f locustfile.py --host http://127.0.0.1:8000

    # Corrida de humo sugerida en el plan: 15 usuarios, 10 minutos
    locust -f locustfile.py --host http://127.0.0.1:8000 \\
        --users 15 --spawn-rate 3 --run-time 10m --headless
"""
import itertools
import json
import os
import random
import sys
import threading
from pathlib import Path

from locust import HttpUser, task, between, events

sys.path.insert(0, str(Path(__file__).parent))

# ─────────────────────────────────────────────────────────────────────────────
# Carga de pools compartidos (una sola vez, al arrancar la prueba) — ids de
# equipos/calibraciones y credenciales de los usuarios de carga. Se guardan
# en un objeto módulo-global; todos los HttpUser simulados los leen.
# ─────────────────────────────────────────────────────────────────────────────
POOL = {
    "equipo_ids": [],
    "calibracion_ids": [],
    "calibracion_ids_pendientes": [],
    "max_pagina_equipos": 1,
    "credenciales": [],
}
_credenciales_ciclo = None
_lock = threading.Lock()


def _cargar_credenciales() -> list[dict]:
    ruta = Path(os.getenv("CARGA_CREDENCIALES_JSON", "usuarios_carga.json"))
    if not ruta.exists():
        raise SystemExit(
            f"[ERROR] No se encontró {ruta}. Corre primero "
            "`python seed_carga_masiva.py` — genera este archivo con las "
            "credenciales del pool de usuarios de carga."
        )
    datos = json.loads(ruta.read_text(encoding="utf-8"))
    usuarios = datos.get("usuarios", [])
    if not usuarios:
        raise SystemExit(f"[ERROR] {ruta} no tiene usuarios. Vuelve a correr seed_carga_masiva.py.")
    return usuarios


def _cargar_pools_desde_bd() -> None:
    db_url = os.getenv("CARGA_DATABASE_URL")
    if not db_url:
        raise SystemExit(
            "[ERROR] Falta la variable de entorno CARGA_DATABASE_URL. "
            "Este archivo la necesita para leer (solo lectura) los ids de "
            "equipos/calibraciones sembrados por seed_carga_masiva.py. "
            "NUNCA se usa DATABASE_URL de la app aquí."
        )
    nombre = db_url.rsplit("/", 1)[-1].split("?")[0]
    if not any(m in nombre.lower() for m in ("test", "carga", "staging", "stg", "dev")):
        print(
            f"[ADVERTENCIA] La BD '{nombre}' no parece ser de prueba/staging por su "
            "nombre. locustfile.py solo LEE de esta BD, pero verifica que sea la "
            "correcta antes de seguir — ver PLAN_PRUEBAS_CARGA.md §5."
        )

    from sqlalchemy import create_engine, text

    engine = create_engine(db_url)
    with engine.connect() as conn:
        equipo_ids = [r[0] for r in conn.execute(
            text("SELECT id FROM equipos WHERE codigo LIKE 'CARGA-%'"))]
        cal_ids = [r[0] for r in conn.execute(
            text("SELECT c.id FROM calibraciones c JOIN equipos e ON e.id = c.equipo_id "
                 "WHERE e.codigo LIKE 'CARGA-%'"))]
        cal_pendientes = [r[0] for r in conn.execute(
            text("SELECT c.id FROM calibraciones c JOIN equipos e ON e.id = c.equipo_id "
                 "WHERE e.codigo LIKE 'CARGA-%' AND c.resultado = 'pendiente'"))]
    engine.dispose()

    if not equipo_ids:
        raise SystemExit(
            "[ERROR] No hay equipos con prefijo 'CARGA-' en esa BD. Corre "
            "`python seed_carga_masiva.py` primero."
        )

    POOL["equipo_ids"] = equipo_ids
    POOL["calibracion_ids"] = cal_ids
    POOL["calibracion_ids_pendientes"] = cal_pendientes
    POOL["max_pagina_equipos"] = max(1, -(-len(equipo_ids) // 30))  # PAGE_SIZE=30 en routers/equipos.py
    print(
        f">>> Pools cargados: {len(equipo_ids)} equipos, {len(cal_ids)} calibraciones "
        f"({len(cal_pendientes)} pendientes de aprobar)."
    )


@events.test_start.add_listener
def _al_iniciar_prueba(environment, **kwargs):
    global _credenciales_ciclo
    POOL["credenciales"] = _cargar_credenciales()
    _credenciales_ciclo = itertools.cycle(POOL["credenciales"])
    _cargar_pools_desde_bd()


def _siguiente_credencial() -> dict:
    """Reparte credenciales de forma round-robin entre los usuarios virtuales
    de Locust. Si hay más usuarios virtuales que credenciales, se repiten
    (login concurrente con la misma cuenta es válido — no hay restricción
    de sesión única en el código, ver auth.py)."""
    with _lock:
        return next(_credenciales_ciclo)


# ─────────────────────────────────────────────────────────────────────────────
# USUARIO SIMULADO
# ─────────────────────────────────────────────────────────────────────────────
class UsuarioMetroGest(HttpUser):
    # Ritmo humano entre acciones — no es un stress test de rafagas sin pausa,
    # es la mezcla "mayoría navegando" que pide PROJECT_PLAN §2.3.
    wait_time = between(2, 6)

    def on_start(self):
        cred = _siguiente_credencial()
        self.rol = cred["rol"]
        self._cred = cred  # necesaria luego para la reautenticación de firma electrónica
        with self.client.post(
            "/usuarios/login",
            data={"email": cred["email"], "password": cred["password"]},
            catch_response=True, allow_redirects=False, name="/usuarios/login",
        ) as resp:
            if resp.status_code not in (302, 303):
                resp.failure(f"login falló para {cred['email']}: {resp.status_code}")
            else:
                resp.success()

    # ── Navegación (peso alto — mayoría del tráfico) ─────────────────────────

    @task(10)
    def ver_dashboard(self):
        self.client.get("/dashboard/", name="/dashboard/")

    @task(10)
    def listar_equipos(self):
        pagina = random.randint(1, POOL["max_pagina_equipos"])
        # De vez en cuando con filtro de estado, para ejercitar esa rama del query
        params = {"page": pagina}
        if random.random() < 0.2:
            params["estado"] = random.choice(["operativo", "fuera_de_uso", "en_espera_calibracion"])
        self.client.get("/equipos/", params=params, name="/equipos/?page=[n]")

    @task(6)
    def ver_detalle_equipo(self):
        if not POOL["equipo_ids"]:
            return
        eid = random.choice(POOL["equipo_ids"])
        self.client.get(f"/equipos/{eid}", name="/equipos/[id]")

    # ── Generación de reportes (peso bajo — CPU-intensivo, ver riesgo en el plan) ──

    @task(2)
    def generar_pdf_analisis(self):
        if not POOL["calibracion_ids"]:
            return
        cid = random.choice(POOL["calibracion_ids"])
        self.client.get(f"/analisis/{cid}/pdf", name="/analisis/[id]/pdf")

    @task(1)
    def exportar_excel_dashboard(self):
        self.client.get("/dashboard/excel", name="/dashboard/excel")

    # ── Escritura (peso muy bajo — firma electrónica real) ───────────────────

    @task(1)
    def aprobar_calibracion(self):
        # Los usuarios "solo_lectura" no pueden aprobar (RBAC real, ver
        # tests/test_rbac.py) — no tiene sentido simular esa llamada con ellos.
        if self.rol == "solo_lectura" or not POOL["calibracion_ids_pendientes"]:
            return
        cid = random.choice(POOL["calibracion_ids_pendientes"])
        # LIMITACIÓN CONOCIDA (ver PLAN_PRUEBAS_CARGA.md §6): el pool de
        # calibraciones "pendiente" se agota a medida que se aprueban durante
        # la corrida — no se repone en caliente. Para corridas largas,
        # dimensionar --pct-pendiente en seed_carga_masiva.py o resembrar
        # entre corridas. Reintentar sobre una ya aprobada devuelve un 303
        # con error_firma=1 (guardia agregada en services/analisis_service.py
        # tras el hallazgo de PQ-7 — antes se re-firmaba sin aviso, ver
        # PLAN_PRUEBAS_CARGA.md §7). No rompe la prueba: Locust solo valida
        # 302/303, no distingue "aprobado" de "rechazado por ya aprobada".
        self.client.post(
            f"/analisis/{cid}/aprobar",
            data={"obs_aprobacion": "Aprobación generada por prueba de carga Fase 2.3.",
                  "password": self._cred["password"]},
            allow_redirects=False, name="/analisis/[id]/aprobar",
        )
