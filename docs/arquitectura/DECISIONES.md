# Decisiones de arquitectura (ADR corto)

> Registro de decisiones de diseño relevantes, formato breve tipo ADR:
> contexto, decisión, alternativas consideradas, consecuencias. Sirve para
> no repetir discusiones ni revertir decisiones por accidente. Ver
> `docs/PROJECT_PLAN.md` §1.2.

---

## ADR-001 — Corregir el cuello de botella de PDF/Excel con `ProcessPoolExecutor` + workers de Uvicorn, no con una cola de trabajos

**Fecha:** 12-ago-2026
**Estado:** Aceptada — implementada y medida (ver resultado abajo)
**Contexto que la motivó:** corrida de humo de la Fase 2.3 (`docs/calidad/PLAN_PRUEBAS_CARGA.md` §7) con 15 usuarios / 10 min contra `metrogest_carga` (1,600 equipos sintéticos). Resultado: `GET /analisis/{id}/pdf` con promedio 18.7s (máximo 80.1s) y `GET /dashboard/excel` con promedio 53.2s (máximo 89.4s), con desconexiones colaterales en `/dashboard/`, `/equipos/` y `POST /analisis/{id}/aprobar` — el evento de negocio más crítico del sistema — mientras esos documentos se generaban.

### Causa raíz identificada

Los endpoints de PDF/Excel ya son funciones síncronas normales (`def`, no `async def`), así que FastAPI ya los despacha a un thread pool interno — el problema **no es el event loop de asyncio**. El problema es que ReportLab/openpyxl consumen CPU real, y con un solo proceso Python (`iniciar.bat` arranca Uvicorn sin `--workers`), todos los hilos compiten por el mismo GIL. Mientras un hilo genera un Excel de 53 segundos, acapara el intérprete y todos los demás usuarios —sin importar qué estén haciendo— quedan esperando.

Un segundo factor, independiente del anterior: `routers/dashboard.py` calculaba los datos de exportación **dos veces** por cada PDF/Excel — una vez cacheada (`_calcular_datos_cacheado`, KPIs) y otra vez sin caché (`_filas_y_totales` → `routers/auditoria.py:_datos`, el detalle fila-por-fila), cada una recorriendo los 1,600 equipos completos con sus relaciones. Esto infla el tiempo de generación independientemente de cuánta concurrencia haya.

### Opciones consideradas

| Opción | Qué es | Por qué se descarta / acepta |
|---|---|---|
| **A — `uvicorn --workers N`** | Procesos de SO separados, cada uno con su propio GIL. | Aceptada como refuerzo — diluye la contención entre procesos, pero por sí sola no resuelve la causa raíz (un PDF individual sigue tardando igual) y tenía un bug real: el `lifespan` de `main.py` revisa y manda alertas por correo en cada arranque — con N workers, N arranques simultáneos = N veces las mismas alertas. Ver corrección abajo. |
| **B1 — Cola externa (Celery/RQ + Redis)** | Patrón estándar de background jobs con broker externo. | Descartada para esta escala. MetroGest se vende como instalación local en el servidor del cliente (`CLAUDE.md` §1) — pedirle al cliente que instale y mantenga Redis además de Postgres no se justifica para 10-20 usuarios concurrentes. |
| **B2 — `ProcessPoolExecutor` interno** | La generación se manda a un proceso hijo de Python vía `loop.run_in_executor`, sin infraestructura nueva. El endpoint sigue respondiendo igual (el usuario sigue esperando su descarga), pero mientras el proceso hijo trabaja, el proceso principal queda libre para todos los demás. | **Aceptada.** Ataca la causa raíz real (libera el GIL del proceso principal) sin nueva infraestructura ni cambio de UX. |
| **B3 — Job con estado + polling** | Tabla de trabajos, endpoints de estado, JS de polling — decoupla también la espera del usuario que pidió el documento. | Pospuesta. B3 necesita a B2 como motor de ejecución (no lo reemplaza), y el costo (tabla+migración, 7+ puntos de descarga a cambiar de UX, limpieza de archivos, tests nuevos de estado async) solo se justifica si, tras aplicar B2, el tiempo *individual* de generación sigue siendo inaceptable. Se decide medir primero. |

### Decisión

1. **B2** — introducir un `ProcessPoolExecutor` en `main.py` y una función genérica `utils/orm_snapshot.py:_snapshot()` que convierte cualquier objeto SQLAlchemy ya cargado en una copia desconectada de la sesión (picklable), copiando columnas escalares y relaciones ya cargadas recursivamente vía `sqlalchemy.inspect(...).mapper` — sin tener que reescribir a mano cada generador de PDF/Excel. Aplicada primero a los dos endpoints con evidencia real de la corrida de humo: `GET /analisis/{cid}/pdf` y los exportadores del dashboard (`GET /dashboard/pdf`, `GET /dashboard/excel`). Los otros ~11 endpoints de PDF/Excel del sistema (mantenimientos, verificaciones, ilac ×5, auditoría) quedan pendientes de aplicar el mismo patrón — ver checklist en `docs/PROJECT_PLAN.md`.
2. **Arreglo del recorrido duplicado** — `dashboard.py:_calcular_datos` ahora calcula también las filas de detalle en la misma pasada que ya usa `selectinload`, en vez de que `_filas_y_totales` dispare una segunda consulta completa sin caché.
3. **A** — se agrega `--workers` a `iniciar.bat`, configurable vía `.env` (`UVICORN_WORKERS`, default 4), pero **solo después** de sacar la revisión de alertas del `lifespan` de arranque: ya existe `script_alertas.py` + `configurar_tarea_windows.bat` (tarea programada diaria de Windows) para esto — estaba en el repo pero **no documentado como paso de instalación** en `README.md`, lo cual además significa que hoy las alertas solo se disparaban cuando alguien reiniciaba el servidor, no todos los días como se pretendía. Se corrige ambas cosas a la vez: se saca del `lifespan` y se documenta la tarea programada como paso obligatorio de instalación.

### Consecuencias

- RAM: con `UVICORN_WORKERS=4` la app usa ~4× la memoria de un solo proceso (cada worker carga su propia copia de la app). El requisito de "RAM mínimo 256 MB" en `README.md` queda desactualizado y debe revisarse una vez se mida con la carga completa.
- Conexiones a Postgres: cada worker abre su propio pool (`pool_size=5, max_overflow=10` por defecto de SQLAlchemy, no configurado explícitamente en `database.py`) → con 4 workers, hasta 60 conexiones simultáneas. Verificar contra `max_connections` de Postgres antes de subir `UVICORN_WORKERS` en producción.
- El patrón `_snapshot()` es reusable — cualquier nuevo endpoint de PDF/Excel debería usarlo desde el día uno en vez de pasar objetos ORM vivos a un executor.
- Pendiente de evidencia: correr de nuevo la prueba de carga (`docs/calidad/PLAN_PRUEBAS_CARGA.md`) tras este cambio, para confirmar que desaparecen las desconexiones colaterales y medir el tiempo real de generación sin contención — eso decide si hace falta B3 más adelante.

### Resultado medido (12-ago-2026, ver `docs/calidad/PLAN_PRUEBAS_CARGA.md` §7)

Misma corrida de humo (15 usuarios, 10 min, `metrogest_carga`,
`UVICORN_WORKERS=1` — es decir, este resultado aísla el efecto de B2 solo,
sin sumar todavía el de A):

- `GET /analisis/{id}/pdf`: 18.7s → **1.92s** promedio (máx 80.1s → 9.0s).
- `GET /dashboard/excel`: 53.2s → **8.76s** promedio (máx 89.4s → 16.2s).
- El resto de endpoints (dashboard, listado de equipos, aprobar
  calibración) también bajó su latencia — confirma que el problema real no
  era el tiempo de PDF/Excel en sí, sino que acaparaban el único proceso.
- Throughput total: 1,263 → 1,901 peticiones en los mismos 10 minutos
  (+50%).
- Tasa de fallas de conexión: 0.55% → 1.05% (ambas corridas: errores de
  socket — `RemoteDisconnected`/`ConnectionReset`/`ConnectionAborted` —,
  cero errores de aplicación). Sube un poco en términos relativos, pero
  sobre 50% más peticiones; no hay evidencia de si es ruido de correr
  Locust y la app en la misma máquina Windows o algo propio del
  `ProcessPoolExecutor`. **Queda como punto a vigilar**, no bloqueante —
  revisar si crece en la corrida larga (20-30 min) o al activar
  `UVICORN_WORKERS > 1`.
- **B3 pospuesta**: con B2, la generación de PDF/Excel ya no bloquea a
  otros usuarios (el problema que motivaba considerar B3). Se reconsidera
  solo si el tiempo *individual* de Excel se vuelve inaceptable a mayor
  escala, no por el efecto colateral (ya resuelto).
- Pendiente aún: activar `A` (`UVICORN_WORKERS > 1`) y repetir la medición
  para ver el efecto combinado; verificar RAM y `max_connections` de
  Postgres antes de subirlo en la instalación del cliente.

### Efecto combinado B2+A medido (12-ago-2026, `UVICORN_WORKERS=4`, ver `docs/calidad/PLAN_PRUEBAS_CARGA.md` §7 tercera corrida)

Misma corrida de humo (15 usuarios, 10 min, `metrogest_carga`), servidor
con 4 workers de Uvicorn. Los 4 procesos arrancaron limpios, sin duplicar
las alertas por correo — confirma que el fix de sacar la revisión de
alertas del `lifespan` sostiene con múltiples workers, no solo con uno.

- Tasa de fallas de conexión: **1.05% → 0.15%** (20/1,901 → 3/1,956) —
  bajó en vez de subir al agregar procesos, lo que indica que la causa era
  saturación de un único proceso aceptando conexiones, no un defecto del
  `ProcessPoolExecutor`. Sigue siendo 100% `ConnectionResetError` de
  sistema operativo, cero errores de aplicación.
- Throughput: 1,901 → 1,956 peticiones en los mismos 10 minutos (+3%) —
  con 15 usuarios el sistema ya no estaba saturado tras B2 solo, así que
  A no multiplica el throughput bruto, pero sí absorbe mejor los picos
  (ver fallas arriba).
- Latencia promedio: mejora o se mantiene en todos los endpoints frente a
  B2 solo. Los más beneficiados por tener 4 procesos en paralelo son
  `equipos/{id}` (299ms → 191ms) y `login` (1.63s → 815ms) — antes
  competían por el GIL del único proceso con el resto del tráfico. PDF
  1.92s → 1.21s, Excel 8.76s → 7.70s.
- Cola larga (p95-p99) de `dashboard/` (p95=2.7s) y `equipos/?page=N`
  (p95=1.8s) sigue por encima del ideal — el promedio se ve bien pero
  hay peticiones individuales ocasionales que tardan más de lo que
  sugiere el promedio. No bloqueante, pero relevante para leer PQ-1/PQ-2.
- **B2+A queda validado como la combinación de trabajo** para esta escala
  (15 usuarios simulados, 1,600 equipos). Pendiente: verificar RAM real
  usada con 4 workers y `max_connections` de Postgres antes de fijar
  `UVICORN_WORKERS=4` como valor de instalación por defecto en el cliente
  (ver consecuencias arriba — hasta 60 conexiones simultáneas con el pool
  por defecto de SQLAlchemy).

### RAM real medida (12-ago-2026, corrida sostenida de 25 min, ver `docs/calidad/PLAN_PRUEBAS_CARGA.md` §7 cuarta corrida)

Con `UVICORN_WORKERS=4` + `PDF_EXECUTOR_WORKERS=2`, el RSS total de los
procesos de MetroGest (padre + 4 workers + hasta 8 subprocesos de
`ProcessPoolExecutor`, 14 procesos en total una vez que cada worker generó
su primer PDF/Excel) se estabiliza en **~2.5 GB**, medido con
`monitorear_recursos.py` durante 25 minutos sin señal de fuga (banda
2.47-2.57 GB sostenida, sin tendencia de crecimiento). El "RAM mínimo 256
MB" de `README.md` queda confirmado como **desactualizado** — hay que
sumarle Postgres y el sistema operativo al RAM mínimo recomendado para la
instalación del cliente; pendiente actualizar `README.md` con una cifra
real (sugerido: no menos de 4 GB dedicados a la instalación completa,
Postgres incluido, como punto de partida a validar).

Opción de reducción no aplicada todavía: bajar `PDF_EXECUTOR_WORKERS` de 2
a 1 recortaría los subprocesos de 8 a 4 (la mayor parte del salto de ~1.7
GB), a costa de que dos generaciones de PDF/Excel simultáneas en el mismo
worker de Uvicorn hagan cola entre sí en vez de correr en paralelo — dado
el volumen bajo de esas peticiones (321 PDF + 172 Excel en 25 minutos en
la corrida), es poco probable que se note en la práctica. Evaluar si vale
la pena antes de fijar el valor de instalación por defecto.

---
