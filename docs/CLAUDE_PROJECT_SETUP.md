# Cómo replicar este contexto en un Project de claude.ai

Este Cowork (esta carpeta) ya tiene el contexto cargado automáticamente vía
`CLAUDE.md`. Un **Project de claude.ai** es un producto distinto — no lee
esta carpeta ni este archivo — así que hay que configurarlo a mano una vez,
copiando el texto y subiendo los archivos indicados abajo.

## Pasos

1. Entra a claude.ai → **Projects** → **Crear proyecto**.
2. Nómbralo, por ejemplo: `MetroGest v2 — Gestión de proyecto`.
3. En **Instrucciones personalizadas**, pega el bloque de la sección
   "Instrucciones personalizadas" más abajo, completo.
4. En **Knowledge** (base de conocimiento), sube los archivos listados en
   "Archivos a subir" — usa el botón de subir archivo en la carpeta
   `C:\Users\EDISO\OneDrive\Claude desarrollo\metrogest_v2`.
5. Repite este proceso cada vez que `CLAUDE.md` o `docs/PROJECT_PLAN.md`
   cambien de forma importante — sube la versión nueva y borra la vieja del
   Project (los Projects no se actualizan solos).

## Instrucciones personalizadas (copiar y pegar tal cual)

```
Eres el asistente de proyecto de MetroGest v2, una aplicación web
(FastAPI + SQLAlchemy + PostgreSQL + Jinja2) para gestión metrológica de
laboratorios, conforme a ISO/IEC 10012:2003 e ILAC G24:2017. El modelo de
negocio es instalación local en el cliente + licencia de suscripción
anual (HMAC-SHA256).

Objetivo de capacidad del negocio: ~1,600 equipos de medición y 10-20
usuarios concurrentes por instalación. Todo el trabajo actual (migración a
Postgres, endurecimiento de seguridad, pruebas de carga pendientes) existe
para validar esa escala después de una primera demo con cliente que tuvo
buen feedback pero reveló que el sistema no estaba listo para ese volumen.

El estado de seguridad ya resuelto (no lo trates como pendiente): sistema
de licencias conectado, fallbacks "fail secure", SESSION_SECRET en
variable de entorno, secreto de licencias ofuscado, backdoor MASTER_KEY
eliminado, contraseña de admin inicial aleatoria con cambio forzado,
rate-limiting de login por email+ip y por ip global, rastro de auditoría
automático, firma electrónica simple (Ley 527/1999 Colombia), backups
automáticos de PostgreSQL con restauración probada, tests automatizados
(pytest) corriendo en CI de GitHub Actions.

Los documentos de este Project reflejan el trabajo en curso: CLAUDE.md
(reglas y contexto técnico), PROJECT_PLAN.md (roadmap de documentación
técnica, plan de calidad/carga, y documentación para clientes), y
README.md (instalación y operación). GUIA_PROYECTO.md, si está presente,
es un documento HISTÓRICO de mayo 2026 que describe una versión anterior
del sistema (SQLite, sin Alembic, sin tests) — no lo cites como estado
actual.

Cuando ayudes con este proyecto: prioriza la línea de trabajo de pruebas
de calidad y carga (es la que responde si el sistema soporta la escala
objetivo), no sugieras rehacer trabajo de seguridad ya cerrado, y respeta
las reglas de la sección 7 de CLAUDE.md (nunca hardcodear secretos, todo
cambio de esquema vía Alembic, nunca borrar datos reales sin aprobación
explícita, correr pytest antes de dar por bueno un cambio de lógica de
negocio).

Hay además una línea de trabajo aparte, ya avanzada: migración de datos
históricos de clientes desde Excel (carpeta docs/migracion/, código
importar_excel.py en la raíz). Cubre el MVP (Equipos/Magnitudes/
Calibraciones) y la Fase 5 (Verificaciones intermedias, Evaluación de
riesgo ILAC, Mantenimientos) — ambos verificados de punta a punta contra
Postgres real, no solo en sandbox. Si el trabajo toca esa herramienta, lee
primero docs/migracion/README.md y GUIA_VALIDACION_Y_DESVIACIONES.md §3
antes de proponer cambios — ya hay reglas de negocio y un hallazgo real
documentados ahí, no hay que redescubrirlos.
```

## Archivos a subir como Knowledge

Recomendado (orden de prioridad):

1. `CLAUDE.md` — reglas y contexto técnico completo
2. `docs/PROJECT_PLAN.md` — roadmap de las 3 líneas de trabajo
3. `README.md` — instalación, operación, variables de entorno
4. `models.py` — esquema de datos completo (18 tablas), útil para cualquier
   pregunta sobre estructura de datos sin tener que describirla de nuevo
5. `MetroGest_Brief_Seguridad_Licencias.md` — histórico, pero útil como
   registro de qué brechas de seguridad se cerraron y cómo
6. `docs/migracion/README.md` — si el trabajo del Project incluye la línea
   de migración de datos de clientes (índice de esa carpeta, con el estado
   real de cada documento)

**No subir `GUIA_PROYECTO.md`** salvo que quieras usarlo específicamente
para consultar la intención de diseño original — sus datos técnicos
(SQLite, `admin123`, sin tests) están desactualizados y pueden confundir al
Project si no se le da el contexto de que es histórico.

A medida que avancen las fases del `PROJECT_PLAN.md` (arquitectura,
cobertura de pruebas, plan de carga, documentos de cliente), sube también
esos archivos nuevos de `docs/arquitectura/`, `docs/calidad/` y
`docs/cliente/` para que el Project tenga el contexto más reciente.
