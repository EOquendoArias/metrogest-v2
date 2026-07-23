@echo off
cd /d "%~dp0"
title MetroGest — Configurar respaldo automatico

echo.
echo  ============================================================
echo   MetroGest v2 — Instalador de respaldo automatico
echo  ============================================================
echo.

:: Verificar que el venv existe
if not exist "venv\Scripts\python.exe" (
    echo  ERROR: No se encontro el entorno virtual en venv\
    echo  Ejecuta primero iniciar.bat para crearlo.
    pause
    exit /b 1
)

:: Rutas absolutas
set "CARPETA=%~dp0"
set "PYTHON=%~dp0venv\Scripts\python.exe"
set "SCRIPT=%~dp0backup_db.py"
set "NOMBRE_TAREA=MetroGest_Respaldo_Diario"

echo  Carpeta : %CARPETA%
echo  Python  : %PYTHON%
echo  Script  : %SCRIPT%
echo  Tarea   : %NOMBRE_TAREA%
echo  Horario : Todos los dias a las 02:00 AM
echo.

:: Eliminar tarea anterior si existe (para reinstalacion limpia)
schtasks /delete /tn "%NOMBRE_TAREA%" /f >nul 2>&1

:: Crear la tarea programada
schtasks /create ^
  /tn "%NOMBRE_TAREA%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /sc DAILY ^
  /st 02:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo  [OK] Tarea programada instalada correctamente.
    echo.
    echo  La tarea "%NOMBRE_TAREA%" se ejecutara todos los dias
    echo  a las 02:00 AM. Cada corrida:
    echo    - Genera un respaldo (pg_dump) en backups\
    echo    - Lo restaura en una base temporal para PROBAR que sirve
    echo    - Compara filas contra la base real
    echo    - Borra respaldos con mas de BACKUP_RETENCION_DIAS (.env, hoy 30)
    echo    - Envia un correo de alerta si algo falla
    echo.
    echo  Los resultados quedan en: logs\backup.log
    echo.
    echo  Para ejecutar el respaldo ahora mismo (sin esperar las 2am):
    echo    schtasks /run /tn "%NOMBRE_TAREA%"
    echo.
    echo  Para eliminar la tarea:
    echo    schtasks /delete /tn "%NOMBRE_TAREA%" /f
    echo.
) else (
    echo.
    echo  ERROR: No se pudo crear la tarea.
    echo  Intenta ejecutar este archivo como Administrador:
    echo    clic derecho ^> "Ejecutar como administrador"
    echo.
)

pause
