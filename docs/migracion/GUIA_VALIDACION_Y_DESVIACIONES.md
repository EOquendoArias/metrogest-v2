# Framework de validación y manejo de desviaciones — Migración de datos

> Responde a la petición de Edison (12-ago-2026): sin clientes todavía
> para probar el importador contra datos reales, pero el **proceso** debe
> quedar construido y documentado desde ahora — cómo se organiza la
> información antes de subirla, y cómo se detectan, documentan y resuelven
> con el cliente las desviaciones que aparezcan, incluida la corrección
> manual. Este documento define el **proceso** (qué pasa cuando algo no
> pasa la validación); `PLAN_IMPORTACION_EXCEL.md` §4-§5 ya define **qué**
> se valida y cómo se detectan duplicados — no se duplica ese contenido
> aquí, se construye encima.

## 1. Qué es una "desviación" en este contexto

Cualquier fila, campo o relación del Excel de origen que **no cumple
alguno de los 5 niveles de validación** de `PLAN_IMPORTACION_EXCEL.md` §4,
o que la Capa 2/3 de detección de duplicados (§5 del mismo documento)
marca como sospechosa. No es un término vago — cada desviación tiene una
fila exacta, una hoja exacta y una regla exacta que no cumplió, porque el
importador la reporta así (§4 del plan: "una fila por problema
encontrado, con hoja/fila/columna/descripción").

## 2. Checklist de organización de la información antes de cargar

Esto es lo primero que se le pide al cliente (o lo primero que organiza
Edison si recibe los archivos sueltos), **antes** de tocar Power Query —
evita que la mitad de las desviaciones sean simplemente "faltó juntar
esto":

- [ ] **Un listado maestro de equipos** con código único por equipo (si el
      cliente no tiene códigos consistentes hoy, es el primer problema a
      resolver con él — sin código único no hay forma de ligar historial a
      equipo de forma confiable).
- [ ] **El historial de calibraciones agrupado por equipo**, aunque esté
      en hojas separadas por año — Power Query las combina, pero deben
      estar identificables (mismo formato de fecha, mismo criterio de qué
      cuenta como "una calibración").
- [ ] **Certificados de calibración como archivos PDF individuales**
      (para la carga posterior de `certificado_path`, fuera del alcance de
      este importador — ver nota al final), idealmente nombrados de forma
      que se puedan asociar al `numero_certificado` de la hoja.
- [ ] **Confirmación de qué magnitudes mide cada equipo** — si el Excel
      del cliente no separa "equipo" de "magnitud" (común: una fila por
      calibración con el nombre del equipo repetido), es una transformación
      de Power Query, no un error, pero hay que saberlo de antemano.
- [ ] **El EMP (error máximo permisible) de cada magnitud**, si existe
      documentado — sin esto, el semáforo de conformidad no puede
      calcularse y la magnitud queda sin control visual tras la carga (ver
      `PLAN_IMPORTACION_EXCEL.md` §3, nota de `emp_valor`).

## 3. Clasificación de desviaciones por severidad

| Severidad | Significa | Bloquea la carga | Ejemplos concretos |
|---|---|---|---|
| **Crítica** | El dato no se puede insertar sin romper integridad referencial | Sí, siempre | `id_temporal_calibracion` de un punto que no existe en la hoja `Calibraciones`; `codigo_equipo` de una magnitud que no existe en `Equipos`; `codigo` de equipo repetido dentro del mismo Excel (Capa 1, §5 del plan) |
| **Alta** | El dato se podría insertar, pero hacerlo sin decisión humana arriesga corromper el historial de calidad | Sí, hasta que el cliente decida | Calibración que coincide con la Capa 3 de duplicados (mismo equipo+magnitud+fecha+certificado ya en la BD); `resultado` importado no coincide con el semáforo recalculado a partir de los puntos (nivel 4 de validación) |
| **Media** | El dato se importa, pero queda con una limitación funcional conocida | No, se importa con advertencia | Magnitud sin `emp_valor` (queda sin semáforo); equipo sin `estado` (entra como `en_espera_calibracion` por defecto, puede no ser el estado real) |
| **Baja** | Informativa, no afecta funcionalidad | No | Campos opcionales vacíos (`marca`, `ubicacion`, `laboratorio`...); fecha de calibración muy antigua (posible pero razonable en 5 años de historial) |

Las **críticas y altas nunca se resuelven en silencio ni las decide el
importador solo** — pasan por el flujo de §5. Las medias y bajas se
importan igual, pero quedan en el registro de desviaciones para que el
cliente sepa exactamente qué le falta a sus datos ya migrados.

**Advertencia operativa importante, verificada con evidencia real
(13-ago-2026):** "aceptar" una Alta de Capa 3 (calibración/verificación
probablemente duplicada) no es lo mismo que "omitir" — el importador SÍ
inserta la fila cuando la Alta queda resuelta. Esto es intencional para
Calibraciones y Verificaciones (a diferencia de un Equipo, una calibración
"duplicada" puede ser legítimamente una segunda calibración real el mismo
día con el mismo certificado). Por eso `estado` en el Registro de
Desviaciones no es un texto libre decorativo — el importador distingue
dos casos, y solo uno deja pasar `--ejecutar`:

- **`Resuelta - corregida en origen`** → es una promesa de que la fila se
  quitó o corrigió en el Excel de origen y se regeneró la plantilla. El
  importador **no la trata como resuelta** — si esa misma fila sigue
  apareciendo en la corrida siguiente (porque la corrección no llegó de
  verdad al archivo), `--ejecutar` **sigue bloqueando**, no inserta nada
  a ciegas confiando en una nota vieja.
- **`Aceptada como excepción`** (o `Resuelta - corrección manual
  documentada`) → decisión consciente de que el dato es correcto tal como
  está. Esta sí deja pasar `--ejecutar`, y el importador inserta la fila.

**Regla práctica: si de verdad es un duplicado accidental, corrígelo en el
Excel de ORIGEN y usa "Resuelta - corregida en origen" — el importador te
protege si se te olvidó aplicar la corrección de verdad. Si es una
segunda calibración/verificación real, usa "Aceptada" a propósito.**

## 4. Plantilla del Registro de Desviaciones

Un archivo por migración (Excel o CSV), que el modo `--dry-run` del
importador genera automáticamente como punto de partida y que luego se
completa a mano durante la resolución con el cliente:

| Columna | Contenido |
|---|---|
| `id_desviacion` | Correlativo, ej. `DEV-001` |
| `hoja` / `fila` | Ubicación exacta en el Excel de origen |
| `campo` | Columna afectada |
| `severidad` | Crítica / Alta / Media / Baja (§3) |
| `regla_violada` | Cuál de los 5 niveles de validación o de las 3 capas de duplicados detectó el problema |
| `valor_encontrado` | Lo que traía el Excel |
| `valor_esperado_o_conflicto` | Qué se esperaba, o con qué registro existente choca |
| `fecha_deteccion` | Generada automáticamente por el dry-run |
| `estado` | `Abierta` / `En revisión con cliente` / `Resuelta — corregida en origen` / `Resuelta — corrección manual documentada` / `Aceptada como excepción` |
| `decision` | Qué se decidió hacer y por qué (texto libre, obligatorio antes de cerrar) |
| `decidido_por` | Nombre de quien tomó la decisión — Edison, o explícitamente el cliente |
| `fecha_cierre` | Cuándo se cerró |

Este registro **se archiva junto con la evidencia de la migración**, no se
descarta después de la carga — para un cliente farmacéutico, es
exactamente el tipo de documento que un auditor pide al preguntar "¿cómo
se garantizó la integridad de los datos históricos migrados?".

## 5. Flujo de resolución conjunta con el cliente

```
1. Correr el importador en modo --dry-run
        │
        ▼
2. El reporte de desviaciones se carga en la plantilla del Registro (§4)
        │
        ▼
3. Edison prioriza: primero Críticas y Altas (bloquean o arriesgan datos),
   luego Medias/Bajas (informativas)
        │
        ▼
4. Sesión de revisión CON el cliente — nunca se decide unilateralmente
   una desviación Crítica o Alta que involucre datos de calidad:
   ┌─────────────────────────────┬─────────────────────────────────┐
   │ El cliente confirma que es  │ El cliente confirma que el dato  │
   │ un error de captura         │ es correcto tal como está        │
   │        │                    │        │                        │
   │        ▼                    │        ▼                        │
   │ Se corrige en el Excel de   │ Se documenta como excepción      │
   │ ORIGEN (nunca en la         │ aceptada, con la justificación   │
   │ plantilla ya transformada — │ del cliente en la columna        │
   │ ver §6) y se repite Power   │ `decision` — ej. "dato histórico │
   │ Query desde ese punto       │ incompleto, equipo dado de baja  │
   │                             │ antes de digitalizar registros"  │
   └─────────────────────────────┴─────────────────────────────────┘
        │
        ▼
5. Se vuelve a correr --dry-run hasta que no queden desviaciones
   Críticas, y las Altas estén todas en estado Resuelta o Aceptada
        │
        ▼
6. Solo entonces se corre en modo --ejecutar (con backup previo,
   ver PLAN_IMPORTACION_EXCEL.md §6)
        │
        ▼
7. El Registro de Desviaciones final (incluidas las aceptadas, con su
   justificación) se archiva como evidencia de la migración
```

## 6. Dónde se corrige cada tipo de desviación — regla clara, no ambigua

- **Regla general y preferida: se corrige en el Excel de ORIGEN**, nunca
  directamente en la plantilla estándar ya transformada por Power Query.
  Razón: si se edita la plantilla a mano, la próxima vez que alguien
  vuelva a correr la transformación de Power Query (por ejemplo, porque
  llegó una hoja adicional del cliente) esa corrección manual se pierde
  sin dejar rastro. Corregir en el origen mantiene una sola fuente de
  verdad reproducible.
- **Excepción controlada**: si el dato no existe en ningún Excel de
  origen y la corrección es una decisión del cliente sobre un valor que
  simplemente no se puede recuperar (ej. "no tenemos el EMP de ese
  instrumento, se dio de baja hace 3 años"), la corrección se aplica
  directamente en la plantilla estándar, **pero queda obligatoriamente
  registrada** en el Registro de Desviaciones (§4) con `estado = Resuelta
  — corrección manual documentada` y la justificación en `decision`. Una
  edición manual sin ese registro no es una corrección válida para efectos
  de evidencia de migración.
- **Nunca se corrige silenciosamente dentro del importador Python** — el
  importador valida y reporta, no "arregla" datos por su cuenta (ej. no
  redondea, no adivina una fecha, no descarta un duplicado sin dejarlo en
  el reporte).

## 7. Fuera de alcance de este framework (déjalo anotado, no lo resuelvas ahora)

- La carga masiva de los **archivos PDF de certificados** (no solo el
  registro tabular de la calibración) es un problema aparte — requiere
  asociar cada archivo físico a su `id_temporal`/`numero_certificado` y
  copiarlo a `static/certificados/` con el mismo validador de tamaño que
  ya usa la app (`utils/validar_archivo.py`, 15 MB por documento). No se
  diseña en este documento; queda anotado para cuando haya un cliente real
  con volumen de certificados que dimensionar.
- Este framework asume que el cliente puede, en algún momento, sentarse a
  revisar desviaciones Altas/Críticas contigo. Si algún cliente no tiene
  esa disponibilidad, la política por defecto (§3: nunca importar
  Críticas, nunca importar Altas sin decisión) significa que la migración
  simplemente no avanza más allá de lo que sí pasó validación limpia —
  es una limitación a comunicar de antemano, no algo que este framework
  resuelva solo.
