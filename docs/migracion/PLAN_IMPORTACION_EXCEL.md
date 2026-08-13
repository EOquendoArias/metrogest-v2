# Plan de diseño — Importador de datos históricos desde Excel

> Responde a 3 preguntas concretas de Edison (12-ago-2026): cómo plantear
> el desarrollo, qué requerimientos hacen falta, y cómo validar datos y
> detectar duplicados — usando Power Query como herramienta de
> transformación del lado del cliente. **Esto es un diseño, no código
> todavía.** Verificado contra `models.py` real, no supuesto.

## 1. Por qué el problema no se resuelve con un solo script

Cada cliente trae su historial en un Excel con su propio formato: columnas
en español o inglés, hojas separadas por año, equipos y calibraciones
mezclados en una sola hoja, fechas como texto libre, puntos de calibración
en columnas ("Punto 1", "Punto 2"...) en vez de filas. Escribir un
importador que intente adivinar el formato de cada cliente es frágil y se
rompe con el cliente número dos. La solución que evita reescribir el
importador cada vez es **separar el problema en dos etapas independientes,
con un contrato fijo entre ellas**:

```
Excel real del cliente (formato variable, "sucio")
        │
        │  Power Query (transformación visual, sin código,
        │  reutilizable por Edison o por el cliente)
        ▼
Plantilla estándar de importación (esquema FIJO, ver §3)
        │
        │  Importador Python (genérico, no cambia por cliente)
        │  → validación (§4) → detección de duplicados (§5) → BD
        ▼
PostgreSQL (equipos, magnitudes, calibraciones, puntos...)
```

Power Query es la herramienta correcta para la primera etapa porque: no
requiere escribir código (Edison o el propio cliente de calidad puede
aprenderlo), sus pasos de transformación (consultas M) se guardan y se
reutilizan/adaptan de un cliente a otro sin empezar de cero, y tiene
funciones nativas exactamente para lo que hace falta aquí — despivotar
columnas repetidas ("Punto 1"..."Punto 5" → filas), combinar/anexar varias
hojas o archivos, normalizar tipos de fecha/número, y agrupar por clave
para contar duplicados antes de que el archivo llegue siquiera al
importador. El importador Python nunca necesita saber qué formato tenía el
Excel original del cliente — solo conoce la plantilla estándar.

## 2. Fases de desarrollo propuestas

| Fase | Entregable | Depende de | Estado |
|---|---|---|---|
| 1 (este documento) | Esquema de la plantilla estándar + reglas de validación + estrategia de duplicados | — | ✅ Hecho |
| 2 | `importar_excel.py` — importador genérico con modo `--dry-run` obligatorio por defecto, cubre Equipos → Magnitudes → Calibraciones → Puntos (el núcleo que motivó la pregunta: 5 años de historial de calibraciones) | Fase 1 | ✅ Hecho (12-ago-2026) |
| 3 | Receta de Power Query documentada (paso a paso, con capturas o descripción de cada transformación) que lleva un Excel real típico de laboratorio a la plantilla estándar | Fase 1 | ✅ Hecho (12-ago-2026) — ver `RECETA_POWER_QUERY.md`. Metodología reutilizable con los 3 problemas típicos del sector (equipo/magnitud mezclados, puntos en columnas anchas, sin id de calibración); **sin probar todavía contra un Excel real de cliente** |
| 4 | Prueba con un Excel de prueba que contenga errores deliberados (duplicados, campos faltantes, fechas inválidas) — confirmar que el modo `--dry-run` los detecta todos, antes de escribir tests `pytest` formales | Fases 2-3 | ✅ Hecho (12-ago-2026): 14/14 errores deliberados detectados sin BD (§8), y `--ejecutar` verificado contra Postgres real (`metrogest_carga`) — escritura, auditoría y duplicados (§9-§10). Un bug real encontrado y corregido en el camino (rastro de auditoría) |
| 5 | Extensión del mismo patrón a Verificaciones intermedias, Evaluación de riesgo ILAC y Mantenimientos, si el cliente también los trae en Excel | Fase 2 | Pendiente |
| 6 | Documentación operativa final: guía para Edison y, si aplica, guía simplificada para que el cliente prepare su propio archivo | Fases 2-5, esquema ya estable | ✅ Hecho (13-ago-2026) — ver `GUIA_OPERATIVA_MIGRACION.md` (guía para Edison, flujo completo de principio a fin) y `docs/cliente/GUIA_PREPARACION_DATOS.md` (guía para el cliente, ya existía desde la Fase 3) |

**Alcance de la Fase 2 (MVP):** Equipos, Magnitudes, Calibraciones y sus
Puntos — es lo que cubre el caso que motivó la pregunta. Verificaciones y
Mantenimientos quedan para la Fase 5 con el mismo patrón, no bloquean el
MVP.

## 3. Esquema de la plantilla estándar (el contrato fijo)

Derivado directamente de los campos obligatorios (`nullable=False`) y
relevantes de `models.py` — no es un esquema inventado. Como la base de
datos destino usa IDs autoincrementales que no existen todavía al momento
de leer el Excel, la plantilla usa **claves naturales de texto** para
ligar las hojas entre sí; el importador las resuelve a IDs reales dentro
de la misma transacción (mismo patrón que ya usa `seed_demo_data.py`:
`db.flush()` para obtener el ID antes de crear los hijos).

**Hoja `Equipos`**

| Columna | Obligatorio | Nota |
|---|---|---|
| `codigo` | Sí | Único — clave natural que usan las demás hojas |
| `nombre` | Sí | |
| `descripcion`, `marca`, `modelo`, `numero_serie`, `numero_inventario`, `fecha_adquisicion`, `costo`, `area`, `ubicacion`, `responsable` | No | |
| `estado` | No | Si se omite, entra como `en_espera_calibracion`; valores válidos: `operativo` / `en_espera_calibracion` / `fuera_de_uso` / `dado_de_baja` |

**Hoja `Magnitudes`**

| Columna | Obligatorio | Nota |
|---|---|---|
| `codigo_equipo` | Sí | Debe existir en `Equipos` |
| `nombre_magnitud` | Sí | Junto con `codigo_equipo` es la clave natural que usan Calibraciones |
| `simbolo`, `unidad`, `rango_min`, `rango_max`, `resolucion`, `emp_texto`, `emp_unidad`, `clase_exactitud`, `tipo_instrumento` | No | |
| `emp_valor` | Recomendado, no obligatorio en BD | Sin este valor el semáforo de conformidad no puede calcularse para las calibraciones de esa magnitud — avisar al cliente que sin EMP, esa magnitud queda sin control visual |

**Hoja `Calibraciones`**

| Columna | Obligatorio | Nota |
|---|---|---|
| `id_temporal` | Sí | Texto libre, único dentro del archivo (ej. `EQ-001-2023-06`) — es la clave que usa la hoja `PuntosCalibracion` para saber a qué calibración pertenece cada punto. Más robusto que usar fecha+certificado porque evita ambigüedad si hay dos calibraciones el mismo día |
| `codigo_equipo`, `nombre_magnitud` | Sí | Deben existir en las hojas anteriores |
| `fecha_calibracion` | Sí | |
| `numero_certificado` | Recomendado fuertemente | Es la referencia principal para la detección de duplicados (§5) y para trazabilidad ante auditoría |
| `laboratorio`, `acreditacion_laboratorio`, `proxima_calibracion`, `patrones_utilizados`, `metodo_calibracion`, `temperatura_ambiente`, `humedad_relativa`, `trazabilidad`, `observaciones`, `costo` | No | |
| `resultado` | Recomendado | Para historial ya cerrado, normalmente `aprobado`; si se omite, el importador puede recalcularlo con `utils/calculos.py` a partir de los puntos (ver §4) |

**Hoja `PuntosCalibracion`**

| Columna | Obligatorio | Nota |
|---|---|---|
| `id_temporal_calibracion` | Sí | Debe existir en la hoja `Calibraciones` |
| `numero_punto` | Sí | |
| `valor_patron` | Sí | |
| `valor_indicado` | Sí | |
| `incertidumbre`, `observacion` | No | |

## 4. Guía de validación de datos

Se ejecuta en 5 niveles, en orden — cada nivel solo corre si el anterior
pasó, y **todo se acumula en un reporte, no se detiene en el primer
error** (para que el cliente corrija todo de una vez, no fila por fila):

1. **Estructural** — existen las hojas y columnas obligatorias de §3; no
   hay valores vacíos en columnas marcadas "Sí".
2. **De tipo/formato** — fechas parseables y no absurdas (ej. año < 1990 o
   fecha futura para una calibración "ya realizada" se marca como
   sospechosa, no se rechaza automáticamente); `valor_patron`,
   `valor_indicado`, `emp_valor` parseables como número, no texto.
3. **Referencial** — toda fila de `Magnitudes` referencia un
   `codigo_equipo` que existe en `Equipos`; toda fila de `Calibraciones`
   referencia un `codigo_equipo`+`nombre_magnitud` que existe; todo punto
   referencia un `id_temporal_calibracion` que existe.
4. **De regla de negocio** — recalcular el semáforo de conformidad
   (`utils/calculos.py`, la misma función que usa la app en producción,
   no una reimplementación) a partir de los puntos importados, y si el
   Excel trae un `resultado` que no coincide con lo recalculado, marcarlo
   como advertencia (no error duro — puede ser una decisión de calidad
   documentada del cliente, pero hay que mostrársela).
5. **Duplicados** — ver §5.

El importador corre por defecto en **modo `--dry-run`**: produce un
reporte (Excel o CSV, una fila por problema encontrado, con hoja/fila/
columna/descripción) sin escribir nada en la base de datos. Solo con
`--ejecutar` explícito, y tras revisar que el dry-run salió limpio (o que
las advertencias restantes son aceptadas conscientemente), se hace la
carga real — dentro de **una sola transacción**: si algo falla a mitad de
camino, se revierte todo, nunca se deja al cliente con una carga a medias.

## 5. Detección de duplicados — 3 capas

**Capa 1, dentro del propio Excel (en Power Query, antes de que el
archivo llegue al importador):** agrupar por `codigo` en `Equipos` y por
`id_temporal` en `Calibraciones`, contar, filtrar donde el conteo sea > 1.
Es exactamente el tipo de chequeo que Power Query hace bien de forma
visual — es la primera línea de defensa, más barata que descubrirlo ya
dentro de la base de datos.

**Capa 2, equipos contra la base de datos destino (importador Python,
antes de insertar):** `Equipo.codigo` es `UNIQUE` en la base de datos real
— si el importador intentara insertar un código ya existente sin
verificar antes, la transacción completa fallaría con un error de
integridad a mitad de una carga de 1,600 equipos. Política por defecto:
**no tocar equipos que ya existen** — se insertan solo los nuevos, los
existentes se reportan como "ya presente, no modificado" en el reporte de
validación. Actualizar campos de un equipo ya existente requiere una
bandera explícita (`--actualizar-existentes`), nunca es el comportamiento
por defecto.

**Capa 3, calibraciones probablemente duplicadas (no hay constraint único
real en la base de datos, así que es heurística, no una regla dura):**
misma combinación `codigo_equipo` + `nombre_magnitud` + `fecha_calibracion`
+ `numero_certificado` ya presente en la base de datos → se excluye de la
inserción por defecto y se reporta para revisión humana. Nunca se decide
solo si es un duplicado real o una recalibración legítima el mismo
día — eso lo confirma una persona, el importador solo lo señala.

## 6. Requerimientos técnicos

- **Sin dependencias nuevas**: `openpyxl` ya está en `requirements.txt`
  (se usa para exportación) y alcanza para leer la plantilla estándar ya
  limpia por Power Query. No se agrega `pandas` — mismo criterio que ya se
  usó para elegir Locust sobre k6 en la Fase 2.3: no sumar infraestructura
  que la escala real no exige.
- **Nunca contra la base de datos de producción en el primer intento** —
  mismo principio de `seed_carga_masiva.py`: correr primero contra una
  copia de staging, con guardas explícitas de confirmación antes de tocar
  la base real de un cliente.
- **Backup obligatorio antes de una carga real** (`backup_db.py`, ya
  existe) — documentarlo como paso obligatorio del runbook de esta
  herramienta, no opcional.
- **El rastro de auditoría es gratis**: si el importador usa la sesión
  normal de SQLAlchemy (`SessionLocal`), cada fila que crea pasa
  automáticamente por `utils/auditoria_trail.py` sin código adicional —
  confirmar esto con una prueba puntual en la Fase 4, no darlo por hecho.

## 7. Qué falta después de este documento

`importar_excel.py` ya existe en la raíz del proyecto e implementa los 5
niveles de validación y las 3 capas de duplicados descritos arriba,
produciendo el Registro de Desviaciones de
`GUIA_VALIDACION_Y_DESVIACIONES.md` §4. Limitación conocida y documentada
en el propio código (no oculta): si un equipo importado ya existía y ya
tenía una magnitud con el mismo nombre, el importador reutiliza esa
magnitud existente en vez de duplicarla, pero no fusiona/actualiza sus
campos — suficiente para el MVP, revisar si un cliente real lo necesita.

Sigue faltando, en orden de lo más urgente a lo menos:

1. ~~Probar `--ejecutar` contra un Postgres real~~ — ✅ **Hecho (12-ago-2026)**,
   ver §9-§10: escritura transaccional, rastro de auditoría y detección de
   duplicados contra BD real verificados con evidencia. En el camino se
   encontró y corrigió un bug real (el rastro de auditoría no se generaba
   para las cargas del importador — §10, hallazgo B).
2. La receta de Power Query documentada (Fase 3) — sin ella, alguien
   tiene que armar la plantilla estándar a mano por ahora.
3. Confirmar con Edison si el esquema de §3 cubre los campos que
   realmente trae el Excel típico de sus clientes.
4. Decidir si `--ejecutar` debe pedir confirmación interactiva
   fila-crítica por fila-crítica o basta con el resumen actual antes de
   confirmar toda la carga (hoy es un solo "SI" para toda la operación).
5. Agregar al checklist de instalación (IQ) la verificación de
   `POSTGRES_BIN_DIR` contra la versión real de Postgres del cliente (§11,
   hallazgo A de §10).

## 8. Verificación realizada (Fase 4 parcial, 12-ago-2026)

`generar_excel_prueba_migracion.py` (también en la raíz del proyecto)
genera un Excel de prueba con **14 errores deliberados**, uno por cada
regla de validación de §4-§5 (columna obligatoria faltante, valor no
parseable, referencia rota, duplicado dentro del archivo en 2 hojas
distintas, EMP ausente, estado inválido, fecha sospechosamente antigua o
futura, y el semáforo recalculado que no coincide con el `resultado`
declarado). Corriendo `importar_excel.py` en modo `--dry-run` (sin base de
datos) contra ese archivo:

| Severidad | Esperadas | Detectadas |
|---|---|---|
| Crítica | 8 | 8 |
| Alta | 1 | 1 |
| Media | 3 | 3 |
| Baja | 2 | 2 |

Las 14 coincidieron exactamente, con la fila, la regla violada y la
descripción correctas en cada caso — verificado leyendo el
`Registro_Desviaciones` generado, no solo el conteo del resumen. También
se probó el ciclo completo de `--registro-resueltas`: marcar a mano la
única desviación Alta como `Resuelta - corregida en origen` con su
justificación, y confirmar que una corrida posterior la reconoce (columna
`estado`/`decision`/`decidido_por` correctas) mientras el gate de
`--ejecutar` sigue bloqueando por las Críticas (que en esta prueba nunca
se resolvieron a propósito). **No probado:** la escritura real a Postgres
— no hay una base de datos disponible en el entorno donde se construyó
esto, queda como el primer paso pendiente antes de usar el importador con
un cliente real.

## 9. Runbook — probar `--ejecutar` contra un Postgres real

Esto lo tiene que correr Edison en su máquina (el entorno donde se
construyó `importar_excel.py` no tiene Postgres). Usa `metrogest_carga`,
la misma base de datos de staging que ya existe para las pruebas de carga
de `docs/calidad/PLAN_PRUEBAS_CARGA.md` — es intencional: ese nombre ya
contiene "carga", así que pasa la guarda de seguridad del importador
(`--confirmo-produccion` solo se exige si el nombre de la BD no parece de
prueba) sin necesitar banderas extra, y ya tiene el esquema de Alembic
aplicado.

**Paso 0 — prerrequisitos**

```bat
cd "C:\Users\EDISO\OneDrive\Claude desarrollo\metrogest_v2"
venv\Scripts\activate
```

Confirma que `metrogest_carga` existe y tiene el esquema al día (si no,
créala igual que se hizo para las pruebas de carga y corre
`alembic upgrade head` contra ella antes de seguir).

**Paso 1 — prueba negativa: confirmar que la guarda de seguridad bloquea
un archivo con errores**

Esto reusa el archivo con los 14 errores deliberados. El objetivo de este
paso NO es cargar datos — es confirmar que `--ejecutar` se niega a escribir
cuando quedan Críticas, tal como está documentado.

```bat
python generar_excel_prueba_migracion.py excel_prueba.xlsx
python importar_excel.py excel_prueba.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga --ejecutar --sin-confirmacion
```

Resultado esperado: el importador imprime el resumen de severidades (8
Crítica / 1 Alta / 3 Media / 2 Baja — puede variar levemente en Media/Baja
si `metrogest_carga` ya tiene datos que interactúan con las capas 2/3) y
**aborta sin escribir nada**, listando que hay Críticas pendientes. Si en
cambio escribe algo, es un bug de la guarda de seguridad — repórtamelo con
la salida completa antes de seguir con el resto del runbook.

**Paso 2 — generar el archivo limpio (sin errores) para la prueba
positiva**

```bat
python generar_excel_prueba_limpio_migracion.py excel_prueba_limpio.xlsx
python importar_excel.py excel_prueba_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga
```

Resultado esperado: **0 desviaciones de cualquier severidad**. Si aparece
alguna, no sigas — pégame la salida completa (incluye el `Registro_Desviaciones`
que genera junto al Excel) para que la revisemos antes de intentar
`--ejecutar`; puede ser un problema real del importador o simplemente que
`metrogest_carga` ya tiene un equipo con código `EQ-CLEAN-001`/`EQ-CLEAN-002`
de una corrida anterior (en ese caso, vuelve a correr este paso 2 con
`excel_prueba_limpio2.xlsx` y cambia los códigos dentro del script antes de
generarlo, o simplemente borra esos dos equipos de `metrogest_carga` si es
prescindible — es una BD de staging, no de un cliente real).

**Paso 3 — backup antes de escribir (práctica obligatoria del proyecto,
aunque sea una BD de staging — para no perder el hábito)**

```bat
python backup_db.py
```

Confirma que el backup se generó (revisa la carpeta de backups configurada
en `.env`) antes de seguir.

**Paso 4 — carga real (`--ejecutar`) con el archivo limpio**

```bat
python importar_excel.py excel_prueba_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga --ejecutar
```

El importador va a preguntar si ya hiciste un backup (contesta que sí,
ya lo hiciste en el paso 3) y luego va a pedir que escribas `SI` en
mayúsculas para confirmar la escritura real. Después de confirmar, debe
imprimir un resumen de conteos creados: 2 equipos, 2 magnitudes, 2
calibraciones, 4 puntos.

**Paso 5 — verificar en la base de datos que los datos quedaron bien**

Con `psql` o pgAdmin, contra `metrogest_carga`:

```sql
SELECT codigo, nombre, estado FROM equipos WHERE codigo LIKE 'EQ-CLEAN%';
SELECT e.codigo, m.nombre_magnitud, m.emp_valor
  FROM magnitudes_equipo m JOIN equipos e ON e.id = m.equipo_id
  WHERE e.codigo LIKE 'EQ-CLEAN%';
SELECT numero_certificado, fecha_calibracion, resultado FROM calibraciones
  WHERE numero_certificado LIKE 'CERT-CLEAN%';
SELECT COUNT(*) FROM puntos_calibracion pc
  JOIN calibraciones c ON c.id = pc.calibracion_id
  WHERE c.numero_certificado LIKE 'CERT-CLEAN%';  -- debe dar 4
```

**Paso 6 — confirmar que el rastro de auditoría se generó solo (esto
nunca se había verificado — está marcado como "no darlo por hecho" en §6)**

```sql
SELECT tabla, accion, fecha, usuario_id FROM registro_auditoria
  ORDER BY fecha DESC LIMIT 20;
```

Debe haber filas nuevas para `equipos`, `magnitudes_equipo`,
`calibraciones` y `puntos_calibracion` con la fecha/hora de este runbook.
Si no aparece nada, es un hallazgo real (la afirmación "el rastro de
auditoría es gratis" de §6 sería falsa para este flujo) — pégame la
consulta vacía y lo investigamos, no lo demos por bueno solo porque el
importador no dio error.

**Paso 7 — prueba de idempotencia: correr la misma carga otra vez (valida
las Capas 2/3 de duplicados contra BD real, que tampoco se habían probado)**

```bat
python importar_excel.py excel_prueba_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga
```

Resultado esperado en el `Registro_Desviaciones`: 2 desviaciones Baja
("equipo ya existe, no se modifica" — Capa 2) y 2 desviaciones Alta
("calibración probablemente duplicada" — Capa 3, una por cada
`numero_certificado` que ya está en la BD). Si `--ejecutar` se corriera de
nuevo sobre este mismo archivo sin resolver esas Altas, debe abortar — es
la prueba de que el importador no duplica una carga por accidente si
alguien lo corre dos veces.

**Paso 8 — repórtame los resultados**

Pégame la salida de cada paso (o al menos confirmá cuáles salieron como se
esperaba y cuáles no). Con eso actualizo este documento — cambio el
"Pendiente" del punto 1 de §7 a hecho, completo esta §9 con los resultados
reales (igual que se hizo con la tabla de §8), y en `docs/PROJECT_PLAN.md`
§4.1 actualizo el estado de esta línea de trabajo.

## 10. Resultados reales del runbook §9 (12-ago-2026, contra `metrogest_carga`)

Ejecutado por Edison, guiado paso a paso, contra Postgres real por primera
vez. Resultado: **7 de 8 pasos salieron exactamente como se esperaba a la
primera. Uno reveló un bug real** — se corrigió en el momento y se
reverificó con éxito. Se documenta el hallazgo completo porque es
justamente la clase de cosa que este runbook existía para descubrir.

| Paso | Resultado |
|---|---|
| 1. Prueba negativa (14 errores) | ✅ Bloqueó correctamente: 8 Crítica detectadas, `--ejecutar` abortó sin escribir nada |
| 2. Archivo limpio, dry-run | ✅ 0 desviaciones de cualquier severidad |
| 3. Backup (`backup_db.py`) | ⚠️ Falló en el primer intento — ver hallazgo A |
| 4. Carga real (`--ejecutar`) | ✅ 2 equipos, 2 magnitudes, 2 calibraciones, 4 puntos creados, 0 omitidos |
| 5. Verificación en BD (SQL directo) | ✅ Los 2 equipos, 2 calibraciones y 4 puntos existen con los valores correctos |
| 6. Rastro de auditoría automático | ⚠️ Ninguna fila generada en el primer intento — ver hallazgo B (bug real, corregido) |
| 7. Reintento con datos nuevos tras el fix | ✅ 10 filas nuevas en `registro_auditoria` (2 equipos + 2 magnitudes + 2 calibraciones + 4 puntos), acción `crear`, `usuario_id` correcto, timestamp exacto |
| 8. Idempotencia (Capas 2/3 contra BD real) | ✅ Mismo archivo corrido de nuevo: 2 Baja (equipo ya existe) + 2 Alta (calibración probable duplicada, Capa 3), `--ejecutar` abortó sin duplicar nada |

**Hallazgo A — `backup_db.py` no encontraba `pg_dump`:** la ruta por
defecto (`POSTGRES_BIN_DIR`) asume Postgres 17; la instalación de Edison es
Postgres 18. No es un bug del script — es una variable de entorno que hay
que ajustar por instalación. Se resolvió agregando
`POSTGRES_BIN_DIR=C:\Program Files\PostgreSQL\18\bin` al `.env`. **Nota
para instalaciones de clientes:** el instalador/checklist de IQ debería
verificar la versión real de Postgres instalada y ajustar esta variable —
agregarlo al checklist de instalación (pendiente, ver §11).

**Hallazgo B — el rastro de auditoría NO se generaba para las cargas del
importador (bug real, ya corregido):** `utils/auditoria_trail.py` engancha
sus listeners (`before_flush`/`after_flush`) a la clase genérica
`sqlalchemy.orm.Session` — en teoría alcanza a cualquier sesión del
proceso. En la práctica, esos decoradores solo se ejecutan (y por lo tanto
solo registran los listeners) cuando el módulo `utils.auditoria_trail` se
*importa* en algún punto del proceso. `importar_excel.py` crea su propio
`engine`/`Session` con SQLAlchemy directo y nunca pasaba por
`main.py`/`database.py`, así que nunca importaba ese módulo — la carga
escribía perfectamente bien en las tablas, pero cero filas nuevas
aparecían en `registro_auditoria`. Confirmado con evidencia real (consulta
SQL vacía para las tablas recién escritas), no supuesto — exactamente el
riesgo que ya advertía §6: *"confirmar esto con una prueba puntual... no
darlo por hecho"*.

**Corrección aplicada** (en `importar_excel.py`, junto a donde se crea la
sesión de BD): se agregó `import utils.auditoria_trail` antes de crear el
`Session()`, más un flag nuevo `--usuario-id` para que la carga quede
atribuida a un usuario real en el rastro de auditoría (antes habría
quedado en `NULL` incluso después de arreglar el import — relevante para
trazabilidad GxP). **Reverificado con éxito**: una segunda carga (con
`--usuario-id 1`) generó las 10 filas esperadas en `registro_auditoria`
con el usuario y timestamp correctos (ver paso 7 de la tabla).

**Conclusión:** el importador está verificado de punta a punta contra
Postgres real — lectura, validación, escritura transaccional, resolución
de IDs vía `flush()`, rastro de auditoría, y detección de duplicados en 3
capas. Queda listo para usarse con un cliente real en cuanto a la parte
técnica; sigue pendiente la Fase 3 (receta de Power Query) para que la
transformación desde el Excel real del cliente hacia la plantilla estándar
no dependa de armarla a mano.

## 11. Pendientes que salieron de esta verificación

1. ~~Agregar al checklist de instalación (IQ) la verificación de
   `POSTGRES_BIN_DIR` contra la versión real de Postgres instalada en el
   equipo del cliente~~ — ✅ **Hecho (13-ago-2026)**: nuevo ítem IQ-3 en
   `docs/calidad/validacion_farma/IQ_CALIFICACION_INSTALACION.md`, y el
   ítem de backup (ahora IQ-12) exige que `backup_db.py` se haya corrido
   manualmente con éxito, no solo que la tarea programada exista.
2. ~~Fase 3: receta de Power Query documentada~~ — ✅ Hecho, ver
   `RECETA_POWER_QUERY.md`.
3. Confirmar con Edison si el esquema de §3 cubre los campos reales de sus
   clientes.
4. Decidir si `--ejecutar` debe confirmar fila-crítica por fila-crítica o
   basta el resumen actual (sigue abierto, sin cambios desde §7).
