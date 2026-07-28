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
- Ya se hizo, como respuesta directa a esto: migración SQLite → PostgreSQL,
  endurecimiento de seguridad completo (ver `CLAUDE.md` §5), paginación y
  caché del dashboard, backups automáticos con restauración probada,
  infraestructura de pruebas + CI.
- Lo que **falta** para poder decir con evidencia "esto soporta 1,600
  equipos / 10-20 usuarios" es una prueba de carga real — eso es el centro
  de la Línea 2 (§2.3).

## 1. Línea 1 — Documentación técnica (`docs/arquitectura/`)

| Fase | Entregable | Contenido |
|---|---|---|
| 1.1 | `docs/arquitectura/ARQUITECTURA.md` | Diagrama y descripción de la arquitectura actual: FastAPI + Jinja2 SSR + PostgreSQL, capa de routers vs. capa de servicios (`services/`, aún parcial), middlewares en orden real (auditoría → cabeceras de seguridad → forzar cambio de password → sesión → licencia → logging de requests), esquema de BD (18 tablas, relaciones clave). |
| 1.2 | `docs/arquitectura/DECISIONES.md` | Registro de decisiones de diseño relevantes (formato tipo ADR corto): por qué Postgres y no seguir en SQLite, por qué Alembic, por qué firma electrónica simple y no PKI, por qué HMAC propio para licencias en vez de un proveedor externo. Sirve para no repetir discusiones ni revertir decisiones por accidente. |
| 1.3 | Runbook operativo | Ya cubierto en buena parte por `README.md` (instalación, arranque, backup, recuperación de contraseña). Esta fase es solo *completar huecos* si aparecen durante la Línea 2 (ej. qué hacer si falla una migración en producción del cliente). |

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

### 2.4 Checklist de seguridad recurrente

`docs/calidad/CHECKLIST_SEGURIDAD.md` — convierte las 6 brechas ya cerradas
(`CLAUDE.md` §5) en una checklist de auditoría periódica (ej. antes de cada
entrega a un nuevo cliente), para no depender de la memoria de una sesión
de Claude puntual.

## 3. Línea 3 — Documentación para clientes (`docs/cliente/`)

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
2. Línea 2, fase 2.1 — inventario de cobertura (rápido, ya hay mucho hecho)
3. Línea 2, fase 2.3 — plan y ejecución de prueba de carga (es la que
   responde la pregunta de negocio que motivó todo esto)
4. Línea 1 completa (arquitectura + decisiones) — más fácil de escribir bien
   una vez que la prueba de carga confirma o corrige supuestos de diseño
5. Línea 3 (documentos de cliente) — al final, para que cite datos reales
   en vez de promesas

## 5. Relación con el Project de claude.ai

Además de vivir en esta carpeta (Cowork), el mismo contexto se replica como
un Project en claude.ai para conversaciones fuera de esta carpeta de
trabajo. Ver `docs/CLAUDE_PROJECT_SETUP.md` para las instrucciones
personalizadas y la lista de archivos a subir como *knowledge*.
