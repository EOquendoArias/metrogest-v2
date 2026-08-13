# Documentación para clientes — Hecho (12-ago-2026)

Ver **Línea 3** de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md).

Tres documentos separados, para tres audiencias:

- [`RESUMEN_EJECUTIVO.md`](RESUMEN_EJECUTIVO.md) — para el decisor de
  negocio del cliente (corto, sin jerga técnica).
- [`ANEXO_TECNICO.md`](ANEXO_TECNICO.md) — para el equipo técnico/TI del
  cliente o un auditor: arquitectura, seguridad, suite de pruebas,
  capacidad soportada con evidencia real de la prueba de carga (1,600
  equipos / 15-20 usuarios), respaldo/recuperación, y estado honesto del
  paquete de validación GxP (PQ cerrado y aprobado; IQ/OQ con protocolo
  listo pero pendientes de ejecutar por instalación).
- [`GUIA_PREPARACION_DATOS.md`](GUIA_PREPARACION_DATOS.md) — para quien en
  el cliente reúne la información histórica (gerente de calidad,
  metrólogo): checklist de qué organizar antes de entregarla, y cómo es el
  proceso de migración en términos simples. Derivado del checklist técnico
  de `docs/migracion/GUIA_VALIDACION_Y_DESVIACIONES.md` §2, sin
  tecnicismos ni el detalle de severidades/registro que sí ve Edison — esa
  parte del proceso de migración es deliberadamente interna (ver
  `docs/migracion/README.md`).

Los dos primeros se redactaron **después** de que la Línea 2
(calidad/carga) produjera resultados reales — cada afirmación del anexo
técnico cita el documento fuente donde se puede verificar la evidencia, no
es una promesa de diseño. El tercero se redactó después de verificar
`importar_excel.py` contra Postgres real y de documentar la receta de
Power Query (ver `docs/migracion/PLAN_IMPORTACION_EXCEL.md` §9-§10 y
`RECETA_POWER_QUERY.md`) — mismo criterio: no prometer un proceso que
todavía no existía en código.
