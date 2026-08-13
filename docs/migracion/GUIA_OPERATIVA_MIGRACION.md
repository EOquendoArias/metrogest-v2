# Guía operativa — cómo correr una migración real de un cliente

> Fase 6 de `PLAN_IMPORTACION_EXCEL.md` §2: documentación operativa final.
> Este documento es el **punto de entrada único** para Edison (o cualquier
> sesión de Claude que retome este trabajo) cuando toca migrar el
> historial de un cliente real — no repite el diseño ni las reglas de
> negocio, que ya están en los documentos de §1 de abajo; aquí está **el
> orden en que se usan** y los comandos exactos, incluidos los tropiezos
> reales que ya salieron al ejecutar este proceso con `metrogest_carga`.

## 1. Mapa de documentos — qué leer y cuándo

| Documento | Cuándo usarlo |
|---|---|
| `docs/cliente/GUIA_PREPARACION_DATOS.md` | **Primero, se lo envías al cliente** — checklist en lenguaje simple de qué debe reunir antes de que empieces a trabajar su Excel. |
| `RECETA_POWER_QUERY.md` | Cuando ya tienes el Excel del cliente y hay que transformarlo a la plantilla estándar. **Interno, no se comparte con el cliente** (ver razonamiento dentro del propio documento). |
| `PLAN_IMPORTACION_EXCEL.md` §3 | Referencia del esquema exacto de la plantilla estándar (Equipos/Magnitudes/Calibraciones/PuntosCalibracion) — qué columnas son obligatorias, cuáles no. |
| `PLAN_FASE5_EXTENSIONES.md` §1.4 y §2.2 | Igual que arriba, pero para las 6 hojas opcionales (Verificaciones, ILAC, Mantenimientos), si el cliente también las trae. |
| `GUIA_VALIDACION_Y_DESVIACIONES.md` | El framework de *proceso*: cómo clasificar y resolver desviaciones con el cliente, la plantilla del Registro de Desviaciones, y la regla operativa sobre "Aceptada" vs. "corregida en origen" (§3 — importante, ya causó un hallazgo real). |
| **Este documento** | El flujo completo de principio a fin, con los comandos reales. |

## 2. Flujo completo, de principio a fin

```
1. Enviar docs/cliente/GUIA_PREPARACION_DATOS.md al cliente
        │
        ▼
2. Recibir su(s) Excel(es) → transformarlos con la receta de Power Query
   (RECETA_POWER_QUERY.md) a la plantilla estándar (1 archivo .xlsx con
   las hojas de §3 de PLAN_IMPORTACION_EXCEL.md, y si aplica, las 6 hojas
   opcionales de PLAN_FASE5_EXTENSIONES.md)
        │
        ▼
3. --dry-run SIN --database-url (§3.1 abajo) → revisar que el esquema
   de la plantilla esté bien formado, sin conectar todavía a nada real
        │
        ▼
4. --dry-run CON --database-url, apuntando a una BD de STAGING primero,
   nunca directo a la del cliente (§3.2) → ahora sí se activan las
   Capas 2/3 de duplicados
        │
        ▼
5. Trabajar el Registro de Desviaciones con el cliente
   (GUIA_VALIDACION_Y_DESVIACIONES.md §5) hasta que no queden Críticas,
   y las Altas estén Resueltas o Aceptadas
        │
        ▼
6. Backup de la base de datos REAL del cliente (backup_db.py) — NUNCA
   te saltes este paso, aunque el dry-run haya salido perfecto
        │
        ▼
7. --ejecutar contra la base de datos REAL del cliente (§3.3)
        │
        ▼
8. Verificar en la BD que los datos quedaron bien + que el rastro de
   auditoría se generó (§4 abajo)
        │
        ▼
9. Archivar el Registro de Desviaciones final + la evidencia de esta
   migración (§5 abajo) — para un cliente farmacéutico, esto es
   literalmente lo que un auditor va a pedir ver
```

### 3.1 Paso 3 — dry-run sin base de datos

```powershell
cd "C:\Users\EDISO\OneDrive\Claude desarrollo\metrogest_v2"
venv\Scripts\activate
python importar_excel.py plantilla_cliente.xlsx
```

Solo valida estructura, tipos, referencias dentro del archivo y reglas de
negocio (niveles 1-4 de `PLAN_IMPORTACION_EXCEL.md` §4, más ILAC/plan de
verificación de Fase 5). No compara contra ninguna base de datos — sirve
para limpiar el archivo antes de gastar tiempo conectando a nada.

### 3.2 Paso 4 — dry-run contra staging (activa Capas 2/3)

```powershell
python importar_excel.py plantilla_cliente.xlsx --database-url postgresql+psycopg2://usuario:PASSWORD_REAL@host:5432/nombre_bd_staging
```

**Nunca dejes `PASSWORD_REAL` como placeholder literal** — ya pasó en este
proyecto (ver §6, "problemas ya encontrados"). Reemplázalo siempre por la
contraseña real antes de correr el comando.

### 3.3 Paso 7 — carga real

```powershell
python backup_db.py

python importar_excel.py plantilla_cliente.xlsx `
  --database-url postgresql+psycopg2://usuario:PASSWORD_REAL@host:5432/base_del_cliente `
  --ejecutar `
  --usuario-id ID_DEL_USUARIO_RESPONSABLE `
  --registro-resueltas Registro_Desviaciones_trabajado_con_cliente.xlsx `
  --confirmo-produccion
```

Notas sobre las banderas de este comando:

- **`--usuario-id`**: siempre inclúyelo contra una base real de cliente —
  sin esto, cada fila del rastro de auditoría queda con `usuario_id NULL`,
  lo cual es un problema real para trazabilidad GxP con clientes
  farmacéuticos.
- **`--registro-resueltas`**: el archivo que resultó de trabajar las
  desviaciones con el cliente (paso 5), con la columna `estado` puesta en
  `Aceptada como excepcion` o `Resuelta - corrección manual documentada`
  para cada Alta que se decidió dejar pasar. **`Resuelta - corregida en
  origen` no cuenta como resuelta** — es una promesa de que ya se corrigió
  en el archivo de origen; si la fila reaparece, el importador sigue
  bloqueando a propósito (ver `GUIA_VALIDACION_Y_DESVIACIONES.md` §3).
- **`--confirmo-produccion`**: obligatoria si el nombre de la base de
  datos no contiene "test"/"staging"/"stg"/"carga" — es la base real del
  cliente, así que sí la vas a necesitar aquí (a diferencia de las pruebas
  contra `metrogest_carga`, donde no hace falta).
- **`--actualizar-existentes`**: normalmente NO la uses. Sin ella, un
  equipo que ya existe en la BD se omite sin tocar sus campos — es el
  comportamiento seguro por defecto. Solo actívala si el cliente pidió
  explícitamente actualizar equipos ya cargados con datos nuevos del
  Excel, y entiendes que sobrescribe campos existentes.
- **Nunca uses `--sin-confirmacion`** contra una base real de cliente —
  esa bandera existe solo para pruebas automatizadas, y salta la
  confirmación interactiva `SI` que es la última barrera antes de escribir.

El comando va a preguntar si ya hiciste el backup (contesta que sí, ya lo
hiciste arriba) y luego va a pedir escribir `SI` en mayúsculas para
confirmar. Después de eso, imprime el resumen de conteos creados por
tabla — revísalo contra lo que esperabas antes de dar la migración por
cerrada.

## 4. Verificación post-carga (obligatoria, no opcional)

Con `psql` o pgAdmin contra la base del cliente:

```sql
-- Conteos generales, ajusta los filtros a los códigos reales del cliente
SELECT COUNT(*) FROM equipos;
SELECT COUNT(*) FROM calibraciones;

-- Confirmar que el rastro de auditoría se generó (no darlo por hecho,
-- ver el hallazgo real documentado en PLAN_IMPORTACION_EXCEL.md §10)
SELECT tabla, accion, COUNT(*) FROM registro_auditoria
  WHERE usuario_id = ID_DEL_USUARIO_RESPONSABLE
  GROUP BY tabla, accion
  ORDER BY tabla;
```

Si `registro_auditoria` sale vacío para esta carga, **no sigas** — es un
hallazgo real, no una corrida más. Repórtalo antes de continuar.

## 5. Cierre y archivo de evidencia

Para cada migración de cliente, archiva (fuera del repo de código, en la
carpeta de evidencia del cliente):

1. El Excel original que envió el cliente (sin transformar).
2. La plantilla estándar ya transformada (el archivo que realmente se
   cargó).
3. El Registro de Desviaciones **final**, con `estado`/`decision`/
   `decidido_por`/`fecha_cierre` completos para cada fila.
4. La salida completa de consola del `--ejecutar` (conteos creados).
5. La confirmación del backup previo (`backup_db.py`) con fecha/hora.

Para un cliente farmacéutico, este paquete es la evidencia de integridad
de datos migrados que un auditor de CSV va a pedir ver — no es
burocracia, ver `CLAUDE.md` §1 sobre el requisito de validación de
sistemas computarizados para ese segmento.

## 6. Problemas ya encontrados al correr este proceso — revisa aquí antes de reportar un bug

Estos ya salieron ejecutando este flujo contra `metrogest_carga` real —
no son teoría, y probablemente se repitan con un cliente real si no se
tienen presentes:

- **`FileNotFoundError` en `backup_db.py` (`pg_dump.exe` no encontrado)**:
  `POSTGRES_BIN_DIR` en `.env` asume una versión de Postgres específica.
  Verifica la versión real instalada (`Get-ChildItem -Path "C:\Program
  Files" -Recurse -Filter "pg_dump.exe"` en PowerShell) y ajusta la
  variable — esto ya es un ítem obligatorio del checklist de instalación
  (IQ-3 en `docs/calidad/validacion_farma/IQ_CALIFICACION_INSTALACION.md`),
  así que en una instalación de cliente ya calificada no debería
  sorprenderte; si te pasa, es señal de que esa IQ no se hizo bien.
- **`'utf-8' codec can't decode byte 0xf3...' al conectar a la BD**: casi
  siempre significa que la contraseña en `--database-url` está mal (a
  veces porque se dejó un placeholder tipo `TU_PASSWORD` sin reemplazar,
  literal) — Postgres devuelve el mensaje de error de autenticación en
  español con tildes codificadas en Latin-1, y el driver falla al
  decodificarlo como UTF-8, enmascarando el verdadero problema. Si ves
  este error, sospecha primero de la contraseña/usuario en la URL, no de
  un bug de codificación.
- **Editaste el `estado` en el Registro de Desviaciones en Excel, guardaste,
  y el importador sigue diciendo que la fila no está resuelta**: verifica
  que el cambio realmente quedó grabado antes de asumir que
  `--registro-resueltas` no lo lee. Diagnóstico rápido sin abrir Excel:

  ```powershell
  python -c "import openpyxl; wb=openpyxl.load_workbook('ARCHIVO.xlsx', data_only=True); ws=wb.active; rows=list(ws.iter_rows(values_only=True)); h=rows[0]; idx={n:i for i,n in enumerate(h)}; [print(repr(r[idx['clave']]), '|', repr(r[idx['estado']])) for r in rows[1:] if r]"
  ```

  Si sigue mostrando `'Abierta'`, el archivo no se guardó de verdad — edítalo
  de nuevo (o hazlo por script, más confiable que editar a mano en Excel).
- **Aceptar una Alta de Capa 3 (calibración/verificación probablemente
  duplicada) SÍ inserta la fila, no la omite** — es el comportamiento
  diseñado (ver `GUIA_VALIDACION_Y_DESVIACIONES.md` §3), pero es fácil
  asumir lo contrario la primera vez. Antes de aceptar una Alta de Capa 3,
  confirma con el cliente que de verdad es una segunda medición real y no
  un duplicado accidental — si es accidental, corrígelo en el Excel de
  origen en vez de aceptarlo.
- **Re-ejecutar la misma carga (`--ejecutar`) dos veces duplica
  `Verificaciones`, `PuntosVerificacion` y `Mantenimientos`** — estas 3
  tablas no tienen detección de duplicados contra la BD (limitación
  conocida, documentada en `PLAN_FASE5_EXTENSIONES.md` §5). Si necesitas
  reintentar una carga que falló a medias, revisa primero si ya insertó
  algo de estas 3 tablas antes de correrla de nuevo.
