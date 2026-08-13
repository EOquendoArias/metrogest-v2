# Validación de Sistemas Computarizados (CSV) — Clientes de industria farmacéutica

> Extensión de la **Línea 2 (Calidad)** de [`../../PROJECT_PLAN.md`](../../PROJECT_PLAN.md),
> motivada por que los clientes objetivo incluyen laboratorios/industria
> farmacéutica: ahí no basta con "el software funciona bien" — se exige
> **evidencia documentada** de que el sistema fue validado conforme a un
> marco regulatorio de integridad de datos (GxP / registros y firmas
> electrónicas), con un enfoque de aseguramiento por riesgo pero un paquete
> formal completo de Calificación de Instalación, Operacional y de
> Desempeño (IQ/OQ/PQ) — decisión tomada con el usuario el 2026-07-28.

## Alcance regulatorio

Se prepara la **base común** a los tres marcos más probables según el
mercado del cliente, más un anexo de diferencias específico por marco
(no se duplica el plan tres veces):

| Marco | Cuándo aplica |
|---|---|
| **INVIMA (Colombia) + ISO/IEC 10012** | Mercado inmediato del negocio. Ya es la base normativa que el software implementa hoy (ISO/IEC 10012:2003, ILAC G24:2017). |
| **21 CFR Part 11 (FDA, EE.UU.)** | Clientes que exportan a o son auditados bajo estándares de EE.UU. |
| **EU Annex 11 (GMP europeo)** | Clientes con operación o auditoría europea. |

## Documentos de esta carpeta

| Documento | Contenido | Estado |
|---|---|---|
| [`PLAN_MAESTRO_VALIDACION.md`](PLAN_MAESTRO_VALIDACION.md) | Enfoque, alcance, categorización GAMP5, roles, ciclo de vida de validación, lista maestra de entregables | Borrador inicial |
| [`GAP_ANALISIS_REGULATORIO.md`](GAP_ANALISIS_REGULATORIO.md) | Matriz requisito regulatorio × estado real en el código (`auth.py`, `firma_electronica.py`, `auditoria_trail.py`, `models.py`) | Completado con base al código actual — punto de partida real, no aspiracional |
| [`IQ_CALIFICACION_INSTALACION.md`](IQ_CALIFICACION_INSTALACION.md) | Protocolo de Calificación de Instalación (IQ) | Protocolo listo para ejecutar — resultados pendientes |
| [`OQ_CALIFICACION_OPERACIONAL.md`](OQ_CALIFICACION_OPERACIONAL.md) | Protocolo de Calificación Operacional (OQ) | Protocolo listo para ejecutar — resultados pendientes |
| [`PQ_CALIFICACION_DESEMPENO.md`](PQ_CALIFICACION_DESEMPENO.md) | Protocolo de Calificación de Desempeño (PQ) — se apoya en la prueba de carga de la Fase 2.3 del plan general | Protocolo listo para ejecutar — depende de la prueba de carga |
| [`ANEXOS_MARCOS.md`](ANEXOS_MARCOS.md) | Diferencias específicas por marco regulatorio sobre la base común | Borrador inicial |

## Relación con el resto del plan de calidad

- El **gap analysis** (este documento) y `../CHECKLIST_SEGURIDAD.md`
  (Fase 2.4, sí se escribió — nota de 12-ago-2026, corrige lo que decía
  antes esta sección) son complementarios, no duplicados: el gap analysis
  es una lectura *regulatoria* de una sola vez (requisito GxP × estado del
  código, con marco explícito ALCOA+/21 CFR 11/EU Annex 11), mientras que
  `CHECKLIST_SEGURIDAD.md` es una checklist *operativa* y repetible
  (automatizado vs. manual, pensada para marcarse antes de cada entrega a
  un cliente nuevo). Este documento cita al otro para la brecha #16
  (validación IQ/OQ/PQ), no lo reemplaza.
- El **PQ** reutiliza directamente los resultados de la prueba de carga de
  la Fase 2.3 (1,600 equipos / 10-20 usuarios concurrentes) — no se duplica
  el trabajo, se referencia como evidencia de desempeño.
- El **OQ** reutiliza el plan de pruebas funcionales de la Fase 2.2, pero
  reformateado como protocolo formal con columnas de resultado
  esperado/obtenido/aprobado y firma de quien ejecuta.
