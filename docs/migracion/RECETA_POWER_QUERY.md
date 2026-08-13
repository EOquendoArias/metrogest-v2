# Receta de Power Query — de Excel del cliente a la plantilla estándar

> Fase 3 de `PLAN_IMPORTACION_EXCEL.md`. **Documento de trabajo de Edison,
> no para el cliente** — ver `README.md` de esta carpeta para la
> justificación de esa decisión. Construido sin un Excel real de cliente
> todavía disponible (ver §11 punto 3 del plan): es una metodología y un
> conjunto de transformaciones reutilizables, **no una receta fija** — cada
> cliente trae su propio desorden particular, y hay que ajustarla la
> primera vez que se usa con datos reales. Queda anotado explícitamente
> dónde es previsible que haya que adaptar algo.

## 1. Qué resuelve este documento

`PLAN_IMPORTACION_EXCEL.md` §1 ya explica por qué existe una etapa
Power Query separada del importador Python: el importador solo entiende
la plantilla estándar de 4 hojas (`Equipos`, `Magnitudes`, `Calibraciones`,
`PuntosCalibracion`, esquema exacto en §3 de ese documento); nunca ve el
Excel real y desordenado del cliente. Este documento es el "cómo" de esa
transformación — los pasos concretos dentro de Power Query para llegar de
uno al otro.

## 2. Antes de abrir Power Query

Primero se aplica el checklist de
[`GUIA_VALIDACION_Y_DESVIACIONES.md` §2](GUIA_VALIDACION_Y_DESVIACIONES.md#2-checklist-de-organización-de-la-información-antes-de-cargar)
— si el cliente no tiene ni un listado maestro de equipos con código
único, Power Query no arregla eso, solo lo hace más visible. No vale la
pena empezar a transformar datos que todavía no están mínimamente
organizados en origen.

## 3. Herramienta

Power Query viene incluido en Excel 2016+ y en Microsoft 365 (pestaña
**Datos → Obtener y transformar datos**) — no se necesita licencia ni
instalación aparte. Todo lo que sigue se hace en el **Editor de Power
Query** (botón "Transformar datos" al importar, o "Editor de Power Query"
desde la cinta Datos).

## 4. Vista general del flujo

```
Archivo(s) Excel del cliente (una o varias hojas/libros)
        │
        │  Obtener datos → Editor de Power Query
        ▼
4 consultas de transformación (una por hoja de destino)
        │  cada una termina con nombres de columna EXACTOS
        │  a los de PLAN_IMPORTACION_EXCEL.md §3
        ▼
Cerrar y cargar → como tabla, cada consulta a su propia hoja,
con el nombre de hoja EXACTO: Equipos / Magnitudes / Calibraciones /
PuntosCalibracion (importar_excel.py los busca por ese nombre literal,
ver HOJAS_REQUERIDAS en el código)
        ▼
Ese libro es lo que se le pasa a importar_excel.py
```

**Regla de oro:** las 4 consultas finales deben producir exactamente las
columnas de §3 del plan (ni de más ni de menos en las obligatorias), con
los mismos nombres, mismo orden no importa. Todo lo demás — cuántas
consultas intermedias, cuántos pasos, cómo se llaman los pasos — es libre.

## 5. Los 3 problemas típicos que resuelve Power Query aquí

No hay una receta universal porque no hay un formato universal de cliente,
pero en la práctica del sector (laboratorios de metrología) casi siempre
aparecen estos tres problemas, y Power Query tiene una herramienta nativa
para cada uno:

### 5.1 Equipo y magnitud mezclados en una sola fila

Común: una hoja con una fila por calibración, que repite el nombre/código
del equipo en cada fila junto con la magnitud medida esa vez.

**Transformación:** de esa consulta base salen DOS consultas hijas:

- **Equipos**: `Referencia` a la consulta base → `Quitar duplicados`
  sobre las columnas que identifican al equipo (`codigo`, `nombre`, y las
  demás columna de equipo) → esas son las únicas columnas que se
  conservan antes de quitar duplicados (`Elegir columnas` primero, si no
  cada fila se ve "distinta" por traer también datos de la calibración).
- **Magnitudes**: mismo patrón, pero quitando duplicados sobre
  (`codigo_equipo`, `nombre_magnitud`) — esa combinación es la clave
  natural real de la hoja `Magnitudes` (§3 del plan).

### 5.2 Puntos de calibración en columnas anchas ("Punto 1", "Punto 2"...)

El caso más común y el más laborioso: una fila por calibración, con
columnas repetidas tipo `Punto1_Patron`, `Punto1_Indicado`,
`Punto2_Patron`, `Punto2_Indicado`, ... en vez de una fila por punto. Esto
es exactamente lo que Power Query resuelve mejor y a mano sería tedioso.

**Transformación (despivotar en dos pasos):**

1. Con la consulta de Calibraciones ya identificada por un `id_temporal`
   (ver §5.3 si el cliente no trae uno), seleccionar **solo** las columnas
   `id_temporal` + todas las columnas `PuntoN_Patron`/`PuntoN_Indicado`.
2. **Transformar → Anular dinamización de otras columnas** (Unpivot Other
   Columns) sobre las columnas de punto → queda una fila por
   `id_temporal` + nombre de columna original (`Atributo`) + su valor.
3. La columna `Atributo` ahora tiene textos como `Punto1_Patron`,
   `Punto2_Indicado`. Con **Columna personalizada** o **Dividir columna
   por delimitador**, separar en dos columnas: `numero_punto` (el número)
   y `tipo_valor` (`Patron` o `Indicado`).
4. **Transformar → Dinamizar columna** (Pivot Column) usando `tipo_valor`
   como columna a dinamizar y `valor` (el paso 2) como columna de valores
   → el resultado son dos columnas, `Patron` e `Indicado`, una fila por
   `id_temporal` + `numero_punto`. Renombrarlas a `valor_patron` y
   `valor_indicado` (nombres exactos de §3 del plan).

Fragmento de M equivalente (referencia, no literal — los nombres de paso
van a variar según cómo se llamen las columnas del cliente real):

```m
// Paso: separar Atributo en numero_punto / tipo_valor
= Table.SplitColumn(Unpivoted, "Atributo", Splitter.SplitTextByEachDelimiter({"_"}, QuoteStyle.Csv, false), {"col_punto", "tipo_valor"})
// col_punto viene como "Punto1" -> extraer solo el número
= Table.TransformColumns(Separado, {{"col_punto", each Text.Trim(Text.Remove(_, {"P","u","n","t","o"})), type text}})
```

### 5.3 El cliente no trae un identificador único de calibración

La hoja `Calibraciones` necesita un `id_temporal` único dentro del archivo
(§3 del plan — es la clave que usa `PuntosCalibracion` para saber a qué
calibración pertenece cada punto). Si el Excel del cliente no trae uno:

**Transformación:** `Agregar columna → Columna de índice` sobre la
consulta de Calibraciones (antes de separar los puntos), y construir el
`id_temporal` concatenando algo legible + el índice, para que quede
trazable a simple vista en el Registro de Desviaciones si algo falla:

```m
= Table.AddColumn(Origen, "id_temporal", each [codigo_equipo] & "-" & Date.ToText([fecha_calibracion], "yyyy-MM-dd") & "-" & Text.From([Indice]))
```

## 6. Fechas y tipos de dato

- Convertir columnas de fecha con **Transformar → Tipo de dato → Fecha**
  (no dejarlas como texto libre) — Power Query detecta la mayoría de
  formatos regionales automáticamente. El importador (`_parsear_fecha` en
  `importar_excel.py`) acepta tanto objetos fecha reales de Excel como
  texto en `%Y-%m-%d`, `%d/%m/%Y` o `%d-%m-%Y` — pero es mejor entregar
  fecha real, no texto, para no depender de qué formato regional tenía el
  Excel original.
- Columnas numéricas (`valor_patron`, `valor_indicado`, `emp_valor`,
  `costo`...) deben quedar con tipo **Número decimal**, no texto — mismo
  motivo: el importador las intenta convertir, pero es mejor que ya
  lleguen limpias.

## 7. Detectar duplicados dentro de Power Query (Capa 1)

Antes de cerrar y cargar, es buena práctica dejar una consulta de
diagnóstico aparte (que **no** se carga al libro final, solo se usa
visualmente en el editor) para adelantar lo que la Capa 1 del importador
(`PLAN_IMPORTACION_EXCEL.md` §5) va a detectar de todas formas — así se
corrige en Power Query antes de gastar un ciclo de `--dry-run`:

```m
// Sobre la consulta de Equipos, antes de exportar
= Table.Group(Equipos, {"codigo"}, {{"Conteo", each Table.RowCount(_), Int64.Type}})
// Filtrar donde Conteo > 1 -> esos códigos están repetidos en el archivo
```

Igual para `id_temporal` en Calibraciones.

## 8. Exportar al formato final

**Inicio → Cerrar y cargar → Cerrar y cargar en...** por cada una de las
4 consultas finales, eligiendo "Solo crear conexión" para las consultas
intermedias/de diagnóstico y "Tabla en una hoja de cálculo existente o
nueva" para las 4 finales. Renombrar cada hoja resultante exactamente a
`Equipos`, `Magnitudes`, `Calibraciones`, `PuntosCalibracion` — el
importador busca esos nombres literales.

## 9. Checklist para reusar esta receta con el siguiente cliente

Lo que **cambia** de un cliente a otro (hay que rehacer/ajustar):

- Los pasos de limpieza/renombrado de columnas de origen (cada cliente
  nombra sus columnas distinto).
- Si el cliente separa equipo/magnitud o los trae mezclados (§5.1).
- Si trae puntos en columnas anchas o ya en filas (§5.2 puede no
  necesitarse).
- Si trae o no un identificador de calibración propio (§5.3).

Lo que **se mantiene igual** (es la parte reutilizable, el activo real):

- La forma final de las 4 consultas de salida (columnas exactas de §3).
- La técnica de despivotar puntos anchos (§5.2) — es prácticamente
  universal en Excel de laboratorios de metrología, cambia el nombre de
  columna, no la técnica.
- Las consultas de diagnóstico de duplicados (§7).

**Pendiente real, no resuelto todavía:** esta receta no se ha corrido
contra un Excel real de un cliente — se construyó a partir del formato
típico documentado en la industria y de la plantilla ya verificada del
importador (`PLAN_IMPORTACION_EXCEL.md` §9-§10). La primera vez que se use
con un cliente real, es esperable ajustar nombres de pasos y quizás
encontrar un cuarto problema típico no listado aquí — cuando pase,
documentarlo en este archivo para que la receta crezca con la experiencia
real, no se quede como un documento de diseño desconectado de la
práctica.
