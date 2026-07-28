# Análisis de brechas — Integridad de datos y validación (INVIMA / 21 CFR Part 11 / EU Annex 11)

> A diferencia de `PLAN_MAESTRO_VALIDACION.md` (que es un marco a llenar),
> este documento sí está basado en una lectura real del código actual
> (`auth.py`, `models.py`, `utils/auditoria_trail.py`, `utils/firma_electronica.py`,
> `backup_db.py`, `tests/`) al 2026-07-28. Léase como punto de partida real,
> no como un checklist ya cumplido — varios ítems están marcados
> explícitamente como "por verificar" porque no se leyó el código fuente
> completo del módulo en cuestión durante esta sesión, para no afirmar más
> de lo que se comprobó.

**Leyenda:** ✅ implementado y evidenciado · ⚠️ implementado parcialmente o
requiere verificación/ajuste · 🔴 no implementado — brecha real

Los tres marcos (INVIMA/ISO, 21 CFR Part 11, EU Annex 11) comparten una
base común de integridad de datos (principios ALCOA+: Atribuible, Legible,
Contemporáneo, Original, Exacto, + Completo, Consistente, Perdurable,
Disponible). La tabla usa esa base común; las diferencias específicas por
marco están en `ANEXOS_MARCOS.md`.

| # | Requisito (base común ALCOA+ / GxP) | Estado | Evidencia en el código | Brecha / acción pendiente |
|---|---|---|---|---|
| 1 | Identificación única de usuario, sin cuentas compartidas | ✅ / ⚠️ | `Usuario.email` único, login individual (`auth.py`) | El control técnico de unicidad existe; que nadie *comparta* una cuenta ya creada es procedimental del cliente, no técnico — documentar como requisito de uso, no del software |
| 2 | Control de acceso por rol, privilegio mínimo | ✅ | Roles `administrador`/`operador`/`solo_lectura`, probado en `tests/test_rbac.py` | Ninguna conocida |
| 3 | Autenticación robusta, protección contra fuerza bruta | ✅ | bcrypt, bloqueo por (email+ip) y por ip global, probado en `tests/test_auth.py` | Ninguna conocida |
| 4 | Rastro de auditoría automático, con fecha/hora, usuario, y valor anterior/nuevo | ✅ / ⚠️ | `RegistroAuditoria` + `utils/auditoria_trail.py` (listeners `before_flush`/`after_flush`), probado en `tests/test_auditoria_trail.py` | **Verificar alcance exacto:** confirmar qué tablas están efectivamente cubiertas por el listener (no se leyó `utils/auditoria_trail.py` completo en esta sesión) — un auditor preguntará explícitamente "¿qué tablas NO están auditadas y por qué?" |
| 5 | Registros no eliminables físicamente sin dejar rastro (soft-delete) | ✅ / ⚠️ | `PuntoCalibracion` y `PuntoVerificacion` tienen `eliminado`/`eliminado_en`/`eliminado_por_id` | Verificar si `Calibracion`, `VerificacionIntermedia` y `Mantenimiento` (los registros "padre", no solo sus puntos) tienen la misma protección o si algún router permite `DELETE` físico — revisar `routers/calibraciones.py`, `routers/verificaciones.py`, `routers/mantenimientos.py` |
| 6 | Firma electrónica: identifica al firmante, no reutilizable, incluye nombre impreso + fecha/hora + significado del acto firmado | ✅ | `FirmaElectronica` (nombre snapshot, significado, fecha server-side, ip), reautenticación con password en `utils/firma_electronica.py`, probado en `tests/test_firma_electronica.py` | Confirmar la lista completa de los "4 puntos críticos" donde se usa hoy (CLAUDE.md los menciona pero no los enumera) y compararla contra los actos que el cliente considera "decisiones de calidad" — puede que falten puntos |
| 7 | Vínculo entre la firma y el contenido exacto firmado (que no se pueda alterar el registro después sin invalidar la firma) | ⚠️ | El vínculo hoy es por `tabla` + `registro_id`, no por un hash del contenido en el momento de firmar | Brecha real de robustez frente a 21 CFR 11.70 en su interpretación más estricta — considerar agregar un hash SHA-256 del contenido relevante al momento de la firma como evidencia adicional (el rastro de auditoría #4 mitiga parcialmente, pero no es lo mismo) |
| 8 | Marca de tiempo generada por el servidor, no editable por el usuario | ✅ | `server_default=func.now()` en los modelos de auditoría y firma | Ninguna conocida |
| 9 | Copias exactas y completas de los registros, legibles en papel/pantalla | ✅ | Exportación PDF (ReportLab) y Excel (openpyxl) de análisis, verificación, mantenimiento, dashboard | Ninguna conocida |
| 10 | Backup periódico con recuperación verificada | ✅ | `backup_db.py`: `pg_dump` + restauración de prueba contra BD temporal, comparación de conteos de filas | Ninguna conocida a nivel de mecanismo |
| 11 | Política de retención de datos alineada al marco regulatorio del cliente | ⚠️ | `BACKUP_RETENCION_DIAS` controla cuánto se guardan los *archivos* de respaldo | Eso no es lo mismo que la retención regulatoria de los *datos* (algunos marcos exigen conservar registros de calibración años después de retirado el equipo) — falta definir esta política explícitamente, probablemente por cliente |
| 12 | Revisión periódica de accesos (roles vigentes, cuentas inactivas) | ⚠️ | `routers/usuarios.py` permite activar/desactivar y listar | Funcionalidad existe; falta un reporte o recordatorio que *fuerce* la revisión periódica — hoy depende de que alguien se acuerde de hacerlo |
| 13 | Control de cambios documentado del software (qué cambió, quién lo aprobó, cuándo) | ⚠️ | `git log`, migraciones de Alembic | Sirve como bitácora técnica, pero no es un procedimiento de control de cambios formal con aprobación previa al despliegue — pendiente en `PLAN_MAESTRO_VALIDACION.md` §6 |
| 14 | Ambiente de pruebas separado de producción (nunca probar contra datos reales) | ✅ | `tests/conftest.py` usa una BD `..._test` dedicada, nunca la real | Ninguna conocida |
| 15 | Especificación funcional documentada por módulo (base para decir si una prueba "pasa") | ⚠️ | Docstrings en el código, `GUIA_PROYECTO.md` (desactualizado, no confiable) | Falta una especificación funcional formal — se recomienda producirla en la Fase 1.1 (`docs/arquitectura/ARQUITECTURA.md`) antes de redactar el detalle fino del OQ |
| 16 | Validación documentada del propio sistema (IQ/OQ/PQ ejecutados y aprobados) | 🔴 | — | Es justamente el trabajo que arranca con este paquete — no existía antes de esta sesión |

## Resumen para el usuario

La base técnica es sólida — control de acceso, autenticación, rastro de
auditoría y firma electrónica ya existen y están probados, no hay que
construirlos desde cero. Las brechas reales que vale la pena resolver
**antes** de mostrarle este paquete a un cliente farmacéutico exigente son
los ítems **5** (confirmar soft-delete en registros padre, no solo en
puntos), **7** (vínculo criptográfico firma-contenido) y **16** (ejecutar
de verdad el IQ/OQ/PQ). El resto son ajustes de documentación/proceso, no
de código.
