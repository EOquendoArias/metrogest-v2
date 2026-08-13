# Protocolo de Calificación de Instalación (IQ) — MetroGest v2

> Confirma que el sistema se instaló en el entorno especificado, con las
> versiones y configuración correctas, antes de calificar que *funciona*
> (eso es el OQ). Ejecutar una vez por instalación de cliente, y de nuevo
> tras cualquier cambio significativo de infraestructura.

**Instalación evaluada:** _____________________ **Fecha:** _____________
**Ejecutado por:** _____________________ **Revisado por:** _____________

| # | Ítem a verificar | Criterio de aceptación | Método | Resultado | ¿Cumple? |
|---|---|---|---|---|---|
| IQ-1 | Versión de Python | 3.10 o superior | `python --version` | | ☐ Sí ☐ No |
| IQ-2 | Servidor PostgreSQL accesible | Versión 14+, servicio activo, alcanzable con las credenciales de `DATABASE_URL` | `psql` o pgAdmin, conexión de prueba | | ☐ Sí ☐ No |
| IQ-3 | `POSTGRES_BIN_DIR` coincide con la versión real de Postgres instalada | La ruta en `.env` (usada por `backup_db.py` para ubicar `pg_dump.exe`/`pg_restore.exe`) apunta a la carpeta `bin` de la versión de Postgres realmente instalada en este equipo — **no asumir la 17 por defecto**, ver hallazgo real documentado en `docs/migracion/PLAN_IMPORTACION_EXCEL.md` §10/§11 (una instalación real resultó tener Postgres 18, y `backup_db.py` falló con `FileNotFoundError` hasta corregir la ruta) | `Get-ChildItem -Path "C:\Program Files","C:\Program Files (x86)" -Recurse -Filter "pg_dump.exe"` (PowerShell) para confirmar la ruta real, comparar contra `POSTGRES_BIN_DIR` en `.env` | | ☐ Sí ☐ No |
| IQ-4 | Dependencias Python instaladas | `pip install -r requirements.txt` completa sin error | Log de instalación (`iniciar.bat` o consola) | | ☐ Sí ☐ No |
| IQ-5 | Variables de entorno obligatorias presentes | `.env` contiene como mínimo `SESSION_SECRET` (≥32 caracteres), `DATABASE_URL` apuntando a Postgres | Inspección de `.env` contra `.env.example` | | ☐ Sí ☐ No |
| IQ-6 | Esquema de base de datos al día | `alembic current` coincide con la última revisión en `alembic/versions/` | Comando `alembic current` vs. `alembic history` | | ☐ Sí ☐ No |
| IQ-7 | Carpetas de datos creadas con permisos correctos | `static/uploads/`, `static/certificados/`, `logs/`, `backups/` existen y son escribibles por el proceso del servidor | Inspección de sistema de archivos | | ☐ Sí ☐ No |
| IQ-8 | El servicio arranca sin errores | `iniciar.bat` (o `python main.py`) levanta el servidor y `logs/app.log` no muestra excepciones en el arranque | Arranque + revisión de log | | ☐ Sí ☐ No |
| IQ-9 | Aplicación responde en el puerto esperado | `http://127.0.0.1:8000` (o el configurado) muestra la pantalla de login | Prueba de navegador | | ☐ Sí ☐ No |
| IQ-10 | Archivo de licencia válido presente | `licencia.json` existe, `licencia.py verificar` confirma firma válida y fecha de vigencia | CLI: `python licencia.py verificar` | | ☐ Sí ☐ No |
| IQ-11 | Usuario administrador inicial creado correctamente | Existe exactamente un usuario tras el primer arranque, con `debe_cambiar_password = true` y contraseña temporal registrada una sola vez en `logs/app.log` | Consulta a `usuarios` + inspección de log | | ☐ Sí ☐ No |
| IQ-12 | Backup automatizado configurado, y realmente probado (no solo programado) | Tarea programada de Windows existe (`configurar_tarea_windows.bat` o `configurar_backup_automatico.bat` ejecutado) **y** una corrida manual de `backup_db.py` completó con éxito (depende de que IQ-3 esté correcto — un `POSTGRES_BIN_DIR` mal configurado hace fallar el backup incluso con la tarea bien programada) | Programador de tareas de Windows + ejecución manual de `backup_db.py` + `backups/*.dump` presente | | ☐ Sí ☐ No |
| IQ-13 | HTTPS / cabeceras de seguridad según el entorno | Si el servidor está detrás de HTTPS real, `FORZAR_HTTPS=true` en `.env`; si es acceso local sin TLS, queda en `false` de forma consciente (no por omisión) | Inspección de `.env` + prueba de cabeceras de respuesta | | ☐ Sí ☐ No |

## Desviaciones encontradas

_(registrar aquí cualquier ítem marcado "No", con justificación y plan de
corrección — una IQ con desviaciones abiertas no debería darse por
aprobada)_

## Conclusión

☐ IQ **aprobada** sin desviaciones
☐ IQ aprobada **con desviaciones menores documentadas** (listar arriba)
☐ IQ **no aprobada** — requiere corrección antes de continuar al OQ

Firma ejecutor: _____________ Firma revisor: _____________ Fecha: _______
