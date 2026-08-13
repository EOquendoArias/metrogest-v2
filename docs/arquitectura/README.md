# Documentación de arquitectura

Ver **Línea 1** de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md).

Entregables de esta carpeta:

- `DECISIONES.md` — registro de decisiones de diseño clave, formato ADR
  corto (Fase 1.2). **Hecho** (12-ago-2026): contiene ADR-001, con el
  problema real detectado en la Fase 2.3 (PDF/Excel bloqueando todos los
  usuarios con un solo proceso), las opciones consideradas, la decisión
  (`ProcessPoolExecutor` + `UVICORN_WORKERS`) y los resultados medidos en
  4 corridas de carga. Otros candidatos a ADR mencionados en
  `PROJECT_PLAN.md` §1.2 (por qué Postgres y no SQLite, por qué Alembic,
  por qué firma electrónica simple y no PKI, por qué HMAC propio para
  licencias) todavía no tienen su propia entrada — se documentan cuando
  se retome esta línea.
- `ARQUITECTURA.md` — diagrama y descripción de la arquitectura actual
  (Fase 1.1). **Hecho** (12-ago-2026): capas (routers/services parcial/
  utils), orden real de los 6 middlewares con la advertencia de diseño de
  `RequestLoggingMiddleware` vs `SessionMiddleware` (§3.2 del documento),
  modelo de datos (20 tablas agrupadas por dominio, patrones de
  soft-delete y auditoría automática), y el patrón `ProcessPoolExecutor`
  de ADR-001 resumido y enlazado.

Se escriben después de la Línea 2 (pruebas de calidad y carga), para que
describan la arquitectura ya validada a escala y no solo la intención de
diseño — por eso `DECISIONES.md` ya pudo escribirse con datos medidos en
vez de supuestos.
