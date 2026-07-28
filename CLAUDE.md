# CLAUDE.md — Memoria de trabajo del proyecto MetroGest v2

> Este archivo se carga automáticamente en cada sesión de Claude/Cowork que trabaje
> en esta carpeta. Su función es evitar que cada sesión tenga que redescubrir el
> estado real del proyecto desde cero. Mantenerlo actualizado es parte del trabajo,
> no un extra — si algo cambia (stack, reglas, estado de seguridad), actualízalo
> en el mismo cambio que lo provoca.

## 1. Qué es MetroGest v2

Aplicación web (FastAPI + SQLAlchemy + Jinja2) para gestión metrológica de
laboratorios: inventario de equipos de medición, calibraciones, verificaciones
intermedias, mantenimientos y evaluación de riesgo conforme a **ISO/IEC
10012:2003** e **ILAC G24:2017**. Se instala en el equipo del cliente (modelo
actual) y se cobra por licencia de suscripción anual (`licencia.json`,
firmada con HMAC-SHA256).

**Objetivo de capacidad declarado por el cliente/negocio:** ~1,600 equipos y
10-20 usuarios concurrentes por instalación. Este número es la vara con la
que se debe medir cualquier decisión de arquitectura, índice de base de
datos, o prueba de carga a partir de ahora — ver `docs/PROJECT_PLAN.md`.

Ya hubo una primera demo con un cliente (feedback positivo). La migración a
PostgreSQL y el endurecimiento de seguridad (ver §5) se hicieron *después*
de esa demo, al caer en cuenta de que SQLite + credenciales hardcodeadas no
alcanzaban para la escala objetivo ni para producción real.

**Los clientes objetivo incluyen industria farmacéutica.** Eso implica que
además de "funcionar bien" hay que poder mostrar evidencia documentada de
validación de sistemas computarizados (CSV) bajo un marco regulatorio de
integridad de datos — ver `docs/calidad/validacion_farma/` (Plan Maestro
de Validación, gap analysis regulatorio contra el código real, protocolos
formales IQ/OQ/PQ). No trates esto como un "nice to have" de documentación:
para este segmento de cliente es tan importante como que el cálculo del
semáforo de calibración sea correcto.

## 2. Stack real (no confundir con `GUIA_PROYECTO.md`, ver §6)

| Capa | Tecnología |
|---|---|
| Backend | FastAPI + Uvicorn (ASGI) |
| ORM / migraciones | SQLAlchemy 2.0 + **Alembic** |
| Base de datos | **PostgreSQL** (producción). SQLite solo como fallback de `database.py` si no hay `DATABASE_URL` — no se usa en la instalación real del cliente. |
| Plantillas | Jinja2 (SSR, sin frontend framework) |
| Auth | passlib/bcrypt + sesiones Starlette (`itsdangerous`) |
| Licencias | HMAC-SHA256 propio (`licencia.py`), secreto ofuscado en base64 |
| PDF / Excel | ReportLab / openpyxl |
| Cálculo / gráficas | NumPy, Matplotlib |
| Runtime | Python 3.10+ (este deployment corre en 3.14.6) |
| Arranque Windows | `iniciar.bat` (crea venv, instala deps, corre `alembic upgrade head`, lanza Uvicorn) |
| Tests | pytest + `httpx`, contra una BD Postgres de prueba real (no mocks) — ver §4 |
| CI | GitHub Actions (`.github/workflows/tests.yml`), levanta Postgres como servicio y corre `pytest tests/ -v` en cada push/PR |
| Repo | `github.com/EOquendoArias/metrogest-v2` (rama `main`) |

## 3. Estructura del repo

La estructura de carpetas y el detalle de instalación/variables de entorno
están documentados en **`README.md`** — no lo dupliques aquí, mantenlo como
la fuente de verdad operativa (cómo instalar, arrancar, recuperar
contraseña, hacer backup).

Puntos que no están en el README y conviene recordar:
- `services/` — capa de servicios nueva (piloto en `analisis_service.py` y
  `verificaciones_service.py`), para sacar lógica de negocio de los routers.
  Todavía no todos los módulos la usan.
- `utils/auditoria_trail.py` — engancha `before_flush`/`after_flush` de
  SQLAlchemy para registrar automáticamente en `registro_auditoria` quién
  cambió qué campo, sin que cada router tenga que llamarlo explícitamente.
- `utils/firma_electronica.py` — firma electrónica simple (Ley 527/1999 CO):
  exige reautenticación con contraseña en el momento de firmar. Se usa en 4
  puntos críticos del flujo metrológico (aprobar calibración, cerrar
  verificación, etc.).
- `tests/conftest.py` — cada test corre en una transacción que se revierte
  al final (savepoints anidados), contra una BD Postgres de prueba separada
  (`..._test`), nunca contra la BD real.

## 4. Cómo correr pruebas y migraciones

```bash
# Migraciones (siempre así — nunca editar el esquema a mano salvo emergencia
# documentada, ver §7):
alembic upgrade head          # aplicar
alembic revision --autogenerate -m "descripcion"   # generar nueva migración

# Tests (requieren una BD Postgres de prueba; ver tests/conftest.py para
# cómo se resuelve TEST_DATABASE_URL / DATABASE_URL + "_test"):
pip install -r requirements-dev.txt
pytest tests/ -v
```

La CI de GitHub Actions ya corre esto en cada push — si vas a proponer un
cambio de lógica de negocio o cálculo metrológico, correlo localmente antes
de dar el cambio por bueno.

## 5. Estado de seguridad (ya resuelto — no repetir advertencias viejas)

`MetroGest_Brief_Seguridad_Licencias.md` (17-jun-2026) documentó 6 brechas
críticas. **Las 6 ya están implementadas**, según confirma el código actual
y el historial de commits (`P2:`, `P3:` en `git log`):

- ✅ Middleware de licencia conectado (`LicenciaMiddleware` en `main.py`)
- ✅ Fallbacks "fail secure" en `auth.puede_escribir()` / `get_licencia_info()`
- ✅ `SESSION_SECRET` viene de `.env` (falla al arrancar si no está configurado)
- ✅ `_SECRETO` de licencias ofuscado en `licencia.py`
- ✅ `MASTER_KEY` **eliminado** por completo (commit `741d418`) — la
  recuperación de acceso ahora es `resetear_password_admin.py`, que exige
  acceso directo al servidor, no una clave que cualquiera pueda usar desde
  el login
- ✅ Contraseña de admin inicial es aleatoria (`generar_password_temporal`) y
  fuerza cambio en el primer login (`debe_cambiar_password`)

Encima de eso, ya se agregó (fuera del brief original, ver `git log`):
rate-limiting de login por (email+ip) y por ip global, cabeceras de
seguridad HTTP, validación de archivos subidos, servir archivos protegidos
con auth, página 500 genérica, rastro de auditoría automático, soft-delete
en puntos de calibración/verificación, firma electrónica, backups
automáticos de Postgres con restauración probada, logging estructurado.

**Si vas a auditar seguridad de nuevo, parte de este estado — no repitas
brechas ya cerradas.** Lo que sigue pendiente de verificar a la escala
objetivo (1,600 equipos / 10-20 usuarios) está en `docs/PROJECT_PLAN.md`.

## 6. Documentos existentes — cuáles son históricos y cuáles vivos

| Documento | Estado | Uso |
|---|---|---|
| `README.md` | **Vivo** | Instalación, arranque, variables de entorno, recuperación de contraseña. Mantenerlo actualizado con cada cambio operativo. |
| `GUIA_PROYECTO.md` (14-may-2026) | **Desactualizado / histórico** | Describe una versión anterior (SQLite, `admin123`, sin Alembic, sin tests, sin auditoría/firma electrónica). Útil como referencia de intención de diseño original, pero **no confiar en sus datos técnicos** — están superados por el código actual y por este archivo. Pendiente decidir si se reescribe o se retira (ver Fase 2 de `docs/PROJECT_PLAN.md`). |
| `MetroGest_Brief_Seguridad_Licencias.md` (17-jun-2026) | **Histórico (implementado)** | Plan de hardening de seguridad — las 6 brechas que describe ya se cerraron (§5). Consérvalo como registro de auditoría, no como pendiente. |
| `docs/PROJECT_PLAN.md` | **Vivo** | Roadmap maestro: documentación técnica, plan de calidad/pruebas de carga, documentación para clientes. Ver §7. |
| `CLAUDE.md` (este archivo) | **Vivo** | Reglas y contexto de trabajo para cualquier sesión de Claude en este repo. |

## 7. Reglas de trabajo para Claude en este proyecto

1. **Nunca hardcodear secretos, contraseñas ni claves.** Todo va en `.env`
   (que nunca se sube a git — verificar `.gitignore` si tienes dudas).
2. **Todo cambio de esquema de BD pasa por Alembic.** No editar
   `metrogest.db` ni la BD de Postgres a mano salvo emergencia justificada y
   documentada en el commit/chat (como ocurrió una vez al reparar un backup
   restaurado con un esquema desincronizado — fue la excepción, no la
   regla).
3. **Nunca ejecutar `DROP TABLE`, `DELETE` masivo, ni ninguna operación
   destructiva sobre datos reales sin aprobación explícita del usuario en el
   chat**, incluso si parece la solución más rápida a un problema de
   esquema. Preferir siempre `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`,
   scripts envueltos en transacción, o pedirle al usuario que lo ejecute él
   mismo si hay duda.
4. **Correr `pytest tests/ -v` antes de dar por bueno un cambio en lógica de
   negocio o cálculo metrológico** (regresión, semáforo, ILAC, etc.).
5. **Mensajes de commit cortos, en español, con prefijo de fase cuando
   aplique** (`P1:`, `P2:`, `P3:` — ver `git log` para el patrón ya
   establecido).
6. **El objetivo de escala (1,600 equipos / 10-20 usuarios concurrentes) es
   el criterio de aceptación** para cualquier cambio de arquitectura,
   índice, paginación o caché — no optimizar a ciegas ni ignorar la escala
   real.
7. **Actualizar `README.md` y este archivo cuando el cambio lo amerite** —
   no dejar que la documentación se desincronice del código otra vez (eso
   es justamente lo que le pasó a `GUIA_PROYECTO.md`).
8. Antes de trabajar en Windows con `.bat`/terminal vía computer-use: las
   ventanas de terminal en este entorno solo permiten clic, no escritura —
   los cambios de código van por edición de archivos + relanzar `iniciar.bat`
   por doble clic, no por escribir comandos en una consola abierta.

## 8. Dónde seguir

El plan de trabajo completo (documentación técnica, plan de calidad y
pruebas de carga, documentación para presentar a clientes) vive en
**`docs/PROJECT_PLAN.md`**. Ese documento tiene las fases, y cada fase
apunta a la carpeta de `docs/` donde debe quedar el resultado.
