# Protocolo de Calificación de Desempeño (PQ) — MetroGest v2

> Confirma que el sistema sostiene el desempeño esperado bajo condiciones
> realistas de uso — volumen de datos y concurrencia — no solo que cada
> función individual funciona (eso ya lo cubrió el OQ). **Este protocolo
> depende directamente de la Fase 2.3 de `../../PROJECT_PLAN.md`** (plan
> de pruebas de carga): no se duplica el trabajo, el PQ es el empaque
> formal de esos mismos resultados como evidencia de validación.

**Instalación evaluada:** _____________________ **Fecha:** _____________
**Ejecutado por:** _____________________ **Revisado por:** _____________

## 1. Prerrequisito

Este PQ **no puede ejecutarse** hasta que la Fase 2.3 del plan de calidad
general produzca resultados reales de la prueba de carga. Este documento
define de antemano *cómo* se van a leer esos resultados como evidencia de
validación — para no improvisar los criterios de aceptación después de
ver los números (eso invalidaría la prueba como evidencia objetiva).

## 2. Escenario de prueba (heredado de PROJECT_PLAN.md §2.3)

- Volumen de datos: ~1,600 equipos, con historial de calibraciones/
  verificaciones acumulado realista.
- Concurrencia: 10-20 usuarios simultáneos, mezcla real de navegación y
  escritura (aprobaciones, firmas, generación de PDF).
- Entorno: staging o BD de prueba dedicada — **nunca** la base de datos de
  producción de un cliente real.

## 3. Criterios de aceptación (a confirmar con el usuario antes de ejecutar la prueba)

| # | Métrica | Criterio de aceptación propuesto | Resultado obtenido | ¿Cumple? |
|---|---|---|---|---|
| PQ-1 | Tiempo de respuesta del listado de equipos paginado (1,600 equipos cargados) | < 2 segundos con 15 usuarios concurrentes navegando | | ☐ Sí ☐ No |
| PQ-2 | Tiempo de respuesta del dashboard | < 2 segundos en las mismas condiciones | | ☐ Sí ☐ No |
| PQ-3 | Tiempo de generación de un PDF de análisis bajo carga concurrente | < 5 segundos, sin bloquear otras solicitudes simultáneas | | ☐ Sí ☐ No |
| PQ-4 | Tasa de error HTTP 5xx durante la prueba sostenida | 0% — cualquier error 500 durante la prueba de carga es una desviación a investigar, no un "resultado esperado" | | ☐ Sí ☐ No |
| PQ-5 | Comportamiento de la base de datos ante escrituras concurrentes (aprobaciones, firmas) | Sin bloqueos (deadlocks) ni pérdida de datos; cada escritura queda íntegra y auditada | | ☐ Sí ☐ No |
| PQ-6 | Uso de memoria/CPU del proceso bajo carga sostenida | Sin crecimiento no acotado de memoria (posible fuga) durante la duración de la prueba | | ☐ Sí ☐ No |
| PQ-7 | Integridad del rastro de auditoría bajo carga | El número de filas nuevas en `registro_auditoria` coincide exactamente con el número de operaciones de escritura ejecutadas por el script de carga (sin pérdidas) | | ☐ Sí ☐ No |

> Los valores numéricos de esta tabla son una propuesta inicial razonable,
> no un compromiso — deben confirmarse con Edison (y, si aplica, con el
> cliente) antes de ejecutar la prueba, porque son ellos quienes se comprometen
> con estas cifras frente a un tercero.

## 4. Evidencia a recolectar

- Resultados crudos de la herramienta de carga (locust/k6 — a decidir en
  la Fase 2.3), exportados y anexados.
- Capturas o export de `logs/app.log` durante la ventana de la prueba.
- Consulta de conteo de filas en `registro_auditoria` antes/después.
- Métricas de sistema (CPU/memoria) del proceso Uvicorn durante la prueba.

## 5. Conclusión

☐ PQ **aprobado** — el sistema sostiene el desempeño requerido a la escala objetivo (1,600 equipos / 10-20 usuarios concurrentes)
☐ Aprobado con desviaciones documentadas y plan de remediación
☐ No aprobado — requiere optimización antes de aceptarse como validado a esta escala

Firma ejecutor: _____________ Firma revisor: _____________ Fecha: _______
