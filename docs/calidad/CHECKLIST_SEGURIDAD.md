# Checklist de seguridad recurrente — Fase 2.4

> Entregable de la Fase 2.4 de [`../PROJECT_PLAN.md`](../PROJECT_PLAN.md) §2.4.
> Convierte las 6 brechas ya cerradas (`CLAUDE.md` §5) más el endurecimiento
> agregado después en una checklist de auditoría **repetible** — pensada para
> marcarse antes de cada entrega a un cliente nuevo, o después de cualquier
> cambio que toque autenticación, licencias, o manejo de archivos/errores.
> No es una lectura de una sola vez: es un formulario que se vuelve a llenar.

## Cómo usar este documento

Para cada ítem: correr la verificación indicada (automatizada o manual),
marcar `[x]` si pasa, anotar la fecha y quién lo corrió. Un ítem marcado
"Automatizado" ya corre solo con `pytest tests/ -v` — si ese archivo de test
falla, este ítem falla. Un ítem marcado "Manual" no tiene forma de
verificarse con pytest (por diseño: son cosas como "¿el secreto está en
`.env` y no en el código?", que un test no puede confirmar sobre el
repositorio del cliente) y hay que revisarlo a mano cada vez.

**Última corrida completa:** 12-ago-2026, por Edison Oquendo (con asistencia
de Claude/Cowork) — `pytest tests/ -v` → 105/105 ✅.

---

## Bloque A — Las 6 brechas originales (`MetroGest_Brief_Seguridad_Licencias.md`, 17-jun-2026)

- [ ] **A1. Middleware de licencia conectado** (`LicenciaMiddleware` en `main.py`).
      **Automatizado** — `tests/test_ciclo_vida_licencia.py` (12 tests:
      sin licencia, vencida, activa, gate de módulo premium).
- [ ] **A2. Fallbacks "fail secure" en `auth.puede_escribir()` / `auth.get_licencia_info()`.**
      Si `licencia.py` lanza una excepción, deben negar acceso (`False`) y
      reportar "sin licencia", nunca fallar abierto.
      **Manual** — revisar que ambas funciones sigan envueltas en
      `try/except Exception: return False` / el dict de "sin licencia" (ver
      `auth.py` líneas 125-140). No hay test automatizado porque forzar la
      excepción real (ej. corromper `licencia.json` a mitad de lectura)
      no vale la inversión frente a una revisión de código de 30 segundos.
- [ ] **A3. `SESSION_SECRET` viene de `.env`, la app falla al arrancar si no está.**
      **Manual** — confirmar en `main.py` (~línea 141-146) que sigue el
      `sys.exit(1)` si `SESSION_SECRET` falta o mide menos de 32
      caracteres, y confirmar que `.env` está en `.gitignore` (nunca en
      el repo). No es automatizable con pytest porque el chequeo ocurre
      al importar `main.py`, antes de que exista una app para testear.
- [ ] **A4. Secreto de licencias ofuscado en `licencia.py`.**
      **Manual** — confirmar que `_SECRETO` sigue en base64 (no en texto
      plano) y que no se ha vuelto a hardcodear en ningún otro archivo:
      `grep -r "_SECRETO\|TWV0cm9HZXN0" --include=*.py .`
- [ ] **A5. `MASTER_KEY` eliminado por completo.**
      **Manual** (verificación rápida, no amerita test):
      `grep -rn "MASTER_KEY" --include=*.py .` no debe devolver nada fuera
      de comentarios que documenten su eliminación (confirmado 12-ago-2026:
      solo aparece en el comentario de `resetear_password_admin.py` que
      explica que lo reemplaza). Si aparece código funcional, es una
      regresión grave — revertir de inmediato.
- [ ] **A6. Contraseña de admin inicial aleatoria + cambio forzado en primer login.**
      **Parcialmente automatizado** — `auth.generar_password_temporal()`
      (usa `secrets.token_urlsafe`, no un valor fijo) y
      `debe_cambiar_password=True` al crear el admin (`auth.py::crear_admin_inicial`)
      no tienen test dedicado (ese código corre en el `lifespan`, que los
      tests reemplazan a propósito por uno vacío — ver `conftest.py`). Sí
      está cubierto que el sistema *exige* cambiarla:
      `tests/test_00_infra.py`/flujo de login general. **Manual**: revisar
      una vez por entrega que `crear_admin_inicial` no se haya modificado
      para volver a un valor fijo tipo `admin123`.

## Bloque B — Endurecimiento agregado después del brief (`CLAUDE.md` §5, "Encima de eso")

- [ ] **B1. Rate-limiting de login** por (email+ip) y por ip global.
      **Automatizado** — `tests/test_auth.py` (6 tests: bloqueo por
      cuenta, no-contagio entre IPs, límite exacto, reseteo tras éxito,
      bloqueo global por IP).
- [ ] **B2. RBAC por rol** en los 36 endpoints de escritura reales.
      **Automatizado** — `tests/test_rbac.py` + `tests/test_rbac_ampliado.py`
      (23 tests: `solo_lectura` bloqueado en 19 endpoints, `operador`
      bloqueado en 5 endpoints exclusivos de administrador, y 2 casos de
      control positivo). Ver `docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md`
      ítem 2 para el detalle completo.
- [ ] **B3. Cabeceras de seguridad HTTP** (`CabecerasSeguridadMiddleware`
      en `main.py`: `X-Frame-Options`, `X-Content-Type-Options`,
      `Referrer-Policy`, `Content-Security-Policy`, `Strict-Transport-Security`
      condicionada a `FORZAR_HTTPS`).
      **Sin automatizar — gap identificado en esta revisión.** Ningún test
      actual verifica que estas cabeceras lleguen en la respuesta HTTP.
      Es barato de agregar (un test que haga `client.get(...)` y revise
      `r.headers`) — candidato directo para la próxima sesión que toque
      este documento.
- [ ] **B4. Validación de archivos subidos** (`utils/validar_archivo.py`:
      extensiones permitidas por tipo — imágenes `.jpg/.jpeg/.png/.webp`,
      documentos `.pdf` —, tope de tamaño 5 MB imágenes / 15 MB
      documentos).
      **Sin automatizar — gap identificado en esta revisión.** Los tests
      de la Fase 2.2 que tocan endpoints con `UploadFile` (equipos,
      config-lab) siempre se probaron *sin* adjuntar archivo — nunca se
      probó qué pasa si se sube una extensión no permitida o un archivo
      demasiado grande.
- [ ] **B5. Servir archivos protegidos con sesión** (`_servir_archivo_protegido`
      en `main.py`, para `static/uploads/` y `static/certificados/` —
      antes cualquiera con la URL podía descargarlos sin sesión).
      **Sin automatizar — gap identificado en esta revisión.**
- [ ] **B6. Página 500 genérica** sin fuga de información interna
      (`@app.exception_handler(Exception)` en `main.py`, log completo al
      servidor, `str(exc)` nunca va a la respuesta HTTP).
      **Sin automatizar, y con una advertencia real**: ese
      `exception_handler` solo atrapa excepciones que suben desde el
      router hacia adentro — **no** protege contra excepciones lanzadas
      dentro de un middleware personalizado añadido con `app.add_middleware`
      (como el que causó el bug corregido en
      `docs/calidad/PLAN_PRUEBAS_FUNCIONALES.md` ítem 3: un `AssertionError`
      en `RequestLoggingMiddleware` se propagaba sin pasar por esta página
      bonita). Cualquier middleware nuevo que se agregue debe manejar sus
      propias excepciones explícitamente, no asumir que esta red de
      seguridad lo cubre.
- [ ] **B7. Rastro de auditoría automático** (`utils/auditoria_trail.py`,
      registra cambios en `registro_auditoria` sin que cada router lo
      llame explícitamente).
      **Automatizado** — `tests/test_auditoria_trail.py` (5 tests) +
      verificación cruzada con datos reales de carga en
      `docs/calidad/PLAN_PRUEBAS_CARGA.md` §7 (PQ-7).
- [ ] **B8. Soft-delete** en puntos de calibración y verificación
      (`eliminado`/`eliminado_en`/`eliminado_por_id`, nunca `DELETE` físico).
      **Parcialmente automatizado** — cubierto para verificaciones
      (`tests/test_rbac_ampliado.py::test_solo_lectura_no_puede_eliminar_punto_de_verificacion`,
      `tests/test_flujo_verificacion_intermedia.py`). **Gap identificado**:
      no hay un test que confirme el soft-delete de puntos de
      *calibración* (`routers/analisis.py::eliminar_punto`) de forma
      directa — solo que `solo_lectura` no puede invocarlo.
- [ ] **B9. Firma electrónica** (Ley 527/1999 Colombia) con
      reautenticación por contraseña, en 4+ puntos críticos del flujo
      metrológico.
      **Automatizado** — `tests/test_firma_electronica.py` (3 tests) +
      cobertura end-to-end en `tests/test_flujo_aprobacion_calibracion.py`
      y `tests/test_flujo_verificacion_intermedia.py`.
- [ ] **B10. Backups automáticos de PostgreSQL con restauración probada**
      (`backup_db.py`).
      **Manual, no automatizable con pytest** (es un script operativo que
      toca la BD real, no algo para correr en la suite de tests). Revisar
      según el runbook de `README.md`: que el backup programado siga
      corriendo, y repetir la prueba de restauración periódicamente (no
      solo una vez al implementarlo).

## Desviaciones abiertas (no bloquean, pero quedan registradas)

1. **B3, B4, B5 sin test automatizado** — identificadas en esta revisión,
   no en el brief original. Ninguna es una brecha nueva (el código ya
   existe y funciona, confirmado por revisión manual), pero no tienen red
   de seguridad si alguien las rompe sin querer en un cambio futuro.
2. **B8 incompleto** — falta el equivalente de calibraciones al test que
   ya existe para verificaciones.
3. **B6, advertencia de diseño** — la página 500 genérica no cubre
   excepciones de middlewares personalizados; ya causó un bug real (ver
   Bloque B6 arriba). Cualquier middleware nuevo necesita su propio manejo
   de errores.

Estas 3 desviaciones son los candidatos naturales para la primera vez que
se vuelva a este documento — no ameritaban parar la Fase 2.4 para
resolverlas ahora mismo, pero tampoco hay que perderlas de vista.

## Qué hacer si algo falla

- Si un ítem **Automatizado** falla (el test correspondiente falla en
  `pytest tests/ -v`): es una regresión de seguridad real. No se entrega
  al cliente hasta corregirlo — no es negociable, sin excepción para
  fechas de entrega.
- Si un ítem **Manual** falla en la revisión (ej. aparece `MASTER_KEY`
  funcional, o `SESSION_SECRET` hardcodeado): mismo criterio — bloquea la
  entrega, se corrige antes de continuar.
- Cualquier hallazgo nuevo (brecha no listada aquí) se documenta en este
  mismo archivo como un nuevo ítem del Bloque B, no se resuelve "en
  silencio" sin dejar rastro — mismo principio que se siguió con cada
  hallazgo de la Fase 2.2/2.3.
