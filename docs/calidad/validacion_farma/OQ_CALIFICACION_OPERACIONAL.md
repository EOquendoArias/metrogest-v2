# Protocolo de Calificación Operacional (OQ) — MetroGest v2

> Confirma que cada función opera conforme a su especificación, incluyendo
> casos límite y de error — no solo el "camino feliz". Los casos de
> **riesgo alto** (ver `PLAN_MAESTRO_VALIDACION.md` §3) llevan pruebas de
> desafío ("challenge tests") explícitas, no solo el flujo normal.

**Instalación evaluada:** _____________________ **Fecha:** _____________
**Ejecutado por:** _____________________ **Revisado por:** _____________

## Bloque A — Riesgo alto (obligatorio, sin excepciones)

| # | Caso de prueba | Resultado esperado | Cobertura automatizada existente | Resultado obtenido | ¿Aprobado? |
|---|---|---|---|---|---|
| OQ-A1 | Punto de calibración dentro de tolerancia, con incertidumbre | Semáforo = verde (`dentro_tolerancia = true`) | `tests/test_calculos.py::TestCalcularSemaforo` | | ☐ Sí ☐ No |
| OQ-A2 | Punto de calibración justo en el límite de tolerancia (\|error\|+U = EMP exacto) | Semáforo = verde (límite inclusivo) — confirmar el comportamiento especificado, no asumido | Revisar caso borde en `test_calculos.py` | | ☐ Sí ☐ No |
| OQ-A3 | Punto de calibración fuera de tolerancia | Semáforo = rojo, calibración no puede aprobarse sin acción explícita | `test_calculos.py` | | ☐ Sí ☐ No |
| OQ-A4 | Aprobar calibración exige firma electrónica con reautenticación | Rechaza si la contraseña ingresada en el momento de firmar es incorrecta, aunque la sesión esté activa | `tests/test_firma_electronica.py` | | ☐ Sí ☐ No |
| OQ-A5 | Usuario con rol `solo_lectura` intenta crear/editar un registro | Rechazado (redirección o 403), sin excepción | `tests/test_rbac.py` | | ☐ Sí ☐ No |
| OQ-A6 | Licencia vencida | Bloquea POST/PUT/DELETE, permite GET (solo lectura) | Revisar `LicenciaMiddleware` en `main.py` — no hay test automatizado confirmado, **verificar manualmente** | | ☐ Sí ☐ No |
| OQ-A7 | 5 intentos fallidos de login con la misma cuenta+IP | Cuenta bloqueada 15 minutos para esa combinación; la misma cuenta sigue accesible desde otra IP | `tests/test_auth.py` | | ☐ Sí ☐ No |
| OQ-A8 | 20 intentos fallidos desde la misma IP contra cuentas distintas | IP bloqueada globalmente 15 minutos | `tests/test_auth.py` | | ☐ Sí ☐ No |
| OQ-A9 | Modificar un campo de un registro auditado | Queda una fila en `registro_auditoria` con usuario, campo, valor anterior y nuevo | `tests/test_auditoria_trail.py` | | ☐ Sí ☐ No |
| OQ-A10 | Eliminar un punto de calibración/verificación | No se borra físicamente — queda marcado `eliminado=true` con usuario y fecha, y desaparece de las vistas normales pero no de la BD | Revisar `models.py` (`PuntoCalibracion.eliminado`) — **confirmar en la UI/router, no solo en el modelo** | | ☐ Sí ☐ No |

## Bloque B — Riesgo medio

| # | Caso de prueba | Resultado esperado | Cobertura automatizada existente | Resultado obtenido | ¿Aprobado? |
|---|---|---|---|---|---|
| OQ-B1 | Cálculo de intervalo ILAC G24 con los 14 factores en su valor por defecto (3) | Intervalo sugerido = 12 meses (promedio 3.0, según la tabla de `GUIA_PROYECTO.md` §6.3 — **confirmar que sigue siendo así en el código actual**, ese documento está desactualizado) | Ninguna identificada — **gap de prueba automatizada** | | ☐ Sí ☐ No |
| OQ-B2 | Verificación intermedia con desviación entre umbral de alerta y umbral fuera de tolerancia | Resultado = "alerta" (amarillo), no "aprobado" ni "reprobado" | `tests/test_deriva.py` cubre deriva, **verificar si cubre esta ruta específica** | | ☐ Sí ☐ No |
| OQ-B3 | Generar PDF de análisis de calibración | PDF se genera sin error, con los datos del laboratorio configurados y el resultado correcto por punto | Sin test automatizado — **prueba manual** | | ☐ Sí ☐ No |
| OQ-B4 | Exportar dashboard a Excel | Archivo `.xlsx` válido, abre sin error, cifras coinciden con el dashboard en pantalla | Sin test automatizado — **prueba manual** | | ☐ Sí ☐ No |
| OQ-B5 | Alerta de vencimiento de calibración (30/15/7/1 días antes) | Se genera la alerta correspondiente una sola vez por umbral (no se repite) | `HistorialAlertas` en `models.py` sugiere control de duplicados — **verificar en `utils/alertas_calibracion.py`** | | ☐ Sí ☐ No |

## Bloque C — Riesgo bajo (muestreo, no exhaustivo)

| # | Caso de prueba | Resultado esperado | Resultado obtenido | ¿Aprobado? |
|---|---|---|---|---|
| OQ-C1 | Guardar configuración del laboratorio (logo, razón social) | Se guarda y se refleja en el próximo PDF generado | | ☐ Sí ☐ No |
| OQ-C2 | Vista de calendario muestra actividades próximas | Coincide con las fechas reales de vencimiento en BD | | ☐ Sí ☐ No |
| OQ-C3 | Búsqueda global encuentra un equipo por código | Resultado correcto, sin falsos negativos en una prueba simple | | ☐ Sí ☐ No |

## Desviaciones y gaps de prueba automatizada identificados en este OQ

_(consolidar aquí los ítems marcados "sin test automatizado" arriba — son
candidatos directos para añadir a `tests/` antes de la siguiente
revalidación, no solo para pasar esta vez de forma manual)_

## Conclusión

☐ OQ **aprobado** ☐ Aprobado con desviaciones documentadas ☐ No aprobado

Firma ejecutor: _____________ Firma revisor: _____________ Fecha: _______
