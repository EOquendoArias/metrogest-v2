# Migración de datos históricos de clientes (Excel → MetroGest)

> Línea de trabajo nueva (12-ago-2026), separada de las 3 líneas de
> [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) porque responde a un servicio
> de negocio distinto: la carga de datos históricos de un cliente (hasta 5
> años, ~1,600 equipos) que Edison cobra de forma independiente a la
> licencia. Verificado en el código antes de empezar (12-ago-2026): **no
> existía ninguna herramienta de importación desde Excel** — era un vacío
> de producto real. Ya existe un importador funcional, **verificado de
> punta a punta contra Postgres real** (lectura, validación, escritura
> transaccional, auditoría, duplicados) — ver `PLAN_IMPORTACION_EXCEL.md`
> §9-§10. Un bug real (rastro de auditoría) se encontró y corrigió en esa
> verificación.

## Documentos de esta carpeta

- [`PLAN_IMPORTACION_EXCEL.md`](PLAN_IMPORTACION_EXCEL.md) — enfoque de
  desarrollo, arquitectura de dos etapas (Power Query → plantilla estándar
  → importador), esquema exacto de la plantilla derivado de `models.py`,
  **qué** se valida (5 niveles) y **cómo** se detectan duplicados (3
  capas). **Estado: diseño, sin construir todavía.**
- [`GUIA_VALIDACION_Y_DESVIACIONES.md`](GUIA_VALIDACION_Y_DESVIACIONES.md)
  — el framework de *proceso* que se construye encima de lo anterior:
  checklist de organización de datos antes de cargar, clasificación de
  desviaciones por severidad, plantilla del Registro de Desviaciones, el
  flujo paso a paso de resolución conjunta con el cliente, y la regla de
  dónde se corrige cada tipo de dato (origen vs. excepción documentada).
  **Estado: framework definido y ya implementado por el importador real.**
- [`RECETA_POWER_QUERY.md`](RECETA_POWER_QUERY.md) — Fase 3: la
  transformación técnica de Excel del cliente → plantilla estándar,
  paso a paso en Power Query. **Documento interno de Edison, no para el
  cliente** (ver razonamiento dentro). Construido como metodología
  reutilizable, sin probar todavía contra un Excel real de cliente.
- [`PLAN_FASE5_EXTENSIONES.md`](PLAN_FASE5_EXTENSIONES.md) — Fase 5:
  extiende el importador a Verificaciones intermedias, Evaluación de
  riesgo ILAC y Mantenimientos (6 hojas nuevas, todas opcionales).
  **Estado: construido y verificado de punta a punta contra Postgres real**
  (12/12 errores deliberados sin BD + `--ejecutar` real, escritura,
  intervalo ILAC derivado del historial correcto, auditoría, ver §7). Un
  hallazgo real sobre qué significa "aceptar" una Alta de Capa 3, ya
  documentado en `GUIA_VALIDACION_Y_DESVIACIONES.md` §3 y **corregido en
  código** (`cargar_registro_resueltas()` distingue "corregida en origen"
  de "Aceptada"), verificado también contra Postgres real — ver §7.1.
- [`GUIA_OPERATIVA_MIGRACION.md`](GUIA_OPERATIVA_MIGRACION.md) — Fase 6:
  guía operativa consolidada para Edison — el flujo completo de una
  migración real de cliente, de principio a fin, con los comandos exactos
  y los problemas ya encontrados al ejecutar este proceso (contraseñas mal
  puestas, ediciones de Excel no guardadas, versión de Postgres, etc.).
  **Estado: hecho.** Punto de entrada único — enlaza a los demás
  documentos en vez de repetirlos.

## Código (raíz del proyecto, no en esta carpeta)

- `importar_excel.py` — el importador (Fase 2 de `PLAN_IMPORTACION_EXCEL.md`).
  Modo `--dry-run` verificado con 14/14 errores deliberados detectados
  correctamente (§8 del plan). Modo `--ejecutar` **verificado contra
  Postgres real** (`metrogest_carga`, 12-ago-2026): escritura, rastro de
  auditoría (bug encontrado y corregido) y detección de duplicados en 3
  capas — ver §9-§10 del plan. Listo técnicamente para un cliente real;
  falta la Fase 3 (receta de Power Query).
- `generar_excel_prueba_migracion.py` — genera el Excel de prueba con 14
  errores deliberados usado para verificar el importador. Útil para
  repetir la verificación si el importador cambia.
- `generar_excel_prueba_limpio_migracion.py` — genera un Excel sin ningún
  error deliberado (2 equipos, 2 magnitudes, 2 calibraciones, 4 puntos),
  para probar el camino positivo: que `--ejecutar` realmente inserta datos
  correctos en Postgres. Se usa en el runbook de
  `PLAN_IMPORTACION_EXCEL.md` §9.
- `generar_excel_prueba_fase5.py` — genera un Excel con 12 errores
  deliberados sobre las 6 hojas nuevas de la Fase 5 (Verificaciones/ILAC/
  Mantenimientos). Verificado sin BD (12/12), ver `PLAN_FASE5_EXTENSIONES.md` §5.

**Runbook para probar `--ejecutar` contra un Postgres real:** ver
[`PLAN_IMPORTACION_EXCEL.md` §9](PLAN_IMPORTACION_EXCEL.md#9-runbook--probar---ejecutar-contra-un-postgres-real).

## Por qué es una línea aparte

No es Línea 1 (arquitectura), ni Línea 2 (calidad de lo ya construido), ni
Línea 3 (documentos de venta) — es una funcionalidad de producto que falta
construir, motivada por un compromiso comercial que Edison ya está
vendiendo. Se documenta aquí en vez de mezclarla con `PROJECT_PLAN.md`
para no confundir "documentar lo que existe" con "diseñar lo que falta".
