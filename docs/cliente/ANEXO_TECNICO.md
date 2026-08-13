# MetroGest v2 — Anexo técnico

> Para el equipo técnico/TI del cliente o un auditor externo. Cita
> evidencia real de pruebas ya ejecutadas (no promesas de diseño) —
> cada afirmación enlaza al documento fuente donde se puede verificar el
> detalle completo. Complementa [`RESUMEN_EJECUTIVO.md`](RESUMEN_EJECUTIVO.md)
> (audiencia de negocio, sin este nivel de detalle).

## 1. Arquitectura

Aplicación monolítica de servidor: **FastAPI + SQLAlchemy 2.0 + Jinja2
(server-side rendering) + PostgreSQL**, sin frontend framework separado.
Se instala localmente en el servidor del cliente — los datos nunca salen
de su infraestructura. Descripción completa de capas, orden real de
middlewares y modelo de datos (20 tablas) en
`docs/arquitectura/ARQUITECTURA.md`; decisiones de diseño relevantes, con
su razonamiento y resultados medidos, en `docs/arquitectura/DECISIONES.md`.

**Requisitos de infraestructura** (medidos, no estimados — ver §4):
PostgreSQL 14+, Python 3.10+, ~4 GB de RAM dedicados a la instalación
completa (aplicación + PostgreSQL + sistema operativo) como punto de
partida para la configuración recomendada de varios procesos concurrentes.

## 2. Seguridad

| Control | Mecanismo | Evidencia |
|---|---|---|
| Autenticación | bcrypt, contraseña de administrador inicial aleatoria con cambio forzado en primer login (sin contraseña por defecto) | `tests/test_auth.py`, `tests/test_ciclo_vida_licencia.py` |
| Protección contra fuerza bruta | Bloqueo de login por (email+IP) y por IP global | `tests/test_auth.py` |
| Control de acceso por rol | 3 roles (administrador / operador / solo_lectura), privilegio mínimo, verificado a nivel HTTP en 23+ endpoints de escritura | `tests/test_rbac.py`, `tests/test_rbac_ampliado.py` |
| Rastro de auditoría | Automático (listeners de SQLAlchemy, no requiere que cada módulo lo invoque), registra usuario, campo, valor anterior/nuevo y fecha del servidor | `tests/test_auditoria_trail.py` |
| Firma electrónica | Reautenticación con contraseña en las decisiones críticas (aprobar calibración, cerrar verificación, definir intervalos ILAC, cambiar estado de equipo) — conforme a Ley 527/1999 (Colombia) | `tests/test_firma_electronica.py` + tests de flujo end-to-end |
| Cifrado de sesión | Cookie de sesión firmada, `SESSION_SECRET` obligatorio en variables de entorno (la aplicación no arranca sin él) | Verificación en arranque (`main.py`) |
| Cabeceras HTTP de seguridad | `X-Frame-Options`, `X-Content-Type-Options`, `Referrer-Policy`, `Content-Security-Policy`, `HSTS` condicionado a HTTPS real | `docs/calidad/CHECKLIST_SEGURIDAD.md` B3 |
| Validación de archivos subidos | Extensión y tamaño máximo por tipo (imágenes 5 MB, documentos 15 MB) | `utils/validar_archivo.py`, `docs/calidad/CHECKLIST_SEGURIDAD.md` B4 |
| Archivos protegidos | Fotos, manuales y certificados exigen sesión iniciada para descargarse — no son de acceso público por URL | `docs/calidad/CHECKLIST_SEGURIDAD.md` B5 |
| Manejo de errores | Página de error genérica sin fuga de información interna (mensajes de excepción solo van al log del servidor) | `docs/calidad/CHECKLIST_SEGURIDAD.md` B6 |
| Registros no eliminables físicamente | Puntos de calibración y de verificación se marcan `eliminado` con usuario/fecha, nunca se borran de la base de datos | `docs/calidad/CHECKLIST_SEGURIDAD.md` B8 |
| Licencia | HMAC-SHA256, secreto ofuscado; licencia vencida pasa el sistema a modo solo lectura automáticamente, sin pérdida de datos | `tests/test_ciclo_vida_licencia.py` |

El detalle completo, con qué está automatizado por test y qué requiere
verificación manual antes de cada entrega, está en
`docs/calidad/CHECKLIST_SEGURIDAD.md`. Ese documento registra también 3
desviaciones abiertas conocidas (cabeceras HTTP, validación de archivos y
servido de archivos protegidos funcionan pero aún no tienen test
automatizado dedicado) — no son brechas de seguridad, son huecos de
cobertura de prueba ya identificados y a cerrar.

## 3. Suite de pruebas automatizadas

105 tests automatizados (`pytest`), corridos contra una base de datos
PostgreSQL de prueba real (no simulada), integrados en CI de GitHub
Actions en cada cambio. Cubren desde funciones de cálculo puro (semáforo
de conformidad, regresión polinomial, análisis de deriva ILAC) hasta
flujos de negocio completos de principio a fin por HTTP real: alta de
equipo → evaluación de riesgo → calibración → aprobación con firma
electrónica; verificación intermedia con registro de puntos y cierre;
mantenimiento y su efecto sobre el estado del equipo; ciclo de vida
completo de licencia; generación de PDF/Excel. Inventario completo de qué
está cubierto y qué no en `docs/calidad/COBERTURA.md` y
`docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md`.

Como parte de este trabajo se encontraron y corrigieron 3 defectos reales
antes de que llegaran a un cliente: una condición que permitía re-aprobar
una calibración ya aprobada sin ningún control, un error que dejaba
bloqueado en modo error el aviso de licencia vencida (en vez de mostrar la
página de renovación), y un caso en el que eliminar el único punto fuera
de tolerancia de una verificación no recalculaba el resultado agregado.
Los tres quedan cerrados y cubiertos por test de regresión.

## 4. Evidencia de capacidad — prueba de carga

**Escenario probado:** 1,600 equipos sintéticos con historial realista
(2,340 magnitudes, 8,304 calibraciones con 41,520 puntos, 8,286
verificaciones con 24,858 puntos, 2,856 mantenimientos), 15-20 usuarios
concurrentes, mezcla de navegación (dashboard, listado, detalle de equipo)
y escritura (aprobación de calibración con firma electrónica, generación
de PDF/Excel) — contra una base de datos de prueba dedicada, nunca contra
datos de producción de un cliente.

**Resultados de la corrida sostenida final** (25 minutos continuos, 15
usuarios, `UVICORN_WORKERS=4`):

| Criterio | Resultado medido | Umbral acordado | Cumple |
|---|---|---|---|
| Listado de equipos paginado | Promedio 214 ms, p95 = 940 ms | Promedio < 2 s y p95 < 3 s | Sí |
| Dashboard | Promedio 414 ms, p95 = 2.6 s | Promedio < 2 s y p95 < 3 s | Sí |
| Generación de PDF de análisis, sin bloquear otros usuarios | Promedio 1.21 s, no bloquea | < 5 s, sin bloqueo | Sí |
| Errores HTTP 500 durante la prueba | 0 en 1,956+ peticiones | 0% | Sí |
| Bloqueos de base de datos (deadlocks) en escritura concurrente | 0 coincidencias en el log del servidor | Sin bloqueos | Sí |
| Uso de memoria bajo carga sostenida (25 min) | Estable en banda 2.47-2.57 GB, sin tendencia de crecimiento | Sin fuga de memoria | Sí |
| Integridad del rastro de auditoría bajo carga | 57 de 57 operaciones de escritura con su fila de auditoría correspondiente, sin pérdidas | Coincidencia exacta | Sí |

**Conclusión formal:** PQ (Calificación de Desempeño) **aprobado con
desviaciones documentadas** — la única desviación es una cola de latencia
ocasional (percentil 99, hasta 15.7 s en el peor caso observado) que
afecta menos del 1-5% de las peticiones, no representa bloqueo de otros
usuarios ni pérdida de datos, y queda registrada como observación a
vigilar, no como falla. Detalle completo, metodología, y las dos rondas de
corrección de arquitectura que se hicieron antes de esta corrida final
(migración de la generación de PDF/Excel a un pool de procesos separado,
ver ADR-001) en `docs/calidad/PLAN_PRUEBAS_CARGA.md` y
`docs/calidad/validacion_farma/PQ_CALIFICACION_DESEMPENO.md`.

## 5. Respaldo y recuperación

Respaldo automático de PostgreSQL (`backup_db.py`, `pg_dump`) con
verificación de restauración probada (restaura contra una base de datos
temporal y compara conteos de filas) — no es un respaldo que se asume
funcional, se confirmó que efectivamente se puede restaurar. Retención de
archivos de respaldo configurable (`BACKUP_RETENCION_DIAS`). Recuperación
de acceso ante pérdida de contraseña de administrador vía script dedicado
que exige acceso directo al servidor (sin puerta trasera accesible desde
la pantalla de login).

## 6. Validación de sistemas computarizados (clientes GxP / farmacéuticos)

Para clientes de industria farmacéutica o regulada, MetroGest cuenta con
un paquete de validación (IQ/OQ/PQ) preparado sobre la base común de
integridad de datos ALCOA+, con anexos de diferencias específicas para
INVIMA+ISO/IEC 10012 (mercado inmediato), 21 CFR Part 11 (FDA) y EU Annex
11 — ver `docs/calidad/validacion_farma/`.

Estado real de cada pieza, sin sobreprometer:

- **Análisis de brechas regulatorias** (`GAP_ANALISIS_REGULATORIO.md`):
  completado contra el código real. La base técnica es sólida — control de
  acceso, autenticación, rastro de auditoría y firma electrónica ya
  existen y están probados. Quedan 2 brechas reales identificadas (no de
  documentación, de diseño): el vínculo entre una firma electrónica y el
  contenido exacto que firma es hoy por referencia (tabla + ID), no por
  hash criptográfico del contenido — relevante para la interpretación más
  estricta de 21 CFR 11.70; y falta confirmar que el soft-delete alcanza
  también a los registros "padre" (calibración, verificación,
  mantenimiento), no solo a sus puntos.
- **Calificación de Desempeño (PQ):** **ejecutada y cerrada** — ver §4
  arriba. Aprobada con desviaciones documentadas.
- **Calificación de Instalación (IQ) y Calificación Operacional (OQ):**
  protocolos completos y listos para ejecutar (`IQ_CALIFICACION_INSTALACION.md`,
  `OQ_CALIFICACION_OPERACIONAL.md`), con la cobertura automatizada de cada
  caso ya referenciada — pero **no ejecutados ni firmados todavía**. El IQ
  se ejecuta una vez por instalación de cliente (no es un artefacto que se
  firme una sola vez en general); el OQ se ejecuta como paso formal de
  cierre, apoyándose en la suite de 105 tests de la Fase 2.2, que ya cubre
  la mayoría de sus casos de riesgo alto.

Este anexo se actualiza a medida que se ejecuten y firmen el IQ y el OQ —
no se afirma aquí un estado de validación completo que todavía no existe.

## 7. Referencias para verificación independiente

- Arquitectura y decisiones de diseño: `docs/arquitectura/`
- Cobertura de pruebas e inventario de hallazgos: `docs/calidad/COBERTURA.md`,
  `docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md`
- Prueba de carga completa (metodología, 4 corridas, cifras crudas):
  `docs/calidad/PLAN_PRUEBAS_CARGA.md`
- Checklist de seguridad recurrente: `docs/calidad/CHECKLIST_SEGURIDAD.md`
- Paquete de validación GxP: `docs/calidad/validacion_farma/`
