# Arquitectura de MetroGest v2

> Entregable de la Fase 1.1 de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §1.
> Describe la arquitectura **ya validada a escala** (Línea 2 completa: 105
> tests automatizados + prueba de carga con 1,600 equipos / 15-20 usuarios,
> ver `docs/calidad/`), no solo la intención de diseño original. No duplica
> lo que ya vive en [`../../README.md`](../../README.md) (instalación,
> módulos, variables de entorno) ni en [`../../CLAUDE.md`](../../CLAUDE.md)
> (reglas de trabajo) — enlaza a ambos.

## 1. Visión general

MetroGest v2 es una aplicación monolítica de servidor: **FastAPI +
Jinja2 SSR**, sin frontend framework separado ni API pública (todavía —
ver roadmap SaaS en `README.md`). Se instala localmente en el servidor del
cliente y sirve HTML renderizado en el servidor, con algo de JavaScript
puntual en las plantillas (ej. la barra de búsqueda global, que sí consume
un endpoint JSON: `GET /busqueda/api`).

```
Navegador (HTML + JS puntual)
        │  HTTP
        ▼
┌─────────────────────────────────────────────┐
│  Uvicorn (1-N procesos, UVICORN_WORKERS)     │
│  ┌─────────────────────────────────────────┐│
│  │  FastAPI app (main.py)                  ││
│  │   pila de middlewares (§3)              ││
│  │   → routers/ (capa HTTP)                ││
│  │      → services/ (parcial) o directo    ││
│  │         → models.py (SQLAlchemy ORM)    ││
│  │      → utils/ (cálculo, PDF, email...)  ││
│  └─────────────────────────────────────────┘│
│  ProcessPoolExecutor (PDF_EXECUTOR_WORKERS)  │ ← subprocesos para PDF/Excel (ADR-001)
└─────────────────────────────────────────────┘
        │
        ▼
   PostgreSQL (producción) / SQLite (solo fallback local, database.py)
```

## 2. Capas: routers, servicios, utilidades

- **`routers/`** (16 módulos, 82 endpoints — ver `docs/calidad/COBERTURA.md`)
  es la capa HTTP: recibe el `Request`, valida sesión/rol con `auth.py`,
  parsea formularios, y hoy en la mayoría de los módulos **también contiene
  la lógica de negocio directamente** (no solo enrutamiento).
- **`services/`** es una capa nueva, **todavía parcial** — solo dos módulos
  la usan hasta ahora: `analisis_service.py` (aprobación de calibración,
  con la guardia anti-reaprobación) y `verificaciones_service.py` (cierre
  de verificación intermedia, con su propia guardia anti-recierre, y el
  recálculo de `resultado` al agregar/eliminar puntos). El resto de los
  routers no tiene equivalente en `services/` — es deuda de diseño
  reconocida, no un patrón terminado. Si se retoma este refactor, seguir el
  mismo patrón: la función de servicio recibe `db, request, u` y hace el
  chequeo de estado de negocio **antes** de llamar a
  `utils/firma_electronica.py::verificar_y_firmar` (ver ambos módulos como
  referencia).
- **`utils/`** son funciones sin estado de sesión/HTTP: cálculo puro
  (`calculos.py` — semáforo y regresión polinomial, `deriva.py`,
  `escalera.py`, `caja_negra.py`, `horas.py`, `interpolacion.py` — los 4
  métodos ILAC G24), generación de documentos (`pdf_*.py`,
  `excel_dashboard.py`), infraestructura transversal
  (`auditoria_trail.py`, `firma_electronica.py`, `validar_archivo.py`,
  `orm_snapshot.py`, `pdf_executor.py`, `email_sender.py`).

Este orden de dependencia (routers → services parcial / directo → utils →
models) es el real hoy, no un objetivo aspiracional — `ARQUITECTURA.md`
describe lo que hay, no lo que "debería" haber.

## 3. Middlewares: orden real y por qué importa

`main.py` registra los middlewares con `app.add_middleware(...)`. En
Starlette **el último registrado queda más externo** (se ejecuta primero
en la entrada de cada request, último en la salida) — es contraintuitivo y
ya causó un bug real (ver §3.2), así que vale la pena dejarlo explícito.

Orden de registro en `main.py` (de adentro hacia afuera / de más interno a
más externo en la pila real de ejecución):

| # (orden de `add_middleware`) | Middleware | Qué hace |
|---|---|---|
| 1 (más interno) | `AuditoriaContextMiddleware` | Deja el `user_id` de sesión disponible en un `ContextVar` para que `utils/auditoria_trail.py` sepa quién hizo cada cambio, sin que cada router lo pase explícitamente |
| 2 | `CabecerasSeguridadMiddleware` | Agrega cabeceras OWASP (`X-Frame-Options`, `CSP`, etc. — ver `docs/calidad/CHECKLIST_SEGURIDAD.md` B3) a toda respuesta |
| 3 | `ForzarCambioPasswordMiddleware` | Si el usuario tiene `debe_cambiar_password=True`, redirige a `/usuarios/cambiar-password-inicial` sin importar qué haya pedido |
| 4 | `SessionMiddleware` (Starlette) | Cookie de sesión firmada (`SESSION_SECRET`) — es la que le da sentido a `request.session` |
| 5 | `LicenciaMiddleware` | Gate global: sin licencia → `/sin-licencia`; licencia vencida + escritura → `/licencia-vencida`. Ver ciclo completo en `docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md` ítem 3 |
| 6 (más externo) | `RequestLoggingMiddleware` | Log de acceso (método, ruta, status, duración, usuario) a `logs/app.log`, mide el tiempo total de toda la pila |

### 3.1 Por qué `ForzarCambioPasswordMiddleware` y `AuditoriaContextMiddleware` van antes que `SessionMiddleware`

Se agregan antes a propósito: como el orden de ejecución es inverso al de
registro, esto pone a `SessionMiddleware` **más interno que ellas** — es
decir, `SessionMiddleware` corre primero, y para cuando les toca el turno a
esos dos, `request.session` ya existe y es seguro leerla.

### 3.2 El bug real que salió de este orden (referencia, ya corregido)

`RequestLoggingMiddleware`, al ser el más externo, envuelve a
`LicenciaMiddleware` — que puede cortar la cadena (redirigir a
`/sin-licencia` o `/licencia-vencida`) **antes** de que `SessionMiddleware`
llegue a tocar el request. En ese caso, `request.session` no es un
`AttributeError` sino un `AssertionError` de Starlette, y `hasattr()` no lo
atrapa. El fix real fue cambiar el chequeo a `"session" in request.scope`
— documentado con el detalle técnico completo en
`docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md` ítem 3 y cubierto por
`tests/test_ciclo_vida_licencia.py`. Se deja aquí como advertencia de
diseño: **cualquier middleware nuevo que se agregue más externo que
`SessionMiddleware` no puede asumir que `request.session` es segura de
leer** sin ese chequeo.

### 3.3 Lo que el `exception_handler` genérico NO cubre

`main.py` registra `@app.exception_handler(Exception)` para servir una
página 500 genérica sin fuga de información. Ese handler vive en la capa
de FastAPI/Starlette (`ExceptionMiddleware`), que es **más interna que
todos los middlewares personalizados de la tabla de arriba** — por lo
tanto no protege contra excepciones lanzadas dentro de esos middlewares
(fue exactamente la causa del bug de §3.2). Cualquier middleware nuevo debe
manejar sus propias excepciones explícitamente. Ver
`docs/calidad/CHECKLIST_SEGURIDAD.md` B6.

## 4. Modelo de datos

20 tablas en `models.py` (SQLAlchemy 2.0, `declarative_base`), gestionadas
por Alembic (`alembic upgrade head` — nunca a mano, ver `CLAUDE.md` §7).
Agrupadas por dominio:

**Núcleo metrológico** — `Equipo` → `MagnitudEquipo` (1-a-N: un equipo
puede tener varias magnitudes de medición) → de cada magnitud cuelgan
`Calibracion` (→ `PuntoCalibracion`), `PlanVerificacion` (→
`VerificacionIntermedia` → `PuntoVerificacion`), `EvaluacionRiesgo` y
`ConfigILAC` (1-a-1 por magnitud — el resultado de los 14 factores ILAC
G24 y el intervalo adoptado). `Equipo` además tiene `HistorialEstado`
(bitácora de cambios de estado), `Mantenimiento` y `PlanMantenimiento`.

**Identidad y seguridad** — `Usuario` (roles: administrador / operador /
solo_lectura), `IntentoLogin` / `IntentoLoginIP` (rate-limiting de login),
`FirmaElectronica` (Ley 527/1999 — reautenticación por contraseña en cada
acción crítica), `RegistroAuditoria` (bitácora automática de cambios,
poblada por listeners `before_flush`/`after_flush` en
`utils/auditoria_trail.py`, no por llamadas explícitas de cada router).

**Configuración y notificaciones** — `ConfigLaboratorio` (nombre, logo,
firmantes de PDF), `ConfigNotificaciones` y `HistorialAlertas` (qué avisos
enviar y registro de lo ya enviado).

**Patrones transversales del esquema:**

- **Soft-delete** en `PuntoCalibracion` y `PuntoVerificacion`
  (`eliminado` / `eliminado_en` / `eliminado_por_id`) — nunca `DELETE`
  físico sobre datos de calibración/verificación, por trazabilidad GxP.
- **Auditoría automática** vía listeners de SQLAlchemy, no vía código
  repetido en cada router — ver `utils/auditoria_trail.py:TABLAS_AUDITADAS`
  para la lista exacta de tablas cubiertas (incluye `firmas_electronicas`,
  no incluye `equipos`/`historial_estados`, que se audita distinto vía
  `HistorialEstado`).
- **Motor:** PostgreSQL en producción (`DATABASE_URL`), SQLite solo como
  fallback de `database.py` si esa variable no está definida — no se usa
  en instalaciones reales de cliente (`CLAUDE.md` §2). `pool_pre_ping=True`
  evita conexiones muertas tras inactividad; el `pool_size`/`max_overflow`
  de SQLAlchemy no está configurado explícitamente (quedan en su default),
  relevante si se sube `UVICORN_WORKERS` — ver ADR-001, sección
  "Consecuencias".

## 5. Generación de documentos: el patrón `ProcessPoolExecutor`

Ver **ADR-001** en [`DECISIONES.md`](DECISIONES.md) para el detalle
completo (causa raíz, alternativas descartadas, resultados medidos). En
corto: `GET /analisis/{cid}/pdf`, `GET /dashboard/pdf` y
`GET /dashboard/excel` cargan datos con la sesión de BD normal, los
convierten a un snapshot picklable (`utils/orm_snapshot.py`) y despachan la
generación real (ReportLab/openpyxl, CPU-bound) a un proceso hijo vía
`loop.run_in_executor(pool, ...)` — el pool vive en `utils/pdf_executor.py`
y se comparte entre requests. El resto de los ~11 endpoints de PDF/Excel
del sistema todavía generan el documento de forma síncrona en el proceso
principal — aplicarles el mismo patrón queda pendiente, solo se hizo donde
la prueba de carga mostró evidencia real del problema.

## 6. Qué no cubre este documento

- Instalación, arranque, variables de entorno, recuperación de contraseña
  → `README.md`.
- Reglas de trabajo para cambios en este repo (Alembic obligatorio, nunca
  hardcodear secretos, correr pytest antes de dar por bueno un cambio de
  lógica de negocio) → `CLAUDE.md` §7.
- Decisiones de diseño con su razonamiento completo → `DECISIONES.md`
  (ADR-001 es la única entrada por ahora — Postgres-vs-SQLite,
  Alembic-vs-migraciones-a-mano, firma-simple-vs-PKI y HMAC-propio-vs-
  proveedor-externo siguen sin su propio ADR).
- Evidencia de que el sistema soporta la escala objetivo (1,600 equipos /
  10-20 usuarios) → `docs/calidad/PLAN_PRUEBAS_CARGA.md`.
- Estado de la validación GxP para clientes farmacéuticos →
  `docs/calidad/validacion_farma/`.
