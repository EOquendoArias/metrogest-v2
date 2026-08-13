# MetroGest v2 — Plan maestro: Documentación, Calidad y Preparación para Clientes

> Roadmap de las 3 líneas de trabajo pedidas tras la primera demo con cliente:
> documentación técnica, pruebas de calidad (incluida carga a escala), y
> documentación lista para presentar a clientes. Este documento es el punto
> de partida — cada fase produce un entregable concreto dentro de `docs/`.
> Actualízalo (marcar `[x]`) a medida que se complete cada fase.

## 0. Contexto y objetivo de escala

- Primera demo con cliente: feedback positivo, pero el sistema aún no estaba
  preparado para la escala objetivo.
- **Objetivo de capacidad:** ~1,600 equipos de medición y 10-20 usuarios
  concurrentes por instalación.
- Los clientes objetivo incluyen **industria farmacéutica** — eso agrega
  un requisito adicional: no basta con que el software funcione bien, hay
  que poder mostrar **evidencia documentada de validación** (CSV) bajo un
  marco regulatorio de integridad de datos. Ver
  [`docs/calidad/validacion_farma/`](calidad/validacion_farma/README.md) —
  ya iniciado (Plan Maestro de Validación, gap analysis contra el código
  real, protocolos IQ/OQ/PQ).
- Ya se hizo, como respuesta directa a esto: migración SQLite → PostgreSQL,
  endurecimiento de seguridad completo (ver `CLAUDE.md` §5), paginación y
  caché del dashboard, backups automáticos con restauración probada,
  infraestructura de pruebas + CI.
- Lo que **falta** para poder decir con evidencia "esto soporta 1,600
  equipos / 10-20 usuarios" es una prueba de carga real — eso es el centro
  de la Línea 2 (§2.3).

## 1. Línea 1 — Documentación técnica (`docs/arquitectura/`) — ✅ Completa (12-ago-2026)

| Fase | Entregable | Contenido |
|---|---|---|
| 1.1 | `docs/arquitectura/ARQUITECTURA.md` | **Hecho.** Diagrama y descripción de la arquitectura actual: FastAPI + Jinja2 SSR + PostgreSQL, capa de routers vs. capa de servicios (`services/`, aún parcial — solo `analisis_service.py` y `verificaciones_service.py`), los 6 middlewares en orden real con la advertencia de diseño sobre `RequestLoggingMiddleware`/`SessionMiddleware` que ya causó un bug real, esquema de BD (20 tablas, no 18 — agrupadas por dominio, con los patrones de soft-delete y auditoría automática). |
| 1.2 | `docs/arquitectura/DECISIONES.md` | **Hecho.** ADR-001 (por qué `ProcessPoolExecutor` + workers de Uvicorn y no una cola externa, con resultados medidos en 4 corridas de carga). Los otros ADR candidatos (Postgres vs. SQLite, Alembic, firma simple vs. PKI, HMAC propio) quedan pendientes de redactar — no bloquean, se documentan si vuelve a surgir la discusión. |
| 1.3 | Runbook operativo | Cubierto por `README.md` (instalación, arranque, backup, recuperación de contraseña) — ya incorporó los huecos que salieron de la Línea 2 (RAM real medida, `UVICORN_WORKERS`, tarea programada de alertas obligatoria). |

**No se duplica** contenido que ya vive en `README.md` o `CLAUDE.md` —
`ARQUITECTURA.md` enlaza a esos archivos en vez de repetirlos.

## 2. Línea 2 — Calidad y pruebas (`docs/calidad/`)

### 2.1 Inventario de cobertura actual (punto de partida, ya real)

Los 7 archivos en `tests/` ya cubren, contra una BD Postgres de prueba real
(no mocks):

- `test_00_infra.py` — aislamiento de transacciones entre tests
- `test_auth.py` — rate-limiting de login por (email+ip) y por ip global
- `test_calculos.py` — semáforo de calibración (funciones puras)
- `test_deriva.py` — análisis de deriva M1 (ILAC-G24)
- `test_firma_electronica.py` — reautenticación antes de firmar
- `test_rbac.py` — control de acceso por rol a nivel HTTP
- `test_auditoria_trail.py` — rastro de auditoría automático

**Gap-analysis pendiente (Fase 2.1):** producir `docs/calidad/COBERTURA.md`
con una matriz flujo-de-negocio × ¿tiene test? para los flujos que *no*
aparecen arriba: registrar equipo, ciclo completo de calibración con
aprobación, ciclo de verificación intermedia, mantenimiento preventivo,
generación de PDF/Excel, exportación del dashboard, ILAC (evaluación de
riesgo de 14 factores), notificaciones de vencimiento.

### 2.2 Plan de pruebas funcionales / regresión

`docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md` — prioriza por impacto de
negocio, no por orden alfabético de router:

1. Login + bloqueo por intentos (ya cubierto)
2. Alta de equipo → magnitud → evaluación ILAC → calibración → aprobación
   (flujo de onboarding completo, §13.1 de `GUIA_PROYECTO.md` como
   referencia de intención original — verificar que sigue siendo así)
3. Verificación intermedia con puntos y cierre
4. Mantenimiento (preventivo y correctivo) y su efecto sobre el estado del
   equipo
5. Generación de PDFs (análisis, verificación, mantenimiento, dashboard) —
   sensible a romperse con cambios de datos porque usa `ReportLab` con
   layouts fijos
6. Exportación Excel del dashboard
7. Ciclo de vida de licencia: activa → por vencer (banner) → vencida (modo
   solo lectura) → sin licencia (bloqueo total)

### 2.3 Plan de pruebas de carga y concurrencia — **el entregable crítico**

`docs/calidad/PLAN_PRUEBAS_CARGA.md` debe responder, con evidencia y no con
intuición, si el sistema soporta el objetivo de negocio:

**Escenario objetivo a simular:**
- Volumen de datos: ~1,600 equipos, cada uno con 1-3 magnitudes, cada
  magnitud con historial de calibraciones/verificaciones acumulado de
  varios años (estimar ~15,000-30,000 filas en `calibraciones` +
  `verificaciones_intermedias` combinadas, y varias veces eso en
  `puntos_calibracion`/`puntos_verificacion`).
- Concurrencia: 10-20 usuarios activos simultáneos, con la mezcla de uso
  real (mayoría navegando/consultando dashboard y listados, minoría
  registrando calibraciones o generando PDFs al mismo tiempo).

**Qué medir:**
- Tiempo de respuesta del dashboard y del listado de equipos paginado con
  el volumen completo de datos (ya hay paginación/caché — falta medirla a
  esta escala, no solo confiar en que "debería andar bien").
- Tiempo de generación de PDF/Excel bajo carga concurrente (ReportLab y
  openpyxl son síncronos y pueden bloquear el worker de Uvicorn si no se
  ejecutan correctamente).
- Comportamiento de la BD Postgres bajo escritura concurrente real
  (aprobaciones de calibración, firmas electrónicas) — verificar que no hay
  contención de locks inesperada.
- Uso de memoria/CPU del proceso Uvicorn con el volumen completo cargado.

**Herramientas sugeridas** (a decidir en la ejecución de esta fase, no
ahora): `locust` o `k6` para carga HTTP concurrente; un script de
`seed_demo_data.py` (ya existe en el repo) ampliado o parametrizado para
generar ~1,600 equipos sintéticos con historial realista como fixture de
carga.

**Regla de oro:** esta prueba se corre contra una base de datos de prueba o
de staging, **nunca contra la base de datos real de un cliente** — mismo
principio que ya se sigue en `tests/conftest.py`.

**Criterio de aceptación a definir junto con el usuario** antes de correr la
prueba (ej. "dashboard responde en <2s con 1,600 equipos y 15 usuarios
concurrentes navegando"), para que el resultado sea un sí/no verificable y
no una impresión subjetiva.

### 2.4 Checklist de seguridad recurrente — ✅ Hecho (12-ago-2026)

`docs/calidad/CHECKLIST_SEGURIDAD.md` — convierte las 6 brechas cerradas de
`CLAUDE.md` §5 (bloque A) más el endurecimiento posterior (bloque B: rate
limiting, RBAC, cabeceras HTTP, validación de archivos, archivos protegidos,
página 500 genérica, auditoría automática, soft-delete, firma electrónica,
backups) en una checklist de auditoría **repetible**, pensada para marcarse
antes de cada entrega a un cliente nuevo — no depende de la memoria de una
sesión puntual de Claude.

Cada ítem queda marcado como **Automatizado** (referencia al archivo de
test exacto que lo cubre) o **Manual** (comando o revisión de código
puntual, cuando no es automatizable con pytest). Se identificaron 3
desviaciones abiertas durante la redacción — quedan registradas en el
propio documento, no bloquean la fase:

1. Cabeceras de seguridad HTTP (`CabecerasSeguridadMiddleware`) sin test.
2. Validación de archivos subidos (extensión/tamaño) sin test.
3. Servido de archivos protegidos por sesión sin test.

Además el documento deja explícita una advertencia de diseño real (no
teórica): el `@app.exception_handler(Exception)` genérico de `main.py` **no**
protege contra excepciones lanzadas dentro de middlewares personalizados
— exactamente la causa del bug de `RequestLoggingMiddleware` corregido en
la Fase 2.2 (ítem 3). Cualquier middleware nuevo debe manejar sus propias
excepciones.

## 3. Línea 3 — Documentación para clientes (`docs/cliente/`) — ✅ Completa (12-ago-2026)

Dos documentos separados, para dos audiencias distintas (decisión ya
tomada con el usuario):

| Documento | Audiencia | Contenido |
|---|---|---|
| `docs/cliente/RESUMEN_EJECUTIVO.md` | Decisor de negocio del cliente (gerente de calidad, dueño del laboratorio) | Qué problema resuelve, cumplimiento ISO/IEC 10012 e ILAC G24, propuesta de valor, capacidad soportada (1,600 equipos / 10-20 usuarios), sin jerga técnica. Corto — pensado para leerse en una reunión, no para auditoría. |
| `docs/cliente/ANEXO_TECNICO.md` | Equipo técnico/TI del cliente o auditor externo | Arquitectura, seguridad (autenticación, cifrado, control de acceso por rol, rastro de auditoría, firma electrónica), modelo de datos, plan de backup/recuperación, resultados de las pruebas de calidad y de carga (Línea 2) como evidencia objetiva. |

Ambos se redactan **después** de que la Línea 2 produzca resultados reales
de pruebas — el anexo técnico pierde credibilidad si cita capacidad
soportada sin una prueba de carga que lo respalde.

## 4. Secuencia recomendada

1. ~~Fundar el proyecto: `CLAUDE.md` + esta estructura de `docs/`~~ (esta fase)
2. ~~Línea 2, fase 2.1 — inventario de cobertura~~ → `docs/calidad/COBERTURA.md`.
   Hallazgo principal: 82 endpoints reales, solo 3 con test HTTP directo;
   ningún flujo de negocio completo tiene test de integración. Define el
   orden de la fase 2.2.
3. Línea 2, fase 2.3 — plan de prueba de carga: **secciones 1-6 ya
   redactadas** en `docs/calidad/PLAN_PRUEBAS_CARGA.md` (herramienta Locust,
   dataset sintético de 1,600 equipos, riesgos de arquitectura). Falta
   ejecutar el runbook (§9 de ese documento — pasos que corre Edison
   localmente) y llenar secciones 7-8 con resultados reales.
4. Línea 1 completa (arquitectura + decisiones) — más fácil de escribir bien
   una vez que la prueba de carga confirma o corrige supuestos de diseño
5. Línea 3 (documentos de cliente) — al final, para que cite datos reales
   en vez de promesas

## 4.1 Línea nueva — Importación de datos históricos de clientes (`docs/migracion/`)

No estaba en el alcance original de este documento (documentación/calidad/
venta de lo ya construido) — surgió el 12-ago-2026 al revisar con Edison
un servicio que ya cobra de forma independiente: cargar el historial de un
cliente (hasta 5 años, ~1,600 equipos) dentro de MetroGest. Se verificó
que **hoy no existe ninguna herramienta de importación desde Excel** — es
un vacío de producto real. Ver `docs/migracion/PLAN_IMPORTACION_EXCEL.md`
para el diseño técnico (arquitectura Power Query + importador Python,
esquema de plantilla, validación y detección de duplicados en 3 niveles)
y `docs/migracion/GUIA_VALIDACION_Y_DESVIACIONES.md` para el framework de
*proceso* (checklist de preparación, clasificación de desviaciones por
severidad, Registro de Desviaciones, flujo de resolución conjunta con el
cliente) — este último ya se puede aplicar conceptualmente aunque el
importador todavía no exista en código.
**Estado (actualizado 12-ago-2026):** diseño y framework de proceso
completos; `importar_excel.py` construido y **verificado de punta a punta
contra Postgres real** (`metrogest_carga`) — lectura, 5 niveles de
validación (14/14 errores deliberados detectados), escritura transaccional,
rastro de auditoría y detección de duplicados en 3 capas, todo con
evidencia real (ver `PLAN_IMPORTACION_EXCEL.md` §9-§10). En esa
verificación se encontró y corrigió un bug real: el rastro de auditoría no
se generaba para las cargas del importador (el módulo que engancha los
listeners de SQLAlchemy nunca se importaba en ese proceso) — reverificado
con éxito tras el fix. Listo técnicamente para usarse con un cliente real.
Fase 3 (receta de Power Query) también lista —
`docs/migracion/RECETA_POWER_QUERY.md`, metodología reutilizable, sin
probar todavía contra un Excel real de cliente. Se decidió que esa receta
es documentación **interna** (el know-how del servicio que Edison cobra
aparte, no algo que el cliente opera); lo que sí se entrega al cliente es
`docs/cliente/GUIA_PREPARACION_DATOS.md` (nuevo, checklist de preparación
en lenguaje simple, tercer documento de la Línea 3).
Fase 5 también construida y verificada de punta a punta contra Postgres
real (12-ago/13-ago-2026, `docs/migracion/PLAN_FASE5_EXTENSIONES.md`): 6
hojas nuevas opcionales (Verificaciones intermedias, Evaluación de riesgo
ILAC, Mantenimientos). La regla de ILAC deriva el intervalo adoptado del
historial real de calibraciones (criterio de negocio de Edison, verificado
contra `routers/ilac.py` real, no inventado) — confirmado con datos reales
en Postgres: intervalo derivado correctamente (6 meses) de dos
calibraciones separadas ese intervalo. Un hallazgo real sobre el
significado de "aceptar" una desviación Alta de Capa 3 (inserta la fila,
no la omite) quedó documentado en `GUIA_VALIDACION_Y_DESVIACIONES.md` §3.
**Corregido y verificado contra Postgres real (13-ago-2026):** el
importador ya no confía ciegamente en `Resuelta - corregida en origen` —
si esa clave reaparece, sigue bloqueando `--ejecutar`; solo `Aceptada`
(decisión consciente) deja pasar e inserta. Ver
`PLAN_FASE5_EXTENSIONES.md` §7.1 para el detalle y la evidencia.
Fase 6 (documentación operativa final) también hecha (13-ago-2026):
`docs/migracion/GUIA_OPERATIVA_MIGRACION.md` es el punto de entrada único
para correr una migración real de cliente de principio a fin, con los
comandos exactos y los problemas reales ya encontrados en el camino
(contraseñas mal puestas, ediciones de Excel no guardadas, versión de
Postgres). Con esto las 6 fases de `PLAN_IMPORTACION_EXCEL.md` §2 quedan
completas. El pendiente de agregar al checklist de instalación (IQ) la
verificación de la versión real de Postgres del cliente también se cerró
(13-ago-2026): `docs/calidad/validacion_farma/IQ_CALIFICACION_INSTALACION.md`
ítem IQ-3 nuevo, y el ítem de backup (ahora IQ-12) exige que la corrida
manual de `backup_db.py` haya sido probada, no solo la tarea programada
— no era solo documentación, es un ítem de auditoría con criterio de
aceptación verificable.

## 5. Relación con el Project de claude.ai

Además de vivir en esta carpeta (Cowork), el mismo contexto se replica como
un Project en claude.ai para conversaciones fuera de esta carpeta de
trabajo. Ver `docs/CLAUDE_PROJECT_SETUP.md` para las instrucciones
personalizadas y la lista de archivos a subir como *knowledge*.
