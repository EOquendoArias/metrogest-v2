# Cobertura de pruebas automatizadas — Fase 2.1

> Entregable de la Fase 2.1 de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §2.1.
> Matriz flujo-de-negocio × ¿tiene test?, construida leyendo el código real de
> `tests/` (7 archivos) y `routers/` (16 archivos, 82 endpoints), no a partir
> de descripciones previas. Alimenta directamente
> [`validacion_farma/OQ_CALIFICACION_OPERACIONAL.md`](validacion_farma/OQ_CALIFICACION_OPERACIONAL.md),
> que reformatea la Fase 2.2 (plan de pruebas funcionales) como protocolo
> formal — por eso el orden de prioridad que sugiere este documento debería
> guiar el orden de la Fase 2.2.

## Metodología

- Se leyeron los 7 archivos de `tests/` completos (no solo sus docstrings).
- Se contaron los endpoints reales de cada router con
  `@router.get/post/put/delete(...)` — 82 endpoints en 16 routers (3 routers,
  `notificaciones.py`, `registro_auditoria.py` y `busqueda.py`, ni siquiera
  aparecen documentados en `README.md`).
- "Cobertura HTTP directa" = existe un test que pasa por `TestClient` (fixture
  `client` de `conftest.py`): sesión real, middleware real, parseo de
  formulario real, render de plantilla real.
- "Cobertura indirecta" = existe un test de la función/servicio que el
  endpoint invoca, pero llamado directamente en Python, sin pasar por el
  router, el formulario ni la plantilla.
- Un endpoint sin ninguna de las dos queda como **sin cobertura**.

## Resumen ejecutivo

- **82 endpoints, 16 routers. De esos, solo 3 tienen algún test que pase por
  HTTP real** (`POST /analisis/{cid}/metodo`, `POST /ilac/riesgo/{mid}`,
  `GET /dashboard/`) — el resto de la superficie HTTP de la aplicación nunca
  se ha ejecutado desde un test automatizado.
- Las funciones de cálculo puro (semáforo, regresión, deriva M1) sí están
  bien cubiertas, pero son una fracción pequeña del código: no prueban que el
  formulario que las alimenta, ni el endpoint que las llama, ni la plantilla
  que muestra el resultado, funcionen.
- **Ningún flujo de negocio de principio a fin** (alta de equipo → magnitud →
  ILAC → calibración → aprobación) tiene un test de integración. Lo que
  existe hoy prueba piezas aisladas.
- RBAC HTTP-level se verificó en 2 de 82 endpoints — y el propio
  `test_rbac.py` documenta que esos 2 eran solo una muestra de "18 endpoints
  que estaban desprotegidos antes de la corrección". Los otros 16 (y los ~30
  endpoints POST adicionales que no estaban en esa lista) no tienen evidencia
  automatizada de que el control de rol aplique ahí.
- **Cero cobertura de generación de PDF/Excel** (7 endpoints) y **cero
  cobertura del ciclo de vida de licencia** (activa/por vencer/vencida/sin
  licencia) — este último ni siquiera aparece en ninguno de los 7 archivos de
  test.

## Matriz por módulo

| Módulo (router) | Endpoints | Cobertura HTTP directa | Cobertura indirecta | Prioridad | Notas |
|---|---|---|---|---|---|
| `usuarios` | 9 | `POST /login` solo camino exitoso (helper `_login` reusado por otros tests, no es un test de login en sí) | Rate-limiting y hash de password ✅ (`test_auth.py`, a nivel de función `auth.py`, no vía HTTP) | **Alta** | Sin cobertura: cambio de password obligatorio en primer login, creación de usuario, cambio de password de otro usuario, toggle-activo, logout, ni el camino de login fallido a nivel HTTP |
| `equipos` | 6 | Ninguna | Ninguna | **Alta** | Es el punto de entrada de todo el sistema (alta de equipo) y el listado paginado es central para la Fase 2.3 (carga) |
| `magnitudes` | 6 | Ninguna | Ninguna | **Alta** | Paso 2 del flujo de onboarding (README, "Flujo de trabajo típico") |
| `calibraciones` | 3 | Ninguna | `test_deriva.py` crea `Calibracion`/`PuntoCalibracion` directo en BD, no vía `POST /magnitud/{mid}/nueva` | **Alta** | No hay evidencia de que el formulario de registro de calibración realmente funcione |
| `analisis` | 8 | `POST /metodo` (2 tests: bloqueo `solo_lectura` + permiso `operador`) | Semáforo y regresión ✅ (`test_calculos.py`, funciones puras); `verificar_y_firmar` ✅ (`test_firma_electronica.py`, aislado) | **Crítica** | `POST /aprobar` — el evento de negocio más importante del sistema (semáforo + firma electrónica + cambio de estado) — no tiene ningún test, ni parcial. Tampoco `punto`, `puntos/lote`, `punto/eliminar`, `regresion`, `pdf` |
| `verificaciones` | 11 | Ninguna | Ninguna (deriva se prueba con objetos creados a mano, no vía este router) | **Alta** | Ciclo completo (plan → registro de puntos → cierre con acción correctiva) sin ningún test |
| `mantenimientos` + `plan_mantenimiento` | 7 | Ninguna | Ninguna | **Media-alta** | Afecta el estado del equipo vía `requiere_calibracion`/`afecta_medicion`, sin verificación automatizada |
| `ilac` | 17 | `POST /riesgo/{mid}` (1 test: solo bloqueo `solo_lectura`, no se prueba que `operador` sí pueda guardar) | `calcular_intervalo_inicial` ✅, `analizar_deriva` ✅ (funciones puras) | **Alta** | El router más grande (17 endpoints) y el más regulado (GxP): 16 de 17 endpoints sin cobertura — periodo, escalera, caja negra, horas, y los 4 PDF de cada método |
| `dashboard` | 3 | `GET /` solo el caso sin sesión (redirect a login) | Ninguna | **Crítica para Fase 2.3** | Es el endpoint más visitado en la mezcla de tareas ya diseñada en `PLAN_PRUEBAS_CARGA.md` §7; no hay test con sesión válida, con datos reales, ni de la caché de 60s |
| `calendario` | 1 | Ninguna | Ninguna | Baja | — |
| `config_lab` | 2 | Ninguna | Ninguna | Media | Un error aquí se propaga a los encabezados de todos los PDFs del sistema |
| `auditoria` | 3 | Ninguna | El *dato* subyacente sí está probado (`test_auditoria_trail.py`), pero no la vista/exportación de este router | Media | — |
| `registro_auditoria` | 2 | Ninguna | Igual que arriba: datos probados, vista no | Baja | No documentado en `README.md` |
| `notificaciones` | 3 | Ninguna | Ninguna | Media | No documentado en `README.md`; según el roadmap parece ser funcionalidad de v2.2 |
| `busqueda` | 1 | Ninguna | Ninguna | Baja | No documentado en `README.md` |
| `licencia.py` (módulo + middleware, no es router) | — | Ninguna | Ninguna | **Alta** | Ciclo activa → por vencer → vencida → sin licencia sin ningún test automatizado — es literalmente el mecanismo de cobro |

## Hallazgos clave (orden sugerido de prioridad)

1. **La aprobación de calibración no tiene ningún test.** `POST
   /analisis/{cid}/aprobar` combina el semáforo de conformidad, la firma
   electrónica y el cambio de estado del equipo — es el evento de negocio
   central del sistema y hoy depende enteramente de pruebas manuales.
2. **RBAC solo se verificó en 2 de 82 endpoints.** El propio `test_rbac.py`
   documenta que eran una muestra de 18 endpoints identificados como
   vulnerables; los otros 16, más el resto de las ~34 rutas de escritura,
   no tienen evidencia automatizada de que el control de rol aplique. Esto
   es particularmente relevante para el paquete de validación farmacéutica
   (`validacion_farma/GAP_ANALISIS_REGULATORIO.md`).
3. **Ningún flujo de negocio completo tiene test de integración.** Todo lo
   que existe prueba piezas aisladas (funciones puras o mecanismos genéricos
   como auditoría/firma) — nunca el camino real que sigue un usuario en el
   navegador, de principio a fin.
4. **Cero cobertura de PDF/Excel** (7 endpoints). Coincide con un riesgo ya
   identificado en `PLAN_PRUEBAS_CARGA.md` §6 (ReportLab/openpyxl síncronos
   en el único worker de Uvicorn) — no solo falta medir su rendimiento, falta
   una red de seguridad funcional si un cambio de datos rompe un layout fijo.
5. **Ciclo de vida de licencia sin ningún test.** Afecta directamente la
   facturación: un bug silencioso aquí puede dejar a un cliente pagando sin
   acceso, o con acceso sin haber pagado.
6. **Deuda de documentación además de deuda de pruebas.** `notificaciones.py`,
   `registro_auditoria.py` y `busqueda.py` no aparecen en `README.md` —
   vale la pena una pasada corta de documentación junto con la Fase 2.2, no
   solo pruebas.
   **Resuelto (12-ago-2026):** los 3 routers ya están documentados en la
   tabla "Módulos principales" y en el árbol de archivos de `README.md`,
   junto con el conteo real de tablas ORM (20, no 14) y de plantillas (35,
   no 25) que también estaban desactualizados. Sigue pendiente lo que no es
   documentación: RBAC ampliado de estos 3 routers a nivel de test HTTP (ya
   cubierto para `notificaciones` en `tests/test_rbac_ampliado.py`; falta
   `registro_auditoria` y `busqueda`).

## Relación con lo que ya existe en `docs/calidad/`

- Este documento resuelve el placeholder que `docs/calidad/README.md` tenía
  para la Fase 2.1.
- No compite con `validacion_farma/GAP_ANALISIS_REGULATORIO.md` (que ya cubre
  el lado normativo/GxP contra el código): este documento es el lado técnico
  — "¿existe un test automatizado?" — y sirve de insumo para that gap
  analysis, especialmente en el punto de RBAC (hallazgo #2).
- Alimenta directamente `validacion_farma/OQ_CALIFICACION_OPERACIONAL.md`,
  que reformatea la Fase 2.2 como protocolo formal.

## Siguiente paso: Fase 2.2 (`PLAN_PRUEBAS_FUNCIONALES.md`)

Orden sugerido según los hallazgos de arriba, no por orden alfabético de
router (mismo criterio que ya proponía `PROJECT_PLAN.md` §2.2):

1. Aprobación de calibración end-to-end (hallazgo #1) — es el mayor riesgo.
2. RBAC ampliado a los ~34 endpoints de escritura restantes (hallazgo #2).
3. Ciclo de vida de licencia (hallazgo #5) — bloquea o desbloquea todo el
   sistema si falla, tiene prioridad sobre generación de documentos.
4. Flujo de onboarding completo (equipo → magnitud → ILAC → calibración).
5. Verificación intermedia con puntos y cierre.
6. Mantenimiento y su efecto sobre el estado del equipo.
7. Generación de PDF/Excel (hallazgo #4).
