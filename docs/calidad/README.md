# Documentación de calidad y pruebas — Pendiente

Ver **Línea 2** de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) — esta es la
línea de trabajo prioritaria: responde si el sistema soporta el objetivo de
negocio de ~1,600 equipos y 10-20 usuarios concurrentes.

Entregables en esta carpeta:

- [`COBERTURA.md`](COBERTURA.md) — **completo**: matriz de 82 endpoints × ¿tiene
  test HTTP real? (Fase 2.1). Hallazgo principal: solo 3 endpoints tienen
  cobertura HTTP directa; ningún flujo de negocio completo (aprobación de
  calibración, RBAC ampliado, ciclo de vida de licencia) tiene test de
  integración. Define el orden de prioridad para la Fase 2.2.
- `PLAN_PRUEBAS_FUNCIONALES.md` — plan de pruebas de regresión priorizado por flujo crítico (Fase 2.2) — **pendiente**, orden ya definido en `COBERTURA.md`
- [`PLAN_PRUEBAS_CARGA.md`](PLAN_PRUEBAS_CARGA.md) — plan y resultados de la prueba de carga/concurrencia a escala objetivo (Fase 2.3) — **secciones 1-6 completas** (herramienta, dataset, escenarios, riesgos de arquitectura); secciones 7-8 (ejecución y resultados) pendientes del runbook que ejecuta Edison
- **[`validacion_farma/`](validacion_farma/README.md)** — **ya iniciado**: paquete de Validación de Sistemas Computarizados (CSV) para clientes de industria farmacéutica — Plan Maestro de Validación, gap analysis regulatorio (INVIMA/21 CFR Part 11/EU Annex 11) contra el código real, y protocolos formales IQ/OQ/PQ. Reemplaza y profundiza el `CHECKLIST_SEGURIDAD.md` que se había planeado en la Fase 2.4.
