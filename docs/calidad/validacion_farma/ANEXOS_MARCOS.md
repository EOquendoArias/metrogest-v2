# Anexos por marco regulatorio — diferencias sobre la base común

> Complementa `GAP_ANALISIS_REGULATORIO.md`. Solo se listan aquí los
> requisitos que **no** están ya cubiertos por la base común ALCOA+, o
> donde un marco es más estricto que los otros en un punto específico.
> No es asesoría legal — es un punto de partida técnico para que el
> equipo de calidad del cliente lo revise con su propio criterio.

## Anexo A — Colombia / INVIMA

- **Ya cubierto, y es una ventaja competitiva a destacar:** la firma
  electrónica implementada en `utils/firma_electronica.py` se basa
  explícitamente en la **Ley 527 de 1999** (Colombia) — es el marco legal
  correcto para el mercado local, no una adaptación de un estándar
  extranjero.
- **Datos personales de los usuarios del sistema** (nombre, correo de los
  operadores/administradores) caen bajo la **Ley 1581 de 2012 (Habeas
  Data)** — no es un requisito de integridad de datos metrológicos, pero
  sí aplica al módulo de usuarios. Verificar que exista una política de
  tratamiento de datos personales documentada del lado del proveedor
  (contractual, no necesariamente técnica).
- INVIMA no tiene, a diferencia de la FDA, una norma tan codificada como
  el 21 CFR Part 11 — en la práctica, auditores en Colombia suelen aceptar
  evidencia alineada a guías internacionales (OMS/PIC/S, ISO) más la
  legislación local de firma electrónica. Este VMP, apoyado en ISO/IEC
  10012 (que el sistema ya implementa) y en la Ley 527/1999, cubre
  razonablemente ese criterio.

## Anexo B — 21 CFR Part 11 (FDA, EE.UU.)

- **§11.10(a) — Validación del sistema:** exige documentación de que el
  sistema produce resultados exactos y consistentes de forma repetible.
  Es exactamente el propósito de este paquete IQ/OQ/PQ — sin ejecutar el
  PQ, este punto queda abierto.
- **§11.200 — Componentes de la firma electrónica:** la firma debe
  incluir al menos dos componentes de identificación (código de
  identificación + contraseña) cuando el firmante ejecuta la firma. La
  implementación actual (sesión iniciada + reautenticación con
  contraseña en el momento de firmar) se alinea razonablemente con esto,
  pero conviene documentarlo explícitamente como tal frente a un auditor
  de FDA, no dejarlo implícito.
- **§11.300 — Controles de códigos de identificación/contraseñas:**
  pide, entre otras cosas, revisión y actualización periódica de
  contraseñas, detección de intentos de uso no autorizado (esto último
  **ya existe** — bloqueo por intentos fallidos), y procedimientos para
  manejar contraseñas comprometidas o perdidas (**ya existe** —
  `resetear_password_admin.py`). **Falta:** una política de expiración/
  rotación periódica de contraseñas — hoy no hay caducidad de contraseña,
  solo el cambio forzado en el primer login.
- Este es el marco **más estricto** de los tres en la robustez esperada
  del vínculo firma-registro (ver ítem #7 del gap analysis) — si un
  cliente objetivo audita bajo FDA, priorizar esa mejora primero.

## Anexo C — EU Annex 11 (GMP europeo)

- **Evaluación de proveedores (vendor assessment):** Annex 11 espera que
  el cliente evalúe formalmente al proveedor del software (MetroGest) como
  parte de su gestión de calidad. Este paquete completo de documentación
  (VMP + gap analysis + IQ/OQ/PQ) es exactamente lo que un cliente europeo
  necesitaría recibir para completar esa evaluación de proveedor — vale la
  pena empaquetarlo explícitamente como tal si aparece un cliente de ese
  mercado.
- **Gestión de incidentes:** Annex 11 pide un procedimiento para
  registrar y resolver incidentes del sistema (caídas, errores). Hoy
  existe el `RequestLoggingMiddleware` y `logs/app.log`, pero no un
  procedimiento formal de gestión de incidentes con clasificación de
  severidad — pendiente, probablemente un documento del cliente que cite
  este log como fuente, no algo que MetroGest deba construir.
- **Evaluación periódica del estado validado:** Annex 11 espera una
  revisión periódica (no solo validación inicial) de que el sistema sigue
  funcionando como se validó — se resuelve con el procedimiento de control
  de cambios pendiente (`PLAN_MAESTRO_VALIDACION.md` §6) más una
  revalidación parcial programada (ej. anual, o ante cambios
  significativos).
- **Archivado a largo plazo:** similar al ítem de retención de datos del
  gap analysis (#11) — Annex 11 es explícito en que los datos archivados
  deben seguir siendo legibles durante todo el período regulatorio, no
  solo "respaldados". Verificar que el formato de los backups de Postgres
  (`.dump`) sea restaurable a largo plazo (no depender de una versión
  específica de PostgreSQL que quede obsoleta).
