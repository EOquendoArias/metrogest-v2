# Plan de Pruebas de Carga y Concurrencia (Fase 2.3)

> Entregable crítico de la Línea 2 (`../PROJECT_PLAN.md` §2.3): responde con
> evidencia, no con intuición, si MetroGest v2 soporta el objetivo de negocio
> de ~1,600 equipos y 10-20 usuarios concurrentes. Este documento alimenta
> directamente `validacion_farma/PQ_CALIFICACION_DESEMPENO.md` — el PQ es el
> empaque formal de estos mismos resultados como evidencia de validación,
> no un trabajo aparte.

**Estado de este documento:** cubre las secciones 1-7 (decisión de
herramienta, revisión del dataset existente, diseño del dataset a escala,
escenarios, riesgos, y ya la corrida de humo con resultados reales). La
sección 8 (criterios de aceptación numéricos y corrida completa) queda
pendiente de decidir con Edison — no se fija ningún número a ciegas.

## 1. Decisión de herramienta: Locust

| Criterio | Locust | k6 |
|---|---|---|
| Lenguaje de los scripts | Python (mismo stack que el proyecto: `pytest`, `httpx`, `SQLAlchemy`) | JavaScript |
| Modelar mezcla de comportamiento realista (navegación vs. escritura, por rol) | Nativo — clases `HttpUser` con `@task(peso)`, fácil de leer para quien mantiene el resto del repo en Python | Posible, pero con sintaxis de `scenarios`/`options` más rígida |
| Reautenticación con contraseña (firma electrónica) dentro de una tarea | Trivial — es solo una función Python que hace login, guarda cookie de sesión, y luego hace el POST de aprobación | Igual de posible, pero sin poder reutilizar nada de `auth.py`/`utils/firma_electronica.py` como referencia |
| Instalación | `pip install locust` (ya usamos `pip`/`requirements-dev.txt` para todo lo demás) | Binario Go aparte, otro gestor de dependencias en el proyecto |
| Overhead por usuario virtual / throughput máximo por core | Mayor overhead que k6 (procesos/greenlets Python) | Mucho más eficiente (Go), pensado para decenas de miles de VUs |
| Relevancia de esa diferencia a *nuestra* escala (10-20 usuarios concurrentes) | Ninguna — Locust satura 10-20 VUs sin esfuerzo, la diferencia de throughput por core solo importa en pruebas de miles de VUs | — |
| Reporte / UI en vivo | Web UI incluida (`locust -f locustfile.py`), útil para ver la prueba correr en tiempo real durante una demo | Requiere Grafana/InfluxDB aparte para lo mismo |

**Decisión:** Locust. La única ventaja real de k6 (throughput masivo por core) no
aplica al objetivo de negocio (10-20 usuarios), y Locust encaja directamente en
el stack Python del proyecto — quien mantenga MetroGest puede leer y modificar
`locustfile.py` sin aprender un lenguaje ni un runtime nuevo. Se deja registrado
como alternativa si en el futuro el objetivo de escala cambia a cientos/miles de
usuarios concurrentes (no es el caso hoy).

Dependencia agregada a `requirements-dev.txt`: `locust`.

## 2. Revisión de `seed_demo_data.py` como base

`seed_demo_data.py` (ya existe en el repo, 25 equipos EQ-002…EQ-025) **no sirve
tal cual** para generar 1,600 equipos, pero **sí aporta piezas reutilizables**:

| Parte de `seed_demo_data.py` | ¿Reutilizable para carga a escala? | Motivo |
|---|---|---|
| Definición de los 25 equipos (`EQUIPOS`, `PESAS_E2`, `EQUIPOS_EXTRA`) como diccionarios escritos a mano | No | Es precisamente un dataset *curado* para demo (nombres, marcas, ubicaciones reales) — no está parametrizado por cantidad, y escribir 1,600 diccionarios a mano no es el objetivo. |
| `generar_puntos_calibracion(mag)` / `generar_puntos_verificacion(mag)` (cálculo de error dentro de EMP, tolerancias, `dentro_tolerancia`) | Sí, como referencia de diseño | La lógica de generar puntos realistas (error aleatorio acotado al EMP, incertidumbre, etc.) es correcta y ya está probada contra el esquema real. Se reimplementa en el nuevo script en vez de importar el módulo (ver nota de seguridad abajo), pero replicando el mismo criterio. |
| Patrón de creación por equipo (Equipo → HistorialEstado → MagnitudEquipo → Calibraciones → Puntos → EvaluacionRiesgo → ConfigILAC → PlanVerificacion → Verificaciones → Puntos → PlanMantenimiento → Mantenimientos) | Sí | Es el árbol de objetos correcto según `models.py`; se conserva el mismo orden de creación (usa `db.flush()` para obtener IDs antes de crear hijos). |
| Idempotencia por código (`if Equipo.codigo == ... : skip`) | Sí, con ajuste | A 1,600 equipos, una consulta `SELECT` por código sería lenta y, sobre todo, no es el patrón correcto para una fixture de carga: la fixture de carga se trata como *desechable* (se recrea la BD de prueba en vez de rellenarla incrementalmente). Ver §4. |
| `Base.metadata.create_all(bind=engine)` en el nivel superior del módulo | No, deliberadamente | Correcto para un script de demo sobre una instalación nueva. Para la BD de carga, el esquema debe llegar por `alembic upgrade head` (regla §7.2 de `CLAUDE.md`) — el script de carga verifica que las tablas ya existan y falla con un mensaje claro si no, en vez de crear esquema por su cuenta. |
| Requiere que ya exista un usuario `administrador` (creado por la app en su primer arranque) | Sí, mismo requisito | Se mantiene: correr la app una vez contra la BD de carga (o usar `resetear_password_admin.py`/lifespan) antes de sembrar. |
| Usa el motor/engine de `database.py` (que apunta a `DATABASE_URL` del `.env` real de la instalación) | **No — riesgo de seguridad** | Esto es aceptable para un script de demo que se corre a propósito contra la instalación de demo. Para 1,600 equipos sintéticos NUNCA se debe correr contra `DATABASE_URL` del `.env` de un cliente. El nuevo script exige una URL explícita (ver §5). |

**Conclusión:** no se extiende `seed_demo_data.py` in situ (mezclar "25 equipos
de demo curados por nombre" con "1,600 equipos sintéticos por lote" en el mismo
archivo generaría confusión sobre cuál usar en qué contexto). Se crea un script
nuevo, `seed_carga_masiva.py`, que reutiliza el *criterio* de generación de
puntos de `seed_demo_data.py` pero está diseñado desde cero para volumen y para
nunca apuntar por accidente a una base real.

## 3. Diseño del dataset sintético (~1,600 equipos)

Distribución de `estado` (basada en los 4 estados válidos que ya usa el código:
`operativo`, `en_espera_calibracion`, `fuera_de_uso`, `dado_de_baja`), pensada
para ejercitar los mismos filtros que usa `equipos.lista` (`?estado=`, `?cal=`)
a escala real:

| Estado | % aprox. | Calibraciones/verificaciones generadas |
|---|---|---|
| `operativo` | 75% | Historial completo (ver abajo) |
| `fuera_de_uso` (calibración vencida) | 10% | Historial completo, pero `proxima_calibracion` en el pasado (misma técnica que `EQ-006`/`EQ-024` de la demo) |
| `en_espera_calibracion` | 10% | Sin calibraciones (equipo "nuevo", como `EQ-025`) |
| `dado_de_baja` | 5% | Historial completo pero congelado (no se generan mantenimientos posteriores a la baja) |

Magnitudes por equipo (según PROJECT_PLAN §2.3, "cada uno con 1-3
magnitudes"): 60% con 1 magnitud, 30% con 2, 10% con 3 — usando una paleta de
~12 plantillas de magnitud (masa, longitud, tensión DC, presión, humedad
relativa, tiempo, ángulo, volumen, pH, iluminancia, velocidad de aire, par de
torsión — las mismas familias que ya usa `seed_demo_data.py`, generalizadas
para no depender de nombres especiales en el código sino de un campo
`emp_modo` (`"absoluto"` o `"relativo_lectura"`) por plantilla).

Profundidad de historial por magnitud con calibraciones:
- **Calibraciones:** 3-5 por magnitud (aleatorio), espaciadas ~12 meses, cada
  una con 5 puntos (`generar_puntos_calibracion`) → **puntos_calibracion**.
- **Verificaciones intermedias:** 2-6 por magnitud, espaciadas ~3 meses, cada
  una con 3 puntos (`generar_puntos_verificacion`) → **puntos_verificacion**.

Con ~1,600 equipos × ~1.5 magnitudes promedio ≈ 2,400 magnitudes con historial,
esto da aproximadamente:

| Tabla | Filas estimadas |
|---|---|
| `equipos` | 1,600 |
| `magnitudes_equipo` | ~2,400 |
| `calibraciones` | ~9,600 (2,400 × 4 promedio) |
| `puntos_calibracion` | ~48,000 (× 5 puntos) |
| `verificaciones_intermedias` | ~9,600 (2,400 × 4 promedio) |
| `puntos_verificacion` | ~28,800 (× 3 puntos) |
| `mantenimientos` | ~3,200 (2 por equipo con historial) |

Calibraciones + verificaciones combinadas ≈ 19,200 filas — dentro del rango
15,000-30,000 filas que pide PROJECT_PLAN §2.3, y los puntos multiplican eso
varias veces, como también pide ese documento.

**Usuarios de prueba:** el script también crea un pool de usuarios (por
defecto 20, uno por usuario concurrente objetivo) con contraseña conocida
(solo en la BD de carga) y mezcla de roles: 70% `operador`, 20%
`solo_lectura`, 10% `administrador` — para que Locust simule sesiones
concurrentes reales en vez de un solo usuario reusado 20 veces (lo cual no
ejercitaría nada del rate-limiting por email+ip de forma realista y
subestimaría la contención de la BD, que sí depende de conexiones/sesiones
distintas).

**Calibraciones "pendientes":** ~3% de las calibraciones más recientes se
dejan en `resultado="pendiente"` (en vez de `"aprobado"`) específicamente para
alimentar la tarea de escritura del load test (aprobar calibración con firma
electrónica). Ver limitación en §6.

## 4. Por qué la fixture de carga es "desechable" y no idempotente por fila

A diferencia de `seed_demo_data.py` (pensado para un entorno de demo
persistente que se puebla una vez y se conserva), la fixture de 1,600 equipos
es puramente instrumental: se genera, se usa para una corrida de prueba, y se
descarta. Por eso `seed_carga_masiva.py`:

- No hace una consulta `SELECT` por cada uno de los 1,600 códigos para decidir
  si ya existe (sería lento y no aporta nada aquí).
- En vez de eso, verifica cuántos equipos con prefijo `CARGA-` ya existen: si
  hay alguno, se detiene y le pide al usuario decidir explícitamente si quiere
  truncar las tablas de esa BD de prueba (nunca lo hace solo) o usar otra BD.
- El flujo recomendado normal es: `dropdb`/recrear la BD de prueba →
  `alembic upgrade head` → `seed_carga_masiva.py` → correr Locust → descartar
  la BD (o dejarla para la siguiente corrida y repetir desde cero).

## 5. Reglas de seguridad (no negociables)

Mismo principio que ya sigue `tests/conftest.py` y que exige PROJECT_PLAN §2.3
("nunca contra la base de datos real de un cliente"):

1. `seed_carga_masiva.py` **no** usa `database.py`/`DATABASE_URL` del `.env`
   de la instalación. Exige una URL explícita vía `--database-url` o la
   variable de entorno `CARGA_DATABASE_URL`, separada de la app real.
2. Si el nombre de la base de datos resuelta no contiene ninguno de
   `test`/`carga`/`staging`/`stg`, el script se niega a continuar salvo que se
   pase `--confirmo-que-no-es-produccion` **y** se escriba `SI` de forma
   interactiva — dos pasos deliberados para que sea imposible ejecutarlo por
   error de copiar/pegar contra la URL equivocada.
3. El script solo hace `INSERT` (nunca `DROP`/`DELETE`/`TRUNCATE`) — cualquier
   limpieza de la BD de carga la decide y ejecuta el usuario, no el script
   (regla §7.3 de `CLAUDE.md`).
4. `locustfile.py` sigue la misma regla: la URL de base de datos que usa para
   leer IDs de equipos/calibraciones (lectura, no escritura) para las tareas
   de Locust se toma de la misma variable `CARGA_DATABASE_URL`, nunca de
   `DATABASE_URL`.
5. La prueba de carga en sí apunta por HTTP a una instancia de MetroGest
   levantada contra esa misma BD de carga/staging — nunca contra la URL de
   producción de un cliente.

## 6. Riesgos de arquitectura identificados al revisar el código real

Estos son puntos concretos del código actual (no genéricos) que la prueba de
carga debe verificar con evidencia, no dar por hecho:

- **Un solo proceso Uvicorn, un solo worker** (`iniciar.bat`: `uvicorn
  main:app --host 127.0.0.1 --port 8000`, sin `--workers`). Todo el trabajo
  CPU-intensivo (ReportLab en `utils/pdf_analisis.py`, `openpyxl` en el export
  del dashboard, NumPy/Matplotlib si aplica) compite por el mismo proceso y el
  mismo GIL. Con 10-20 usuarios concurrentes, varias generaciones de PDF
  simultáneas son el escenario más probable de degradar el tiempo de
  respuesta de *todos* los demás usuarios, no solo de quien pide el PDF.
- **Caché en proceso del dashboard** (`routers/dashboard.py`,
  `CACHE_TTL_SEGUNDOS = 60`): la prueba debe medir tanto el caso "caché fría"
  (primera carga tras expirar, con 1,600 equipos reales) como "caché tibia"
  (requests dentro de la ventana de 60s) — medir solo el segundo caso
  daría una cifra optimista que no representa el peor caso real.
- **Filtrado de `equipos.lista`:** el filtro de texto/estado se hace en SQL,
  pero el filtro por categoría de calibración (`?cal=`) se aplica *después*,
  en Python, sobre la lista de IDs ya filtrada (`routers/equipos.py`, función
  `_categoria_cal`). A 1,600 equipos esto es una lista de hasta 1,600 IDs
  recorrida en Python por request — no debería ser un problema, pero es
  exactamente el tipo de suposición que esta prueba existe para confirmar en
  vez de asumir.
- **`PAGE_SIZE = 30`**: con 1,600 equipos son ~54 páginas. La prueba debe
  incluir tanto páginas tempranas como la última página (el caso con el
  slicing más profundo sobre `ids_candidatos`).
- **Firma electrónica reautentica con contraseña** (`utils/firma_electronica.py`):
  la tarea de escritura del load test debe enviar la contraseña real del
  usuario de prueba en cada `POST /analisis/{id}/aprobar` — no se puede
  simular sin credenciales válidas, así que el pool de usuarios de carga
  (§3) es un prerrequisito, no un detalle secundario.

## 7. Escenarios de carga — corrida de humo ejecutada (12-ago-2026)

Mezcla de tareas en `locustfile.py`, ponderada según "mayoría navegando,
minoría escribiendo" (PROJECT_PLAN §2.3):

| Tarea | Peso relativo | Ruta real |
|---|---|---|
| Ver dashboard | 10 | `GET /dashboard/` |
| Listar equipos (página aleatoria, a veces con filtro) | 10 | `GET /equipos/?page=N` |
| Ver detalle de un equipo | 6 | `GET /equipos/{id}` |
| Generar PDF de análisis | 2 | `GET /analisis/{cid}/pdf` |
| Exportar Excel del dashboard | 1 | `GET /dashboard/excel` |
| Aprobar calibración (firma electrónica) | 1 | `POST /analisis/{cid}/aprobar` |

Duración y número de usuarios concurrentes a definir junto con los criterios
de aceptación (§8) antes de la primera corrida — se sugiere empezar con 15
usuarios concurrentes durante 10 minutos como corrida de humo, y luego una
corrida de 20-30 minutos para observar comportamiento sostenido (fugas de
memoria, agotamiento del pool de calibraciones pendientes, etc.).

### Resultado de la corrida de humo (15 usuarios, 10 min, 12-ago-2026)

1,263 peticiones totales, 7 fallidas (0.55%):

| Endpoint | Promedio | Mediana | Máximo | Fallos |
|---|---|---|---|---|
| `GET /dashboard/` | 500 ms | 60 ms | 11.5 s | 3 |
| `GET /equipos/?page=N` | 489 ms | 110 ms | 8.4 s | 2 |
| `GET /equipos/{id}` | 448 ms | 97 ms | 7.5 s | 0 |
| `POST /usuarios/login` | 2.0 s | 2.2 s | 3.4 s | 0 |
| `POST /analisis/{id}/aprobar` | 850 ms | 430 ms | 5.1 s | 1 |
| `GET /analisis/{id}/pdf` | **18.7 s** | 12.0 s | **80.1 s** | 1 |
| `GET /dashboard/excel` | **53.2 s** | 49.0 s | **89.4 s** | 0 |

Errores observados (todos de conexión, no de lógica de negocio):
`ConnectionResetError` en `/analisis/{id}/pdf` (×1) y en
`/analisis/{id}/aprobar` (×1); `RemoteDisconnected` en `/equipos/?page=N`
(×2) y en `/dashboard/` (×3).

**Interpretación — confirma el riesgo #1 de §6, no es un hallazgo nuevo:**
la generación de PDF/Excel es el cuello de botella dominante, y al ser
síncrona en el único worker de Uvicorn, no solo es lenta en sí misma
(53-89s en el caso de Excel) sino que **bloquea a los demás usuarios
mientras corre** — de ahí las desconexiones en endpoints no relacionados
(`/dashboard/`, `/equipos/`) e incluso en la aprobación de calibración, el
evento de negocio más crítico del sistema. Con solo 15 usuarios y PDF/Excel
pesando apenas 3 de 30 en la mezcla de tareas, el problema ya es visible;
a 20 usuarios con más peso de escritura es razonable esperar que empeore,
no que se estabilice. `POST /usuarios/login` en ~2s promedio también
merece revisión aparte (no debería depender de la contención del worker
para un solo hash de bcrypt).

**Antes de la corrida completa (20-30 min):** vale la pena decidir con
Edison si se corrige el problema de raíz primero (mover generación de
PDF/Excel a un worker en segundo plano, o correr Uvicorn con más de un
worker) o si se corre igual la prueba larga para confirmar que el problema
es estable y no un artefacto de la corrida corta.

**Decidido con Edison (12-ago-2026):** se corrige primero (`B2 +
ProcessPoolExecutor` + arreglo del recorrido duplicado + `A`/`--workers`
opcional) — ver `docs/arquitectura/DECISIONES.md` ADR-001 — y se repite la
misma corrida de humo para medir el efecto real antes de fijar criterios
de aceptación.

### Segunda corrida — mismos parámetros, tras aplicar ADR-001 (12-ago-2026)

Mismos 15 usuarios / 10 min, mismo `metrogest_carga`, `UVICORN_WORKERS=1`
(sin activar `A` todavía — esta corrida aísla el efecto de `B2` solo).
Antes de correrla: `pytest tests/ -v` → 38/38 verdes, sin regresión de
lógica de negocio.

1,901 peticiones totales (+50% frente a las 1,263 de la corrida anterior —
el sistema procesó bastante más trabajo en el mismo tiempo), 20 fallidas
(1.05%):

| Endpoint | Antes (avg / máx) | Ahora (avg / máx) | Mejora |
|---|---|---|---|
| `GET /analisis/{id}/pdf` | 18.7 s / 80.1 s | **1.92 s / 9.0 s** | ~90% |
| `GET /dashboard/excel` | 53.2 s / 89.4 s | **8.76 s / 16.2 s** | ~84% |
| `GET /dashboard/` | 500 ms / 11.5 s | 408 ms / 7.6 s | — |
| `GET /equipos/?page=N` | 489 ms / 8.4 s | 323 ms / 5.0 s | — |
| `GET /equipos/{id}` | 448 ms / 7.5 s | 299 ms / 5.2 s | — |
| `POST /analisis/{id}/aprobar` | 850 ms / 5.1 s | 812 ms / 6.1 s | — |
| `POST /usuarios/login` | 2.0 s / 3.4 s | 1.63 s / 2.8 s | — |

(Medianas de la segunda corrida, para contexto: dashboard 21 ms, equipos
41-59 ms, PDF 1.0 s, Excel 7.8 s, aprobar 490 ms, login 1.4 s.)

**Interpretación:** la hipótesis de causa raíz de ADR-001 (GIL acaparado por
la generación síncrona de PDF/Excel en el único proceso) queda confirmada
por la corrección — el `ProcessPoolExecutor` liberó el proceso principal, y
tanto el tiempo individual de generación como la latencia de *todo lo
demás* (dashboard, listado de equipos, aprobación de calibración) bajaron,
no solo el de PDF/Excel. El arreglo del recorrido duplicado en
`dashboard.py`/`auditoria.py` también contribuye a que Excel ya no dependa
de recorrer los 1,600 equipos dos veces.

Las 20 fallas siguen siendo errores de conexión (`RemoteDisconnected`,
`ConnectionAbortedError`, `ConnectionResetError`), no errores de aplicación
(no hay 500 ni excepciones de negocio) — mismo patrón que la corrida
anterior, ahora con una tasa apenas mayor (1.05% vs 0.55%) pero sobre 50%
más peticiones procesadas. No hay evidencia todavía de si es ruido de la
máquina de pruebas (Locust y la app corriendo en el mismo equipo Windows,
compitiendo por sockets/puertos efímeros) o algo propio del
`ProcessPoolExecutor` — **queda como punto a vigilar, no bloqueante**, y se
revisará si reaparece o crece en la corrida larga (20-30 min) o al activar
`UVICORN_WORKERS > 1`.

**Decisión sobre B3 (cola de trabajos + polling):** con la corrección de B2
ya no bloquea a otros usuarios mientras se genera un documento (el objetivo
que motivaba considerar B3), y el tiempo individual de PDF (~2s promedio)
es razonable para una descarga sincrónica. Excel (~8.8s promedio) sigue
siendo la más lenta, pero al no bloquear el resto del sistema no justifica
todavía el costo de B3 (tabla+migración, cambio de UX en 7+ puntos,
limpieza de archivos). **B3 queda pospuesta** — se reconsidera solo si al
subir la escala (20-30 usuarios, o al implementar los ~11 endpoints de
PDF/Excel restantes) el tiempo individual de Excel se vuelve inaceptable
para el usuario, no por el efecto colateral en otros usuarios (ya resuelto).

### Tercera corrida — mismos parámetros, `UVICORN_WORKERS=4` (efecto combinado B2+A, 12-ago-2026)

Mismos 15 usuarios / 10 min, mismo `metrogest_carga`, servidor reiniciado con
`python -m uvicorn main:app --host 127.0.0.1 --port 8001 --workers 4`
(`.env` actualizado con `UVICORN_WORKERS=4`, `PDF_EXECUTOR_WORKERS=2`). Los 4
procesos arrancaron limpios — 4× "Application startup complete", sin
tracebacks y sin duplicar el envío de alertas por correo (confirma que
sacar la revisión de alertas del `lifespan` en ADR-001 funciona también con
múltiples workers).

1,956 peticiones totales, 3 fallidas (0.15%):

| Endpoint | B2 solo, 1 worker (avg / máx) | B2 + 4 workers (avg / máx) | Mejora vs. B2 solo |
|---|---|---|---|
| `GET /analisis/{id}/pdf` | 1.92 s / 9.0 s | **1.21 s / 10.1 s** | ~37% en avg |
| `GET /dashboard/excel` | 8.76 s / 16.2 s | **7.70 s / 18.9 s** | ~12% en avg |
| `GET /dashboard/` | 408 ms / 7.6 s | 405 ms / 10.5 s | ≈ igual |
| `GET /equipos/?page=N` | 323 ms / 5.0 s | 291 ms / 9.2 s | ~10% |
| `GET /equipos/{id}` | 299 ms / 5.2 s | 191 ms / 4.9 s | ~36% |
| `POST /analisis/{id}/aprobar` | 812 ms / 6.1 s | 635 ms / 6.4 s | ~22% |
| `POST /usuarios/login` | 1.63 s / 2.8 s | 815 ms / 1.3 s | ~50% |

(Medianas de la tercera corrida: dashboard 20 ms, equipos listado 55 ms,
equipos detalle 38 ms, PDF 980 ms, Excel 7.8 s, aprobar 490 ms, login
790 ms — la mediana de casi todos los endpoints es una fracción del
promedio, señal de que el promedio lo tiran hacia arriba unos pocos
picos, no un problema sostenido.)

**Percentiles (aproximados) de la corrida completa:**

| Endpoint | p50 | p90 | p95 | p99 | máx |
|---|---|---|---|---|---|
| `GET /dashboard/` | 20 ms | 1.1 s | 2.7 s | 6.7 s | 10.5 s |
| `GET /equipos/?page=N` | 55 ms | 270 ms | 1.8 s | 5.0 s | 9.2 s |
| `GET /equipos/{id}` | 38 ms | 170 ms | 1.1 s | 3.7 s | 4.9 s |
| `GET /analisis/{id}/pdf` | 980 ms | 2.6 s | 3.3 s | 9.5 s | 10.1 s |
| `GET /dashboard/excel` | 7.8 s | 11 s | 12 s | 19 s | 18.9 s |
| Agregado | 45 ms | 1.6 s | 3.7 s | 9.7 s | 18.9 s |

**Interpretación — throughput y fallas:** el throughput apenas subió
(1,901 → 1,956 peticiones, +3%) frente a la segunda corrida — los 4
workers no multiplicaron la capacidad bruta, porque con 15 usuarios el
sistema ya no estaba saturado tras B2. Donde sí hay un efecto claro y
consistente con la hipótesis de ADR-001 es en la **tasa de fallas de
conexión: 1.05% → 0.15%** (20 fallidas en 1,901 → 3 fallidas en 1,956),
y las 3 siguen siendo `ConnectionResetError` de sistema operativo, cero
errores de aplicación (sin 500, sin excepciones de negocio) — visible en
el reporte de errores de Locust. Esto responde la duda que había quedado
abierta en la segunda corrida ("¿es ruido de la máquina de pruebas o algo
propio del `ProcessPoolExecutor`?"): con más procesos de SO absorbiendo la
carga, las desconexiones bajaron en vez de subir, lo que apunta a que sí
era saturación del único proceso (colas de aceptación de conexión
llenas), no un defecto del `ProcessPoolExecutor`.

**Interpretación — latencia:** todos los endpoints mejoraron o se
mantuvieron frente a B2 solo; `equipos/{id}` y `login` (~consultas
simples/autenticación) fueron los que más se beneficiaron de tener 4
procesos en paralelo (~36-50% de mejora en promedio), consistente con
que antes competían por el mismo GIL con el resto del tráfico. La cola
larga (p95-p99) de `dashboard/` y `equipos/?page=N` sigue estando por
encima de lo ideal (2.7s y 1.8s en p95 respectivamente) — hay que tenerlo
en cuenta al leer PQ-1/PQ-2 más abajo, porque el promedio se ve bien pero
un usuario individual con mala suerte de timing sí puede ver una petición
lenta ocasional.

### PQ-5 y PQ-7 — evidencia recolectada sobre la tercera corrida (12-ago-2026)

**PQ-5 (deadlocks / escrituras concurrentes):** `grep` de `logs/app.log`
completo por `deadlock|lock timeout|could not obtain lock|serialization
failure` → **0 coincidencias**. Además, las 1,761 líneas registradas
durante la ventana exacta de la tercera corrida (11:31-11:41) son **100%
nivel INFO** — cero `WARNING`/`ERROR`/`CRITICAL` y cero respuestas HTTP
5xx, lo que también refuerza PQ-4 con evidencia del lado del servidor (no
solo el reporte de Locust, que ya mostraba 0 errores de aplicación).

**PQ-7 (integridad de `registro_auditoria`):** se verificó contra
`metrogest_carga` con 4 consultas SQL (ver razonamiento: `aprobar_calibracion`
en `services/analisis_service.py` crea una fila en `firmas_electronicas` —
tabla también auditada — y siempre intenta poner `calibraciones.resultado
= "aprobado"`, así que el número de firmas creadas es la referencia exacta
de "operaciones de escritura exitosas" del script de carga):

| Consulta | Resultado |
|---|---|
| Aprobaciones exitosas (`firmas_electronicas`, ventana de la prueba) | **57** |
| Filas de auditoría que registran la creación de esas firmas | **57** |
| Filas de auditoría de `calibraciones.resultado -> 'aprobado'` | **8** |
| Total de filas nuevas en `registro_auditoria` (cualquier tabla, ventana) | **174** |

Las dos primeras coinciden exactamente (57 = 57): **ninguna firma
electrónica se creó sin su fila de auditoría correspondiente, y ninguna se
duplicó** — el rastro de auditoría no pierde escrituras. **PQ-7 pasa** con
esta evidencia.

La tercera cifra (8, no 57) no es una pérdida de auditoría — es la
auditoría funcionando correctamente: `utils/auditoria_trail.py` solo
escribe una fila cuando el valor de un campo *realmente cambia*
(`if anterior == nuevo: continue`). Si solo 8 de las 57 aprobaciones
representan una transición genuina `pendiente -> aprobado`, eso significa
que **49 de las 57 fueron reaprobaciones** de calibraciones que ya estaban
en `'aprobado'` (mismo valor antes y después → sin fila de auditoría para
ese campo, correctamente).

**Hallazgo de negocio (no es un defecto de la prueba de carga, es un
hallazgo *gracias* a ella):** `services/analisis_service.py:aprobar_calibracion()`
no valida que `cal.resultado` siga siendo `"pendiente"` antes de proceder
— acepta y re-firma calibraciones ya aprobadas sin ningún aviso ni error.
El comentario en `locustfile.py` (`"Reintentar sobre una ya aprobada
simplemente falla la firma silenciosamente en la app"`) resulta **incorrecto**:
se revisó `utils/firma_electronica.py:verificar_y_firmar()` y solo valida la
contraseña, no el estado de negocio del registro que se firma. Cada
reaprobación sí queda en el rastro (nueva fila en `firmas_electronicas`,
y cambios en `aprobado_por_id`/`fecha_aprobacion` si aplica), así que no
hay pérdida de datos ni de trazabilidad — pero para un sistema que se
vende con firma electrónica Ley 527/1999 a clientes farmacéuticos, permitir
reaprobaciones sin límite ni control es un hueco de integridad de proceso
que vale la pena cerrar. **Resuelto (12-ago-2026):** se agregó la guardia en
`services/analisis_service.py:aprobar_calibracion()` — si
`cal.resultado == "aprobado"` retorna `(False, "Esta calibración ya fue
aprobada — no se puede volver a aprobar.")` antes de intentar la firma
(así tampoco se generan `firmas_electronicas`/auditoría "de más" por
reaprobaciones). Se corrigió también el comentario en `locustfile.py` que
describía el comportamiento anterior de forma incorrecta. `pytest tests/ -v`
→ **38/38 verdes**, sin regresión. Pendiente de mejora menor (no
bloqueante): el mensaje de error que ve el usuario en la UI sigue siendo el
badge genérico "Contraseña incorrecta" (`templates/analisis/analisis.html`
línea 19) — no distingue "contraseña mala" de "ya estaba aprobada" porque
el router solo propaga `error_firma=1`, no el texto específico. Ese mismo
patrón se repite en `ilac.py`, `equipos.py` y `verificaciones.py` — si se
decide corregirlo, hacerlo de una vez en los 4 lugares.

### Cuarta corrida — sostenida, 25 min, con monitoreo de memoria/CPU (PQ-6, 12-ago-2026)

Mismos 15 usuarios, `--spawn-rate 3`, `--run-time 25m`, servidor reiniciado
limpio con `UVICORN_WORKERS=4`. En paralelo, `monitorear_recursos.py`
muestreando cada 15s el RSS/CPU del proceso padre y todos sus hijos (script
nuevo, agregado a `requirements-dev.txt` vía `psutil`).

**Nota sobre el pool de aprobaciones:** `POST /analisis/{id}/aprobar` no
aparece en esta corrida — el pool de calibraciones `pendiente` en
`metrogest_carga` ya se había agotado en las corridas cortas anteriores
(entre las tres corridas previas se hicieron ~8-30 aprobaciones genuinas).
`locustfile.py` carga ese pool una sola vez al arrancar (`test_start`), lo
carga vacío si no queda ninguna pendiente, y la tarea se salta sola
(`if ... or not POOL["calibracion_ids_pendientes"]: return`) — no rompe la
prueba, pero significa que esta corrida sostenida no ejercitó el camino de
escritura. Para una futura corrida larga que sí lo necesite: resembrar
`metrogest_carga` antes, o subir `--pct-pendiente` en `seed_carga_masiva.py`.

**Resultado — throughput y errores (4,711 peticiones en 25 min, 9 fallidas, 0.19%):**

| Endpoint | # peticiones | Promedio | Mediana | p95 | p99 | Máx |
|---|---|---|---|---|---|---|
| `GET /dashboard/` | 1,621 | 414 ms | 20 ms | 2.6 s | 5.9 s | 15.7 s |
| `GET /equipos/?page=N` | 1,610 | 214 ms | 57 ms | 940 ms | 4.6 s | 9.1 s |
| `GET /equipos/{id}` | 971 | 191 ms | 39 ms | 830 ms | 3.8 s | 9.8 s |
| `GET /analisis/{id}/pdf` | 322 | 1.25 s | 950 ms | 3.2 s | 6.2 s | 7.7 s |
| `GET /dashboard/excel` | 172 | 8.46 s | 8.2 s | 12 s | 14 s | 14.7 s |
| `POST /usuarios/login` | 15 | 780 ms | 850 ms | 1.2 s | 1.2 s | 1.2 s |

Las 9 fallas son 100% `ConnectionResetError` de sistema operativo (mismo
patrón que las tres corridas anteriores), **cero errores de aplicación**
(sin 500, confirmado en el reporte de errores de Locust). Todas las
métricas (throughput ~3.1 req/s, latencia por endpoint, tasa de fallas)
son consistentes con la tercera corrida de 10 minutos — **no hay
degradación con el tiempo**: ni la latencia ni la tasa de errores crecen
a medida que avanza la corrida de 25 minutos, lo que refuerza la confianza
en PQ-1 a PQ-4 más allá de una corrida corta.

**Resultado — memoria/CPU (PQ-6):**

RSS total de los procesos de Uvicorn (padre + 4 workers + subprocesos del
`ProcessPoolExecutor` de cada worker):

| Momento | Procesos | RSS total |
|---|---|---|
| Antes de que arrancara Locust (línea base) | 6 | ~424 MB, estable |
| Rampa — se crean los subprocesos de `ProcessPoolExecutor` de cada worker (primeros PDF/Excel de cada uno) | 6 → 14 | 424 MB → ~2,140 MB |
| Meseta (de la muestra 60 a la 108, ~12 minutos) | 14 (estable) | 2,470-2,570 MB, oscilando sin tendencia de crecimiento |

**Interpretación:** el salto de memoria ocurre una sola vez, entre el
minuto ~5 y ~10, cuando cada uno de los 4 workers de Uvicorn crea sus
propios 2 subprocesos de `PDF_EXECUTOR_WORKERS` la primera vez que procesa
un PDF/Excel (6 procesos → 14, cada uno cargando su propia copia de
numpy/matplotlib/reportlab/openpyxl — de ahí el costo). A partir de ahí el
conteo de procesos (14) y el RSS total (banda 2.47-2.57 GB) se mantienen
estables durante los ~12 minutos restantes de la corrida, sin tendencia de
crecimiento sostenido. **No hay evidencia de fuga de memoria — PQ-6 pasa.**

**Consecuencia para dimensionamiento (actualiza el pendiente de ADR-001):**
~2.5 GB de RAM es el costo real medido de `UVICORN_WORKERS=4` +
`PDF_EXECUTOR_WORKERS=2` bajo esta carga — muy por encima del "mínimo 256
MB" que documenta `README.md` (desactualizado, viene de la época de un solo
proceso SQLite). Falta sumar Postgres + sistema operativo al calcular el
RAM mínimo recomendado para la instalación del cliente. Una opción a
evaluar (no aplicada todavía, es una decisión de trade-off memoria vs.
throughput de PDF/Excel bajo concurrencia): bajar `PDF_EXECUTOR_WORKERS` a
1 reduciría los subprocesos de 8 a 4 y debería recortar buena parte de ese
salto de ~1.7 GB, a costa de que dos usuarios generando PDF/Excel *al mismo
tiempo* en el mismo worker de Uvicorn hagan cola entre sí (en vez de
correr en paralelo) — con solo 2-3 peticiones de PDF/Excel por minuto en
esta corrida (321 en 25 min), es poco probable que eso se note en la
práctica.

## 8. Criterios de aceptación

**Confirmados y cerrados con Edison el 12-ago-2026**, con los datos reales
de las 4 corridas ya en la mano (no a ciegas, como exigía este mismo
documento en la versión anterior de esta sección). Redacción final y
resultado de cada uno de los 7 criterios (PQ-1 a PQ-7) en
`validacion_farma/PQ_CALIFICACION_DESEMPENO.md` §3, con la justificación de
la ambigüedad promedio-vs-percentil resuelta en la nota debajo de esa
tabla. Conclusión: **PQ aprobado con desviaciones documentadas** (§5 del
mismo documento) — falta solo la firma formal de revisor, fuera del
alcance de esta sesión de Claude.

## 9. Pendiente (próxima sesión)

**Decisiones ya tomadas con Edison (28-jul-2026):**

- Los criterios numéricos de PQ §3 **quedan como borrador, sin confirmar
  todavía** — se confirman con datos reales en la mano, después de la corrida
  de humo (15 usuarios / 10 min), no antes. No se fija ningún número a
  ciegas.
- La BD de staging es una **segunda base de datos en el mismo servidor
  Postgres local** que ya usa la instalación de desarrollo (no una instancia
  separada, no Docker) — nombre sugerido: `metrogest_carga` (contiene
  "carga", así que pasa la guarda de seguridad de `seed_carga_masiva.py`
  y `locustfile.py` sin necesitar `--confirmo-que-no-es-produccion`).

**Runbook concreto para la próxima corrida** (Edison ejecuta estos pasos —
Claude no tiene forma de escribir comandos en una terminal de este entorno,
solo clic; ver `CLAUDE.md` §7.8):

1. **Crear la BD nueva** en el mismo Postgres local (con `psql` o pgAdmin):
   ```sql
   CREATE DATABASE metrogest_carga OWNER metrogest;
   ```
   (usa el mismo rol `metrogest` que ya existe — mismo usuario, base nueva.
   Si ese rol no tiene privilegio `CREATEDB`, créala con tu superusuario y
   luego `GRANT ALL PRIVILEGES ON DATABASE metrogest_carga TO metrogest;`.)

2. **Aplicar el esquema con Alembic** contra la BD nueva, sin tocar el `.env`
   real (en Windows, `cmd`, dentro de la carpeta del proyecto):
   ```bat
   set DATABASE_URL=postgresql+psycopg2://metrogest:<misma-contraseña-de-tu-.env>@localhost:5432/metrogest_carga
   alembic upgrade head
   ```
   (`set` en `cmd` solo dura esa sesión de terminal — no modifica el `.env`
   real ni afecta a la instalación normal.)

3. **Levantar una instancia de MetroGest contra esa BD primero** (orden
   corregido tras ejecutarlo en vivo el 12-ago-2026: el script de siembra
   exige que ya exista el usuario `administrador`, y ese usuario solo lo
   crea la app en su primer arranque — `seed_carga_masiva.py` falla con un
   mensaje explícito si se corre antes de este paso). Puerto distinto al de
   la instalación real para no chocar con ella:
   ```bat
   set DATABASE_URL=postgresql+psycopg2://metrogest:<misma-contraseña>@localhost:5432/metrogest_carga
   python -m uvicorn main:app --host 127.0.0.1 --port 8001
   ```
   Espera a ver en consola `⚠ Admin creado: admin@metrogest.com / ...`, y
   ahí sí `Ctrl+C` para detenerla y liberar la terminal para el paso 4.

4. **Sembrar los datos sintéticos** (misma terminal, misma variable ya en
   memoria):
   ```bat
   set CARGA_DATABASE_URL=%DATABASE_URL%
   python seed_carga_masiva.py --confirmo-que-no-es-produccion
   ```
   Va a pedir escribir `SI` para confirmar antes de insertar nada — genera
   además `usuarios_carga.json` con las credenciales de los usuarios de
   prueba (no lo subas a git, ya está en `.gitignore`). Después de sembrar,
   vuelve a levantar la instancia del paso 3 (mismo comando `uvicorn`, esta
   vez déjala corriendo) para la corrida de Locust del paso 5.

5. **Corrida de humo** (terminal nueva, en la carpeta del proyecto, con
   `CARGA_DATABASE_URL` puesto igual que en el paso 3):
   ```bat
   locust -f locustfile.py --host http://127.0.0.1:8001 --users 15 --spawn-rate 3 --run-time 10m --headless
   ```
   Revisar que no haya errores de arranque, que los pools se carguen (mensaje
   `>>> Pools cargados: ...` en consola) y que las tareas respondan con
   códigos 2xx/3xx antes de pasar a la corrida larga.

6. **Con los números de la corrida de humo en la mano**, volver a esta
   sección y a `PQ_CALIFICACION_DESEMPENO.md` §3 para fijar los criterios
   numéricos reales (ya no como borrador) y planear la corrida larga
   (20-30 min) que produce la evidencia formal.

- [x] Pasos 1-4 del runbook (Edison, 12-ago-2026, guiado paso a paso).
      `metrogest_carga` creada (owner `metrogest`), esquema aplicado con
      Alembic hasta `9c49db38b7c1`, fixture sembrada:
      1,600 equipos · 2,340 magnitudes · 8,304 calibraciones (41,520 puntos)
      · 8,286 verificaciones (24,858 puntos) · 2,856 mantenimientos ·
      2,090 evaluaciones de riesgo ILAC · 20 usuarios de carga
      (`usuarios_carga.json`, no versionado). Coincide con las estimaciones
      de §3.
- [x] Paso 5 — corrida de humo (12-ago-2026, 15 usuarios / 10 min). Resultado
      en §7: PDF/Excel síncronos confirmados como cuello de botella
      dominante (hasta 89s), con desconexiones colaterales en dashboard,
      listado de equipos e incluso aprobación de calibración.
- [x] Decidido con Edison (12-ago-2026): corregir primero. Ver
      `docs/arquitectura/DECISIONES.md` ADR-001 — `ProcessPoolExecutor` para
      PDF/Excel (`GET /analisis/{id}/pdf`, `GET /dashboard/pdf`,
      `GET /dashboard/excel`), arreglo del recorrido duplicado de 1,600
      equipos en `dashboard.py`/`auditoria.py`, y `UVICORN_WORKERS`
      configurable en `iniciar.bat` (requiere antes sacar la revisión de
      alertas del `lifespan` — ya corregido, ver README §7).
- [x] Segunda corrida (12-ago-2026, mismos parámetros, B2 solo,
      `UVICORN_WORKERS=1`): confirma la causa raíz de ADR-001, PDF -90%,
      Excel -84%, resto de endpoints también mejora. B3 pospuesta. Ver §7
      segunda corrida.
- [x] Tercera corrida (12-ago-2026, efecto combinado B2+A,
      `UVICORN_WORKERS=4`): tasa de fallas de conexión baja de 1.05% a
      0.15%, mejoras adicionales de latencia. Ver §7 tercera corrida.
- [x] PQ-5 y PQ-7 verificados con evidencia (`logs/app.log`, consultas SQL
      contra `metrogest_carga`) — hallazgo de negocio (reaprobación sin
      guardia) encontrado y corregido en `services/analisis_service.py`,
      `pytest` 38/38 verdes. Ver §7.
- [x] Cuarta corrida — sostenida 25 min con monitoreo de memoria/CPU
      (`monitorear_recursos.py`, PQ-6): sin fuga de memoria, sin
      degradación de latencia/errores con el tiempo. Ver §7 cuarta corrida.
- [x] Criterios de aceptación numéricos confirmados con Edison (12-ago-2026,
      con los datos reales en la mano, no a ciegas): "promedio < 2s Y
      p95 < 3s" para PQ-1/PQ-2 — ver `PQ_CALIFICACION_DESEMPENO.md` §3.
- [x] Evidencia recolectada y tabla de resultados completa en este documento
      y en `PQ_CALIFICACION_DESEMPENO.md` §4-5 — **PQ aprobado con
      desviaciones documentadas** (cola de latencia p99, no bloqueante).
      **Fase 2.3 cerrada.** Falta solo la firma de revisor en el PQ (fuera
      del alcance de esta sesión de Claude).
