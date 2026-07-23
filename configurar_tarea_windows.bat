@echo off
cd /d "%~dp0"
title MetroGest — Configurar tarea programada

echo.
echo  ============================================================
echo   MetroGest v2 — Instalador de tarea programada de alertas
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
set "SCRIPT=%~dp0script_alertas.py"
set "NOMBRE_TAREA=MetroGest_Alertas_Diarias"

echo  Carpeta : %CARPETA%
echo  Python  : %PYTHON%
echo  Script  : %SCRIPT%
echo  Tarea   : %NOMBRE_TAREA%
echo  Horario : Todos los dias a las 08:00 AM
echo.

:: Eliminar tarea anterior si existe (para reinstalación limpia)
schtasks /delete /tn "%NOMBRE_TAREA%" /f >nul 2>&1

:: Crear la tarea programada
schtasks /create ^
  /tn "%NOMBRE_TAREA%" ^
  /tr "\"%PYTHON%\" \"%SCRIPT%\"" ^
  /sc DAILY ^
  /st 08:00 ^
  /ru "%USERNAME%" ^
  /rl HIGHEST ^
  /f

if %errorlevel% equ 0 (
    echo.
    echo  [OK] Tarea programada instalada correctamente.
    echo.
    echo  La tarea "%NOMBRE_TAREA%" se ejecutara todos los dias
    echo  a las 08:00 AM y enviara alertas por correo si hay:
    echo    - Calibraciones que vencen en los proximos 30 dias
    echo    - Licencia de MetroGest proxima a vencer
    echo.
    echo  Los resultados quedan en: logs\alertas.log
    echo.
    echo  Para ejecutar la tarea ahora mismo (sin esperar las 8am):
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
