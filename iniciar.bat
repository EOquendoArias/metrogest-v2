@echo off
cd /d "%~dp0"
title MetroGest v2
echo.
echo  ===================================================
echo   MetroGest v2 - Sistema de Gestion Metrologica
echo  ===================================================
echo.

if not exist "venv\Scripts\activate.bat" (
    echo  Creando entorno virtual por primera vez...
    python -m venv venv
    if errorlevel 1 (
        echo  ERROR: No se pudo crear el entorno virtual.
        pause
        exit /b
    )
)

call venv\Scripts\activate.bat

echo  Instalando dependencias...
pip install -r requirements.txt --quiet

echo  Aplicando migraciones de base de datos...
alembic upgrade head

echo.
echo  Cerrando instancias anteriores en el puerto 8000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr "127.0.0.1:8000" ^| findstr LISTENING') do taskkill /F /PID %%a >nul 2>&1

echo  Iniciando servidor...
rem  Abre el navegador tras 4 segundos, en segundo plano
start "" cmd /c "timeout /t 4 /nobreak >nul & start http://127.0.0.1:8000"

echo.
echo  Servidor en http://127.0.0.1:8000
echo  Primer arranque: la contrasena de admin se genera sola y sale en logs\app.log
echo  ¿La olvidaste? python resetear_password_admin.py admin@metrogest.com
echo  Cierra esta ventana para detener MetroGest
echo.

rem  uvicorn en PRIMER PLANO: al cerrar esta ventana el servidor se detiene.
rem  (Antes usaba "start /b", que dejaba el proceso vivo bloqueando el puerto 8000
rem   y hacia que al reabrir siguiera corriendo el codigo viejo.)
python -m uvicorn main:app --host 127.0.0.1 --port 8000
echo.
echo  === El servidor se detuvo. Revisa el error de arriba. ===
pause
