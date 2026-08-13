# Plan de pruebas funcionales / regresión — Fase 2.2

> Entregable de la Fase 2.2 de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §2.2.
> No reordena por alfabeto de router: sigue el **orden de prioridad ya
> propuesto en [`COBERTURA.md`](COBERTURA.md)** ("Siguiente paso: Fase 2.2"),
> que se construyó leyendo el código real de `tests/` y `routers/` — ese
> orden reemplaza al orden original y más genérico que tenía
> `PROJECT_PLAN.md` §2.2, que se escribió antes de conocer el detalle de
> qué faltaba exactamente.
>
> Formalmente, este plan es la Fase 2.2 en sí; su reflejo como protocolo
> GxP vive en
> [`validacion_farma/OQ_CALIFICACION_OPERACIONAL.md`](validacion_farma/OQ_CALIFICACION_OPERACIONAL.md)
> — cada ítem de este documento corresponde a uno o más casos de ese OQ.

## Orden de trabajo (heredado de `COBERTURA.md`, hallazgos #1-#7)

| # | Flujo | Estado | Test(s) |
|---|---|---|---|
| 1 | Aprobación de calibración end-to-end (`POST /analisis/{cid}/aprobar`) | ✅ **Hecho (12-ago-2026)** | `tests/test_flujo_aprobacion_calibracion.py` |
| 2 | RBAC ampliado a los ~34 endpoints de escritura restantes | ✅ **Hecho (12-ago-2026)** | `tests/test_rbac_ampliado.py` |
| 3 | Ciclo de vida de licencia (activa → por vencer → vencida → sin licencia) | ✅ **Hecho (12-ago-2026)** — encontró y corrigió un bug real | `tests/test_ciclo_vida_licencia.py` |
| 4 | Flujo de onboarding completo (equipo → magnitud → ILAC → calibración) | ✅ **Hecho (12-ago-2026)** | `tests/test_flujo_onboarding_equipo.py` |
| 5 | Verificación intermedia con puntos y cierre | ✅ **Hecho (12-ago-2026)** — encontró y corrigió un bug real | `tests/test_flujo_verificacion_intermedia.py` |
| 6 | Mantenimiento (preventivo/correctivo) y su efecto sobre el estado del equipo | ✅ **Hecho (12-ago-2026)** | `tests/test_flujo_mantenimiento.py` |
| 7 | Generación de PDF/Excel (7 endpoints) | ✅ **Hecho (12-ago-2026)** | `tests/test_generacion_pdf_excel.py` |

## 1. Aprobación de calibración end-to-end — ✅ hecho

**Por qué era el #1:** `POST /analisis/{cid}/aprobar` combina el semáforo de
conformidad, la firma electrónica (Ley 527/1999) y el cambio de estado del
equipo — es el evento de negocio central del sistema, y hasta esta sesión
dependía enteramente de pruebas manuales (`COBERTURA.md`, hallazgo #1).

**Qué cubre `tests/test_flujo_aprobacion_calibracion.py` (vía HTTP real,
`TestClient`, no llamadas directas a funciones aisladas):**

- Camino feliz completo: agregar puntos en lote → seleccionar método →
  aprobar con contraseña correcta → verifica que la calibración queda
  `aprobado`, el equipo pasa a `operativo`/`apto_para_uso`/
  `confirmacion_metrologica`, se crea el `HistorialEstado` con el motivo
  correcto, se registra la `FirmaElectronica`, y esa firma queda auditada
  en `registro_auditoria` (equivalente HTTP de OQ-A4/OQ-A9).
- Contraseña incorrecta: no aprueba, no toca el equipo, no crea historial
  (OQ-A4).
- Rol `solo_lectura`: no puede aprobar (OQ-A5, equivalente al patrón ya
  usado en `test_rbac.py` pero para este endpoint específico).
- Reaprobación de una calibración ya aprobada: confirma por HTTP que la
  guardia agregada tras el hallazgo de PQ-7
  (`docs/calidad/PLAN_PRUEBAS_CARGA.md` §7,
  `services/analisis_service.py::aprobar_calibracion`) bloquea el
  reintento — antes de este test, la guardia solo se había verificado
  indirectamente (que `pytest` completo seguía en verde), no con un test
  que la ejerciera directamente por HTTP.

**Qué queda fuera de este ítem, a propósito** (cubierto por otros ítems de
este plan, no duplicado aquí):

- Que el método `lagrange` calcule igual de bien que `regresion` — es
  cálculo puro, ya cubierto por `test_calculos.py`/`test_deriva.py`.
- RBAC de los demás roles (`administrador`, etc.) contra este mismo
  endpoint — se deja para el ítem #2 (RBAC ampliado), que cubre los ~34
  endpoints de escritura de una sola pasada en vez de repetir el patrón
  endpoint por endpoint.
- Generación del PDF de análisis tras la aprobación — ítem #7.

## 2. RBAC ampliado — ✅ hecho

**Por qué era el #2:** el propio `test_rbac.py` original documentaba que
solo 2 de 82 endpoints tenían evidencia HTTP de que el control de rol
aplicara, y que esos 2 eran una muestra de "18 endpoints identificados
como vulnerables antes de la corrección" — dejando sin evidencia
automatizada tanto los otros 16 de esa lista como el resto de las ~34
rutas de escritura del sistema (`COBERTURA.md`, hallazgo #2).

**Hallazgo de la auditoría de código previa a escribir los tests (no
esperado de antemano):** los 36 endpoints de escritura reales que existen
hoy en `routers/` **sí tienen guardia de rol en el código** — no hay
ningún endpoint desprotegido. Lo que faltaba no era la protección en sí
(la corrección de las 18 rutas vulnerables, según el historial de
`test_rbac.py`, ya se había hecho), sino la evidencia automatizada de que
esa protección sigue funcionando y no se rompe con cambios futuros.

**Qué cubre `tests/test_rbac_ampliado.py` (69 tests en el `pytest` completo
del repo tras este ítem, todos en verde):**

- 19 endpoints bloqueados para `solo_lectura` (equipos, magnitudes,
  calibraciones, plan de verificación, verificación intermedia y sus
  puntos, cierre de verificación, mantenimiento, plan de mantenimiento, y
  los 5 métodos de intervalo ILAC: estándar, deriva M1, escalera M4, caja
  negra M2, horas de uso M3) — en cada caso se confirma que la base de
  datos no cambió, no solo que hubo un redirect.
- 5 endpoints exclusivos de administrador (`usuarios/nuevo`,
  `usuarios/{uid}/cambiar-password`, `usuarios/{uid}/toggle-activo`,
  `notificaciones/guardar`, `notificaciones/prueba`,
  `config-lab/guardar`), probados explícitamente con rol `operador` — no
  solo `solo_lectura` — porque `operador` sí puede escribir en casi todo
  el resto del sistema, así que es el caso donde confundir "cualquiera
  que no sea solo_lectura" con "solo administrador" sería más fácil de
  introducir por accidente.
- 2 casos de control ("sí puede"): `administrador` sí puede crear
  usuarios (confirma que la guardia no es demasiado estricta), y ni
  siquiera un `administrador` puede desactivar su propia cuenta (regla de
  negocio distinta del RBAC, ya existente en el código, ahora con
  cobertura).

## 3. Ciclo de vida de licencia — ✅ hecho (encontró un bug real en producción)

**Por qué era el #3:** `COBERTURA.md` hallazgo #5 — "Ciclo de vida de
licencia sin ningún test [...] un bug silencioso aquí puede dejar a un
cliente pagando sin acceso, o con acceso sin haber pagado." Coincide con
OQ-A6 de `OQ_CALIFICACION_OPERACIONAL.md`, marcado ahí como "no hay test
automatizado confirmado, **verificar manualmente**".

**Qué cubre `tests/test_ciclo_vida_licencia.py` (12 tests):** los 4 estados
reales del sistema —sin licencia, vencida (solo lectura), activa, y el
banner "por vencer" (que resultó ser un `if` en `dashboard.html`, visible
solo para `administrador` con ≤30 días, no un estado propio del
middleware)— más el gate del módulo premium `avanzado_ilac`, que usa el
mismo mecanismo de `licencia.py`. Los tests nunca tocan el `licencia.json`
real del proyecto: una fixture redirige `licencia._ARCHIVO` a un archivo
temporal por test.

**Bug real encontrado y corregido (12-ago-2026, `main.py`):**
`RequestLoggingMiddleware` intentaba protegerse de una sesión no
inicializada con `hasattr(request, "session")` — pero la property
`request.session` de Starlette lanza `AssertionError`, no
`AttributeError`, así que `hasattr()` no la atrapaba. El error se
propagaba sin control exactamente cuando `LicenciaMiddleware` corta la
cadena de peticiones *antes* de que `SessionMiddleware` corra — es decir,
justo cuando el sistema intenta redirigir a `/sin-licencia` o
`/licencia-vencida`. Efecto real: en una instalación sin licencia o con
licencia vencida, la primera petición a cualquier página protegida
crasheaba con un 500 sin manejar, en vez de mostrar la pantalla de aviso.
Corregido cambiando el chequeo a `"session" in request.scope` (una
comprobación de diccionario, no una property que puede lanzar). Validado
con los 4 tests que antes fallaban y ahora pasan
(`test_sin_licencia_redirige_rutas_protegidas`,
`test_sin_licencia_responde_403_json_si_accept_json`,
`test_licencia_vencida_bloquea_escritura_y_no_crea_el_registro`,
`test_licencia_vencida_responde_403_json_en_escritura_si_accept_json`) y
con `pytest tests/ -v` completo (82/82).

**Recomendación operativa:** vale la pena revisar si alguna instalación de
cliente reportó pantallas en blanco o errores al vencer su licencia —
este bug pudo ser la causa, y hasta ahora no había forma de saberlo sin
una prueba automatizada que lo disparara.

## 4. Flujo de onboarding completo — ✅ hecho

**Por qué era el #4:** el flujo insignia del sistema —"equipo → magnitud
→ evaluación ILAC → calibración"— es literalmente cómo empieza la vida
de cada equipo en MetroGest, y ninguno de los 4 pasos tenía un test que
los recorriera encadenados (cada uno se probaba, si acaso, aislado).

**Qué cubre `tests/test_flujo_onboarding_equipo.py` (5 tests):** el
camino feliz completo verificando que cada paso deja el dato correcto Y
enlazado al siguiente (mismo `equipo_id`/`magnitud_id` de punta a punta,
incluyendo que el intervalo sugerido con los 14 factores ILAC en su valor
por defecto da 12 meses también a nivel de endpoint HTTP con firma
electrónica real, no solo como función pura ya cubierta en
`test_calculos.py`). Más las dos reglas de negocio del paso ILAC (§5.1)
que no tenían ningún test: bloqueo si el intervalo adoptado supera al
sugerido sin justificación explícita, y la protección contra
reediciones accidentales de una evaluación ya guardada (exige
`confirmar_edicion=si` explícito, si no el submit se ignora silenciosamente
salvo por el redirect de aviso).

## 5. Verificación intermedia con puntos y cierre — ✅ hecho (encontró un bug real)

**Por qué era el #5:** ciclo completo "plan → registro de puntos → cierre
con acción correctiva" sin ningún test antes de este archivo. También
cerraba explícitamente el gap OQ-B2 de
`OQ_CALIFICACION_OPERACIONAL.md`: "desviación entre umbral de alerta y
umbral fuera de tolerancia -> resultado = alerta, ninguna cobertura
identificada".

**Qué cubre `tests/test_flujo_verificacion_intermedia.py` (6 tests):** el
camino feliz completo (plan → nueva verificación → puntos en lote →
cierre con firma electrónica), los 3 umbrales de `resultado` (ok/alerta/
reprobado, incluyendo que un solo punto "fuera" entre varios "ok" reprueba
toda la verificación — no se promedia), y un challenge test de firma
(contraseña incorrecta no guarda la acción tomada).

**Bug real encontrado y corregido (`services/verificaciones_service.py`):**
`eliminar_punto` marcaba el punto como eliminado pero nunca recalculaba
el campo agregado `resultado` de la verificación — a diferencia de
`agregar_punto`/`agregar_puntos_lote`, que sí lo hacen. Si el punto
eliminado era el único "fuera" o "alerta", la verificación quedaba
marcada con ese resultado indefinidamente, aunque los puntos restantes
estuvieran todos dentro de tolerancia. Corregido agregando la misma
llamada a `recalcular_resultado_verificacion` que ya usan las otras dos
funciones. Validado con `test_eliminar_el_unico_punto_fuera_recalcula_el_resultado`
y con `pytest tests/ -v` completo (93/93).

**Segundo hallazgo, confirmado con Edison (12-ago-2026) y corregido en el
mismo cambio:** `POST /verificaciones/{vid}/cerrar` no tenía guardia
contra re-cierre — mismo patrón que tenía `POST /analisis/{cid}/aprobar`
antes del hallazgo de PQ-7 (`PLAN_PRUEBAS_CARGA.md` §7); la plantilla
siempre muestra el formulario de cierre, sin ocultarlo cuando
`accion_tomada` ya está definido. Se agregó la misma guardia en
`services/verificaciones_service.py::cerrar_verificacion`, validada con
`test_recerrar_una_verificacion_ya_cerrada_es_rechazada_por_http` y con
`pytest tests/ -v` completo.

## 6. Mantenimiento — ✅ hecho

**Por qué era el #6:** `COBERTURA.md` — "Afecta el estado del equipo vía
`requiere_calibracion`/`afecta_medicion`, sin verificación automatizada."

**Qué cubre `tests/test_flujo_mantenimiento.py` (4 tests):** el efecto de
`requiere_calibracion=true` sobre el estado del equipo (pasa a
"en_mantenimiento" con su `HistorialEstado`), que un mantenimiento sin esa
bandera no toca el estado, y una regla de negocio no documentada antes en
ningún sitio (confirmada leyendo el código, no asumida): la transición a
"en_mantenimiento" solo aplica si el equipo estaba "operativo" en ese
momento — si venía de cualquier otro estado, el mantenimiento se registra
igual pero el estado no cambia. También el upsert del plan de
mantenimiento preventivo (crear + actualizar sin duplicar filas).

## 7. Generación de PDF/Excel — ✅ hecho (Fase 2.2 completa)

**Por qué era el #7:** `COBERTURA.md` — "Cero cobertura de generación de
PDF/Excel (7 endpoints)". Coincide con un riesgo ya identificado en
`PLAN_PRUEBAS_CARGA.md` §6 (ReportLab/openpyxl síncronos) — no solo
faltaba medir su rendimiento (ya cubierto en la Fase 2.3), faltaba una
red de seguridad funcional si un cambio de datos rompe un layout fijo.

**Qué cubre `tests/test_generacion_pdf_excel.py` (7 tests):** no se probó
cada uno de los ~14 endpoints reales que generan documentos (más de los 7
que estimaba `COBERTURA.md`) uno por uno — se priorizaron los dos riesgos
concretos: (1) los que pasan por el `ProcessPoolExecutor` compartido de
ADR-001 (`dashboard/pdf`, `dashboard/excel`, `analisis/{cid}/pdf`) —
primera vez que ese mecanismo se ejercita dentro de `pytest` (antes solo
se había probado vía Uvicorn real en la Fase 2.3) y funcionó sin
problemas; (2) que las exportaciones del dashboard respeten el mismo gate
de licencia que la escritura de datos (`puede_escribir()`), un detalle
fácil de pasar por alto porque técnicamente son peticiones GET. El resto
de generadores síncronos se cubre con un representante (PDF de ILAC) más
el caso 404 cuando falta el dato que el PDF necesita.

**Con esto la Fase 2.2 (`docs/PROJECT_PLAN.md` §2.2) queda completa: 7 de
7 ítems, 105 tests nuevos en total repartidos en 6 archivos, más 2 bugs
reales encontrados y corregidos** (reaprobación de calibraciones sin
guardia — Fase 2.3/PQ-7; recálculo de resultado tras eliminar un punto de
verificación — este documento ítem 5) **y un tercero** (crash 500 al
redirigir por licencia vencida/faltante — este documento ítem 3). Todo
validado con `pytest tests/ -v` en verde (105/105) en cada paso.

Se detallan (casos de prueba concretos, no solo el título) a medida que se
empieza cada uno — mantenerlos como títulos vacíos aquí sería redundante
con la matriz de `COBERTURA.md` y se desincronizaría igual que le pasó a
`GUIA_PROYECTO.md` (ver `CLAUDE.md` §6). Cada ítem, al completarse, se
documenta con el mismo nivel de detalle que los ítems 1 y 2 arriba.
