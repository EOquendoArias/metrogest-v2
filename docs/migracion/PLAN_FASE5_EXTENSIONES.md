# Diseño — Fase 5: Verificaciones, Evaluación de riesgo ILAC, Mantenimientos

> Extiende el mismo patrón de `PLAN_IMPORTACION_EXCEL.md` (plantilla
> estándar → `importar_excel.py`) a tres áreas nuevas, independientes
> entre sí — se pueden construir en cualquier orden, o solo la(s) que un
> cliente concreto necesite. Documento aparte para no seguir ampliando el
> plan de la Fase 2 (MVP), que ya quedó cerrado y verificado contra
> Postgres real (`PLAN_IMPORTACION_EXCEL.md` §9-§10). Diseño acordado con
> Edison (12-ago-2026) sobre el criterio real del negocio, no solo sobre
> el esquema de la base de datos.

## 1. Evaluación de riesgo ILAC

### 1.1 Por qué no basta con "recalcular y comparar" como en Calibraciones

En la Fase 2, el Nivel 4 de validación recalcula el semáforo y compara
contra el `resultado` declarado — ahí cualquier discrepancia es solo una
advertencia a revisar. Para ILAC el criterio de negocio es distinto (y lo
aclaró Edison): el propósito de la evaluación de riesgo es **definir el
intervalo hasta la siguiente calibración después de la calibración
inicial**. Si el cliente trae 2 o más calibraciones en su historial, el
dato más honesto para `intervalo_adoptado_meses` no es preguntárselo al
cliente ni recalcularlo desde cero — es el intervalo que el cliente
**realmente usó** entre su primera y su segunda calibración. Ese es el
hecho histórico verificable; lo que la app recalcula con los 14 factores
de riesgo (`intervalo_sugerido_meses`) es la referencia contra la que se
compara, no lo que se debe imponer sobre el historial.

### 1.2 Regla de negocio real (verificada en el código, no supuesta)

`routers/ilac.py` líneas 66-73, comportamiento real de la app hoy:

```python
sug = calcular_intervalo_inicial(fs, fab)          # utils/calculos.py — misma función, se reutiliza
ado = int(intervalo_adoptado_meses) if intervalo_adoptado_meses else sug
if ado > sug and not justificacion_exceso.strip():
    # bloquea — exige justificación
```

El importador debe reproducir exactamente esta regla, no una versión
propia.

### 1.3 Cómo se resuelve `intervalo_adoptado_meses` al migrar historial

En este orden de prioridad:

1. **Si la hoja `Evaluaciones` trae `intervalo_adoptado_meses` explícito**
   → se usa ese valor tal cual (el cliente/Edison documentó un criterio
   distinto al histórico y lo declaró a propósito).
2. **Si no lo trae, y existen 2 o más calibraciones para ese
   equipo+magnitud** (en el mismo archivo que se está important, o ya en
   la base de datos si las calibraciones se cargaron en una corrida
   anterior — requiere `--database-url`, mismo patrón que la Capa 2/3 de
   duplicados) → se calcula como los meses entre la fecha de la 1ª y la
   2ª calibración **cronológicamente**, redondeado al entero más cercano.
   Esto es nuevo respecto a Calibraciones: esta regla necesita mirar datos
   de otra hoja/tabla, no solo la propia fila.
3. **Si no lo trae y hay menos de 2 calibraciones** → `ado = sug` (sin
   excedente, coincide con el comportamiento real de la app cuando el
   campo queda vacío en el formulario).

Si el resultado de 1-3 da `ado > sug` y la hoja no trae
`justificacion_exceso` → se marca como desviación **Alta** (mismo
tratamiento que cualquier otra Alta: bloquea `--ejecutar` hasta que el
cliente la resuelva, igual que ya funciona para el semáforo de
calibraciones).

**Pendiente de decidir, no bloqueante para diseñar el resto:** la
convención exacta de redondeo para "meses entre dos fechas" (ej.
`round(dias / 30.44)` vs. diferencia de meses calendario). Se resuelve al
construir, con un caso de prueba concreto — no cambia el diseño de arriba.

### 1.4 Esquema de la hoja `Evaluaciones` (propuesto)

| Columna | Obligatorio | Nota |
|---|---|---|
| `codigo_equipo`, `nombre_magnitud` | Sí | Clave natural — debe existir en `Equipos`/`Magnitudes` |
| `f_incertidumbre` … `f_legal` (14 factores) | No | Si se omiten, cada uno entra en 3 (valor por defecto real del modelo) |
| `intervalo_fabricante_meses` | No | Si viene y es menor al calculado, la función real ya lo respeta (§1.2) |
| `intervalo_adoptado_meses` | No | Ver §1.3 — si se omite, se deriva del historial o de `sug` |
| `justificacion` | No | Texto libre |
| `justificacion_exceso` | Solo si `ado > sug` | Obligatoria en ese caso — Alta si falta |
| `evaluado_por` | No | |

## 2. Verificaciones intermedias

### 2.1 Decisión confirmada: sí hace falta una hoja `PlanesVerificacion`

A diferencia de Calibraciones (que no depende de que exista una
configuración previa), `VerificacionIntermedia.plan_id` es obligatorio.
Edison confirmó que crear un plan automático con valores por defecto no
sirve — algunos clientes no hacen verificaciones intermedias en absoluto,
y eso hay que **documentarlo explícitamente**, no inferirlo. El modelo
real ya lo anticipa: `PlanVerificacion.frecuencia_meses` es
`nullable=True` con el comentario `"nullable cuando no aplica"`, y ya
existe el campo `justificacion_no_aplica`.

### 2.2 Esquema de la hoja `PlanesVerificacion` (propuesto)

| Columna | Obligatorio | Nota |
|---|---|---|
| `codigo_equipo`, `nombre_magnitud` | Sí | Clave natural |
| `frecuencia_meses` | No | Vacío si el cliente no hace verificaciones intermedias para esa magnitud |
| `patron_referencia`, `procedimiento` | No | |
| `umbral_alerta_pct`, `umbral_fuera_pct` | No | Si se omiten, quedan en los valores por defecto reales (70% / 100%) |
| `activo` | No | Default `True` |
| `justificacion_no_aplica` | **Obligatoria si `frecuencia_meses` viene vacío** | Regla nueva de validación: vacío + sin justificación = desviación Media como mínimo (a definir severidad exacta al construir) |

Luego, hojas `Verificaciones` y `PuntosVerificacion` — mismo patrón de
`id_temporal` que `Calibraciones`/`PuntosCalibracion` de la Fase 2, sin
novedad de diseño.

## 3. Mantenimientos

Confirmado el enfoque simple ya propuesto: `Mantenimiento` no depende de
que exista un `PlanMantenimiento` (no hay FK entre ellos en el modelo), así
que:

- Hoja `Mantenimientos` — carga de historial, independiente.
- Hoja `PlanesMantenimiento` — opcional, solo si el cliente además quiere
  migrar su configuración de mantenimiento preventivo. No bloquea la
  primera.

Sin decisiones de diseño pendientes en esta parte.

## 4. Próximos pasos

1. ~~Definir la convención de redondeo de §1.3~~ — ✅ Resuelto al
   construir: `round(dias / 30.44)` (`_meses_entre()` en `importar_excel.py`).
2. ~~Definir la severidad exacta de "sin `justificacion_no_aplica`"~~ —
   ✅ Confirmado con Edison (12-ago-2026): **Media** (se importa con
   advertencia, no bloquea la carga).
3. ~~Construir: ampliar `importar_excel.py`~~ — ✅ Hecho (12-ago-2026).
   Las 6 hojas nuevas son opcionales — `HOJAS_OPCIONALES` — si el cliente
   no las trae, el importador sigue funcionando exactamente igual que el
   MVP.
4. Repetir el ciclo de verificación de `PLAN_IMPORTACION_EXCEL.md` §8-§10
   (Excel con errores deliberados + Excel limpio, contra Postgres real)
   antes de dar esta fase por cerrada — ver §5, **parcialmente hecho**:
   validado sin BD, falta `--ejecutar` contra Postgres real.

## 5. Verificación realizada (12-ago-2026, sin BD)

`generar_excel_prueba_fase5.py` genera un Excel con 12 errores
deliberados sobre las 6 hojas nuevas (hojas base del MVP deliberadamente
limpias, para aislar el conteo). Corriendo `importar_excel.py --dry-run`
sin `--database-url`:

| Severidad | Esperadas | Detectadas |
|---|---|---|
| Crítica | 10 | 10 |
| Alta | 1 | 1 |
| Media | 2 | 2 |
| Baja | 0 | 0 |

Coincidencia exacta, verificado leyendo el `Registro_Desviaciones`
generado fila por fila, no solo el conteo — incluida una fila que dispara
dos reglas independientes a la vez (magnitud inexistente + sin
frecuencia/justificación), que confirma que las reglas no se pisan entre
sí. También se confirmó explícitamente el caso más importante de diseño
(§1.3): una evaluación de `EQ-F5-001/Masa` con `intervalo_adoptado_meses`
sin declarar, y 2 calibraciones reales en el archivo separadas ~6 meses,
**no genera ninguna desviación** — el importador derivó correctamente
`adoptado=6` del historial real y lo comparó contra `sugerido=12` (factores
por defecto) sin marcar exceso, exactamente como se diseñó en §1.3.

Se confirmó también que la guarda de `--ejecutar` aborta correctamente por
las 10 Críticas de estas hojas nuevas, mismo comportamiento que el MVP.

**No probado todavía:** `--ejecutar` real contra Postgres (Capas 2/3 de
estas hojas nuevas — plan/evaluación ya existente en BD — y la escritura
transaccional de las 6 tablas nuevas). Es el mismo pendiente que tuvo el
MVP hasta que Edison corrió el runbook de `PLAN_IMPORTACION_EXCEL.md` §9
— siguiente paso recomendado antes de usar esto con un cliente real que
traiga Verificaciones/ILAC/Mantenimientos.

**Limitación conocida encontrada al construir (documentada en el código,
`importar_excel.py`, junto al bloque de `Verificaciones`):** a diferencia
de Equipos/Calibraciones/Evaluaciones/Planes (que si ya existen en la BD,
se saltan sin duplicar), `Verificaciones`/`PuntosVerificacion` **no**
tienen una Capa 2/3 equivalente — si el mismo archivo se `--ejecutar` dos
veces, las verificaciones SÍ se duplican, porque `id_temporal` es una
clave que solo vive dentro del archivo, nunca se guarda en la base de
datos. El runbook de §6 lo ejercita a propósito en el paso de
idempotencia, para que quede visto y no sea una sorpresa en un cliente
real. Si algún cliente necesita re-ejecutar cargas de verificaciones de
forma segura, hay que construir esa capa cuando aparezca el caso concreto.

## 6. Runbook — probar `--ejecutar` de la Fase 5 contra un Postgres real

Mismo patrón que `PLAN_IMPORTACION_EXCEL.md` §9 — lo corre Edison en su
máquina, contra `metrogest_carga`. Asume que ya se corrió ese runbook al
menos una vez (así que `POSTGRES_BIN_DIR` y el flujo general ya son
conocidos).

**Paso 0 — prerrequisitos**

```powershell
cd "C:\Users\EDISO\OneDrive\Claude desarrollo\metrogest_v2"
venv\Scripts\activate
$env:POSTGRES_BIN_DIR = "C:\Program Files\PostgreSQL\18\bin"   # si no quedó bien guardado en .env
```

**Paso 1 — prueba negativa (reusa el fixture con errores ya generado antes)**

```powershell
python generar_excel_prueba_fase5.py excel_fase5.xlsx
python importar_excel.py excel_fase5.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga --ejecutar --sin-confirmacion
```

Esperado: 10 Crítica, 1 Alta, 2 Media (o más Bajas si `metrogest_carga` ya
tiene datos que interactúan con las Capas 2/3 de Evaluaciones) — y
`ABORTADO` sin escribir nada.

**Paso 2 — archivo limpio, dry-run sin BD**

```powershell
python generar_excel_prueba_fase5_limpio.py excel_fase5_limpio.xlsx
python importar_excel.py excel_fase5_limpio.xlsx
```

Esperado: 0 desviaciones.

**Paso 3 — dry-run CON la base de datos (ejercita Capas 2/3 nuevas)**

```powershell
python importar_excel.py excel_fase5_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga
```

Esperado: sigue en 0 desviaciones (son códigos nuevos, no deberían chocar
con nada ya cargado).

**Paso 4 — backup** (si no lo hiciste ya hoy)

```powershell
python backup_db.py
```

**Paso 5 — carga real**

```powershell
python importar_excel.py excel_fase5_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga --ejecutar --usuario-id 1
```

Esperado: `planes_verificacion: 2`, `verificaciones: 2`,
`puntos_verificacion: 2`, `evaluaciones: 2`, `planes_mantenimiento: 1`,
`mantenimientos: 1`.

**Paso 6 — verificar en la base de datos, en particular el intervalo ILAC derivado**

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -U metrogest -d metrogest_carga -c "SELECT e.codigo, r.intervalo_adoptado_meses, r.intervalo_sugerido_meses FROM evaluaciones_riesgo r JOIN magnitudes_equipo m ON m.id=r.magnitud_id JOIN equipos e ON e.id=m.equipo_id WHERE e.codigo LIKE 'EQ-F5-OK%';"
```

Esperado: la fila de `EQ-F5-OK-001` debe mostrar `intervalo_adoptado_meses
= 6` (derivado del historial real que se cargó) y
`intervalo_sugerido_meses = 12`. Este es el punto de diseño más
importante de toda la Fase 5 — si esto no sale así, es un hallazgo real,
no un detalle menor.

**Paso 7 — verificar auditoría** (igual que en §9 paso 6, para las tablas nuevas)

```powershell
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" -h localhost -U metrogest -d metrogest_carga -c "SELECT tabla, accion, fecha, usuario_id FROM registro_auditoria WHERE tabla IN ('planes_verificacion','verificaciones_intermedias','puntos_verificacion','evaluaciones_riesgo','planes_mantenimiento','mantenimientos') ORDER BY fecha DESC LIMIT 20;"
```

**Paso 8 — idempotencia (aquí se espera ver la limitación documentada arriba)**

```powershell
python importar_excel.py excel_fase5_limpio.xlsx --database-url postgresql+psycopg2://metrogest:TU_PASSWORD@localhost:5432/metrogest_carga --ejecutar --usuario-id 1 --sin-confirmacion
```

Esperado (y correcto, no es un error): `equipos`, `evaluaciones` y
`planes_verificacion`/`planes_mantenimiento` deben salir en 0 (ya
existían, se saltaron) — pero `verificaciones` y `puntos_verificacion` SE
VUELVEN A CREAR (2 y 2 de nuevo), confirmando la limitación conocida.
Si sale distinto a esto, avísame.

**Paso 9 — repórtame los resultados** y actualizo esta sección con la
evidencia real, igual que se hizo con `PLAN_IMPORTACION_EXCEL.md` §10.

## 7. Resultados reales del runbook §6 (13-ago-2026, contra `metrogest_carga`)

Ejecutado por Edison. Los 8 pasos salieron exactamente como se esperaba,
con un hallazgo adicional real en el paso de idempotencia (§8), que se
documentó en `GUIA_VALIDACION_Y_DESVIACIONES.md` §3.

| Paso | Resultado |
|---|---|
| 1. Prueba negativa (12 errores) | ✅ 10 Crítica / 1 Alta / 2 Media exactos, abortó sin escribir |
| 2. Archivo limpio, dry-run sin BD | ✅ 0 desviaciones |
| 3. Dry-run con BD | ✅ sigue en 0 |
| 4-5. Backup + carga real | ✅ `planes_verificacion: 2`, `verificaciones: 2`, `puntos_verificacion: 2`, `evaluaciones: 2`, `planes_mantenimiento: 1`, `mantenimientos: 1` |
| 6. Intervalo ILAC derivado | ✅ `EQ-F5-OK-001`: adoptado=6 (derivado del historial real, ~6 meses entre 2 calibraciones) / sugerido=12. `EQ-F5-OK-002`: adoptado=sugerido=12 (sin historial suficiente) — exactamente el diseño de §1.3 |
| 7. Auditoría | ✅ 10 filas nuevas (`crear`, `usuario_id=1`) en las 6 tablas nuevas |
| 8. Idempotencia | ✅/⚠️ Primer intento abortó correctamente por Alta de Capa 3 en Calibraciones (protección ya existente del MVP, no anticipada explícitamente para este paso pero funcionó). Al aceptar esa Alta a propósito (solo para completar la prueba) y reintentar: `equipos/magnitudes/planes_verificacion/evaluaciones/planes_mantenimiento` en 0 (correctamente omitidos), `verificaciones`/`puntos_verificacion` se duplicaron (limitación conocida, confirmada), y **`calibraciones` también se duplicó** — hallazgo nuevo: aceptar una Alta de Capa 3 inserta la fila, no la omite (ver advertencia en `GUIA_VALIDACION_Y_DESVIACIONES.md` §3) |

**Conclusión:** las 6 tablas nuevas de la Fase 5 quedan verificadas de
punta a punta contra Postgres real, con el mismo nivel de evidencia que el
MVP. El hallazgo del paso 8 no es un bug — es un comportamiento
intencional (Capa 3 confía en la decisión humana registrada) que no
estaba documentado con suficiente claridad hasta esta prueba; ya quedó
explícito para que no se preste a un error real con un cliente.

`metrogest_carga` quedó con algunas filas de prueba deliberadamente
duplicadas (2 calibraciones, 2 puntos, 2 verificaciones, 2 puntos de
verificación, 1 mantenimiento) — sin urgencia de limpiar, es una base de
staging desechable, no datos de un cliente real.

### 7.1 Corrección aplicada tras el hallazgo del paso 8 (13-ago-2026)

El hallazgo del paso 8 exponía un riesgo real más allá de la documentación:
si alguien marca una Alta de Capa 3 como `Resuelta - corregida en origen`
(prometiendo que la corrigió en el Excel de origen) pero en realidad la
corrección no llegó al archivo — por ejemplo porque olvidó regenerar la
plantilla — el importador la habría dejado pasar igual, confiando
ciegamente en esa nota. Documentarlo como advertencia (§3 de
`GUIA_VALIDACION_Y_DESVIACIONES.md`) no es suficiente cuando el costo de
un descuido humano es un duplicado real insertado en la base de datos de
un cliente.

**Decisión: no basta con advertir, el importador debe hacer cumplir la
distinción.** Se modificó `cargar_registro_resueltas()` en
`importar_excel.py` para que **solo** `Aceptada...` y `Resuelta -
corrección manual documentada` cuenten como definitivamente resueltas.
`Resuelta - corregida en origen` **ya no desbloquea `--ejecutar`** — si esa
clave reaparece en una corrida posterior (señal de que la corrección
prometida no se aplicó de verdad), el importador sigue abortando, igual
que si nunca se hubiera marcado. El mensaje de abort de `--ejecutar`
también se amplió para explicarle al operador esta distinción en el
momento en que la necesita, no solo en la documentación.

Verificado (13-ago-2026, sandbox, sin BD):

- Prueba aislada de `cargar_registro_resueltas()` sobre un registro de 2
  filas (una `Resuelta - corregida en origen`, otra `Aceptada como
  excepción`): el resultado solo incluye la clave `Aceptada` — confirma
  que "corregida en origen" ya no cuenta como resuelta.
- Regresión completa del fixture de 14 errores del MVP
  (`generar_excel_prueba_migracion.py`): mismo resultado de siempre
  (8 Crítica / 1 Alta / 3 Media / 2 Baja) — el cambio no afecta ningún otro
  flujo.

**Confirmado contra Postgres real (13-ago-2026, `metrogest_carga`, corrida
por Edison):** se repitió el paso 8 marcando explícitamente `Aceptada como
excepcion` (no `corregida en origen`) en las dos Altas de Capa 3 del
Registro de Desviaciones. La carga con `--ejecutar
--registro-resueltas` esta vez sí pasó y completó:
`calibraciones: 2` (insertadas de nuevo, confirma que "Aceptada" sí deja
pasar e insertar, tal como se diseñó), `verificaciones: 2` /
`puntos_verificacion: 2` (duplicados de nuevo — limitación conocida,
consistente), `mantenimientos: 1` (misma limitación, `Mantenimiento` tampoco
tiene deduplicación en BD). Nada de esto es un bug — es exactamente el
comportamiento esperado tras el fix, y cierra el pendiente: la lógica que
distingue "corregida en origen" de "Aceptada" queda verificada tanto en
aislamiento (sandbox, turno anterior) como end-to-end contra Postgres real.

Nota operativa del propio ejercicio de verificación: la primera vez que se
intentó, la edición del Excel en Excel no se guardó de verdad en la celda
esperada (el diagnóstico con `openpyxl` mostró `'Abierta'` en vez de
`'Aceptada...'` pese a haber "editado y guardado"). Se resolvió editando el
archivo por script en vez de a mano. Vale la pena tenerlo presente para la
`GUIA_VALIDACION_Y_DESVIACIONES.md`: al trabajar el Registro de
Desviaciones con un cliente, conviene verificar con un vistazo rápido
(o el mismo diagnóstico por script) que el `estado` quedó realmente
grabado antes de asumir que `--registro-resueltas` va a leerlo — un
Registro "editado" que en realidad no se guardó es indistinguible a
simple vista de uno bien editado.
