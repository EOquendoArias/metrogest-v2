@echo off
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
pip install fastapi "uvicorn[standard]" sqlalchemy jinja2 python-multipart aiofiles starlette "passlib[bcrypt]" python-dateutil numpy matplotlib reportlab itsdangerous --quiet

echo  Dependencias listas.
echo.
start "" http://127.0.0.1:8000
echo  Servidor en http://127.0.0.1:8000
echo  Usuario: admin@metrogest.com  /  Contrasena: admin123
echo  Ctrl+C para detener
echo.
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
pause
