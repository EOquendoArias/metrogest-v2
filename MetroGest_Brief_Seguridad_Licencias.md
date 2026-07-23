# MetroGest v2 — Brief de Seguridad y Sistema de Licencias
**Para:** Claude Code  
**Preparado por:** Cowork (análisis de código base)  
**Fecha:** Junio 17, 2026  
**Archivos principales:** `main.py`, `auth.py`, `licencia.py`

---

## DIAGNÓSTICO: 6 brechas críticas encontradas

### BRECHA 1 — CRÍTICA: licencia.py existe pero NO está conectada al sistema
`main.py` **nunca importa ni llama a `licencia.py`**. El app arranca y funciona completamente sin ningún archivo de licencia. Toda la lógica en `licencia.py` (`esta_activa()`, `puede_escribir()`, etc.) está implementada pero **desconectada**.

### BRECHA 2 — CRÍTICA: Fallback peligroso en auth.py
```python
# auth.py línea 44 — PROBLEMA
def puede_escribir(request: Request) -> bool:
    try:
        from licencia import puede_escribir as lic_ok
        return lic_ok()
    except Exception:
        return True  # ← Si falla el import, PERMITE escritura. Al revés de lo que debe ser.
```
Si `licencia.py` tiene un error o se elimina, el sistema otorga acceso total.

### BRECHA 3 — CRÍTICA: SECRET_KEY de sesión hardcodeado en main.py
```python
# main.py línea 45
app.add_middleware(SessionMiddleware, secret_key="metrogest-2024-secret")
```
Cualquiera que vea el código puede forjar cookies de sesión.

### BRECHA 4 — ALTA: _SECRETO de licencias visible en texto plano
```python
# licencia.py línea 16
_SECRETO = "MetroGest#Proveedor#2024#LicenciaSecreta#NoCompartir"
```
Quien tenga acceso al código fuente puede generar licencias válidas para cualquier cliente.

### BRECHA 5 — ALTA: MASTER_KEY de soporte visible en texto plano
```python
# auth.py línea 6
MASTER_KEY = "MetroGest2024Soporte"
```
Permite acceso admin sin contraseña si alguien conoce esta clave.

### BRECHA 6 — MEDIA: Contraseña admin inicial no fuerza cambio
```python
# auth.py línea 25-29
# Crea admin con contraseña "admin123" — nunca se obliga a cambiarla
```

---

## PLAN DE IMPLEMENTACIÓN — Orden de prioridad

---

### FASE 1 — Conectar y activar el sistema de licencias (CRÍTICO)

#### Tarea 1.1: Crear middleware de licencia en main.py

Agregar un middleware Starlette que se ejecute en **cada request HTTP** antes de llegar a cualquier router. El middleware debe:

- Permitir siempre: `/login`, `/static/`, `/favicon.ico`
- Si la licencia no existe (`sin_licencia() == True`): redirigir a `/sin-licencia`
- Si la licencia está vencida (`esta_vencida() == True`): permitir GET pero bloquear POST/PUT/DELETE/PATCH → redirigir a `/licencia-vencida`
- Si la licencia está activa: dejar pasar

```python
# Agregar en main.py DESPUÉS de crear app y ANTES de montar routers

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as SR
import licencia as lic

RUTAS_LIBRES = {"/login", "/static", "/favicon.ico", "/sin-licencia", "/licencia-vencida"}

class LicenciaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        # Dejar pasar rutas de login y recursos estáticos
        if any(path.startswith(r) for r in RUTAS_LIBRES):
            return await call_next(request)
        # Sin licencia → bloquear todo
        if lic.sin_licencia():
            if request.headers.get("accept", "").startswith("application/json"):
                from fastapi.responses import JSONResponse
                return JSONResponse({"error": "Sin licencia"}, status_code=403)
            return SR(url="/sin-licencia")
        # Licencia vencida → solo lectura (bloquear escrituras)
        if lic.esta_vencida():
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                if request.headers.get("accept", "").startswith("application/json"):
                    from fastapi.responses import JSONResponse
                    return JSONResponse({"error": "Licencia vencida — modo solo lectura"}, status_code=403)
                return SR(url="/licencia-vencida")
        return await call_next(request)

app.add_middleware(LicenciaMiddleware)
```

#### Tarea 1.2: Crear rutas y páginas para los estados de licencia

Agregar en `main.py` (después del middleware) estas dos rutas:

```python
from fastapi.responses import HTMLResponse

@app.get("/sin-licencia", include_in_schema=False)
async def sin_licencia_page():
    html = """
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>MetroGest — Sin Licencia</title>
        <style>
            body { font-family: 'Segoe UI', sans-serif; background: #f8fafc; 
                   display: flex; align-items: center; justify-content: center; 
                   min-height: 100vh; margin: 0; }
            .card { background: white; padding: 48px; border-radius: 16px; 
                    box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 480px; 
                    text-align: center; }
            .icon { font-size: 64px; margin-bottom: 16px; }
            h1 { color: #1e293b; margin: 0 0 8px; font-size: 24px; }
            p { color: #64748b; line-height: 1.6; }
            .code { background: #f1f5f9; padding: 12px 16px; border-radius: 8px; 
                    font-family: monospace; font-size: 13px; text-align: left; 
                    margin: 16px 0; }
            a { color: #2563eb; }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">🔒</div>
            <h1>Licencia no encontrada</h1>
            <p>MetroGest requiere un archivo de licencia válido para funcionar.</p>
            <div class="code">
                Copia el archivo <strong>licencia.json</strong> recibido al comprar<br>
                en la carpeta de instalación del programa.<br><br>
                Ruta: <strong>metrogest_v2/licencia.json</strong>
            </div>
            <p>¿No tienes licencia? Contáctanos:<br>
               <a href="mailto:contacto@metrogest.com.co">contacto@metrogest.com.co</a><br>
               <a href="https://wa.me/573167527686">WhatsApp +57 316 752 7686</a>
            </p>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/licencia-vencida", include_in_schema=False)
async def licencia_vencida_page():
    from licencia import info
    i = info()
    html = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <title>MetroGest — Licencia Vencida</title>
        <style>
            body {{ font-family: 'Segoe UI', sans-serif; background: #fffbeb; 
                   display: flex; align-items: center; justify-content: center; 
                   min-height: 100vh; margin: 0; }}
            .card {{ background: white; padding: 48px; border-radius: 16px; 
                    box-shadow: 0 4px 24px rgba(0,0,0,0.1); max-width: 480px; 
                    text-align: center; }}
            .icon {{ font-size: 64px; margin-bottom: 16px; }}
            h1 {{ color: #92400e; margin: 0 0 8px; font-size: 24px; }}
            p {{ color: #64748b; line-height: 1.6; }}
            .btn {{ display: inline-block; background: #2563eb; color: white; 
                    padding: 12px 24px; border-radius: 8px; text-decoration: none; 
                    margin-top: 16px; }}
            .btn-sec {{ background: #f1f5f9; color: #1e293b; margin-left: 8px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="icon">⚠️</div>
            <h1>Licencia vencida</h1>
            <p>La licencia de <strong>{i.get('cliente', 'este equipo')}</strong> 
               venció el <strong>{i.get('vence', 'fecha desconocida')}</strong>.<br><br>
               Puedes consultar tus datos en modo solo lectura, pero no podrás 
               agregar ni editar información hasta renovar.</p>
            <a href="https://wa.me/573167527686?text=Quiero%20renovar%20mi%20licencia%20MetroGest" 
               class="btn">Renovar licencia</a>
            <a href="/" class="btn btn-sec">Ver mis datos</a>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html)
```

**NOTA:** La ruta `/licencia-vencida` tiene el botón "Ver mis datos" que lleva a `/` — esto funciona porque el middleware SÍ permite GETs cuando hay licencia vencida.

---

### FASE 2 — Corregir los fallbacks peligrosos en auth.py

#### Tarea 2.1: Invertir el fallback de puede_escribir()

```python
# auth.py — CAMBIAR línea 39-45:

# ANTES (peligroso):
def puede_escribir(request: Request) -> bool:
    try:
        from licencia import puede_escribir as lic_ok
        return lic_ok()
    except Exception:
        return True  # ← PELIGROSO

# DESPUÉS (seguro):
def puede_escribir(request: Request) -> bool:
    try:
        from licencia import puede_escribir as lic_ok
        return lic_ok()
    except Exception:
        return False  # ← Si algo falla, negar acceso (fail secure)
```

#### Tarea 2.2: Corregir fallback de get_licencia_info()

```python
# auth.py — CAMBIAR línea 47-53:

# ANTES (engañoso):
def get_licencia_info():
    try:
        from licencia import info
        return info()
    except Exception:
        return {"activa": True, "sin_licencia": True, "dias": None}  # ← confuso

# DESPUÉS (honesto):
def get_licencia_info():
    try:
        from licencia import info
        return info()
    except Exception:
        return {"activa": False, "sin_licencia": True, "vencida": False,
                "cliente": None, "modulos": [], "vence": None, "dias": None}
```

---

### FASE 3 — Migrar SECRET_KEY a archivo .env

#### Tarea 3.1: Crear archivo .env en la raíz del proyecto

Crear `C:\Users\USUARIO\metrogest_v2\.env` con este contenido (Edison debe cambiar el valor):

```
SESSION_SECRET=cambiar_por_clave_aleatoria_larga_aqui_2024
```

Para generar una clave segura (ejecutar en terminal):
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

#### Tarea 3.2: Instalar python-dotenv

Agregar a `requirements.txt`:
```
python-dotenv
```

#### Tarea 3.3: Actualizar main.py para leer .env

```python
# main.py — agregar al inicio (después de los imports):
from dotenv import load_dotenv
load_dotenv()

# Y cambiar línea 45:
# ANTES:
app.add_middleware(SessionMiddleware, secret_key="metrogest-2024-secret")

# DESPUÉS:
import os
_session_key = os.getenv("SESSION_SECRET", "")
if not _session_key or len(_session_key) < 32:
    import sys
    print("\n⛔ ERROR: SESSION_SECRET no está configurado en .env")
    print("   Ejecuta: python -c \"import secrets; print(secrets.token_hex(32))\"")
    print("   Copia el resultado en .env como SESSION_SECRET=<valor>")
    sys.exit(1)
app.add_middleware(SessionMiddleware, secret_key=_session_key)
```

#### Tarea 3.4: Verificar que .env está en .gitignore

Revisar `C:\Users\USUARIO\metrogest_v2\.gitignore`. Si no existe o no incluye `.env`, agregar:
```
.env
licencia.json
__pycache__/
*.pyc
venv/
*.db
```

**IMPORTANTE:** `licencia.json` también debe estar en `.gitignore` — no debe subirse al repositorio.

---

### FASE 4 — Hardening adicional (hacer después de Fase 1-3)

#### Tarea 4.1: Ofuscar _SECRETO en licencia.py

El secreto para firmar licencias no debe estar en texto plano en el código fuente. Aplicar una ofuscación básica con `base64` + inversión de bytes para que no sea inmediatamente legible:

```python
# licencia.py — reemplazar línea 16:
# ANTES:
_SECRETO = "MetroGest#Proveedor#2024#LicenciaSecreta#NoCompartir"

# DESPUÉS:
import base64 as _b64
# Secreto codificado — NO modificar
_S = b"TWV0cm9HZXN0I1Byb3ZlZWRvciMyMDI0I0xpY2VuY2lhU2VjcmV0YSNOb0NvbXBhcnRpcg=="
_SECRETO = _b64.b64decode(_S).decode()
```

Esto no es criptografía fuerte, pero elimina la lectura directa del secreto. Para mayor seguridad futura se puede compilar a `.pyc` y distribuir solo el bytecode.

#### Tarea 4.2: Mover MASTER_KEY a .env

```python
# auth.py — CAMBIAR línea 6:
# ANTES:
MASTER_KEY = "MetroGest2024Soporte"

# DESPUÉS:
import os
MASTER_KEY = os.getenv("MASTER_KEY", "")
```

Agregar al `.env`:
```
MASTER_KEY=cambiar_a_clave_de_soporte_segura
```

Si `MASTER_KEY` está vacía, `verificar_acceso_master()` nunca podrá coincidir (línea 33: `if password != MASTER_KEY` → con vacío nunca coincide). Esto es intencional y seguro.

#### Tarea 4.3: Banner de licencia en el dashboard

En el template del dashboard (`templates/dashboard.html` o el layout base), agregar un banner visible cuando la licencia está por vencer (menos de 30 días). El banner debe mostrarse en todas las páginas mientras la licencia esté próxima a vencer.

En el router de dashboard (o en el middleware via `request.state`), pasar el estado de licencia al contexto de los templates:

```python
# En cualquier router que use Jinja2Templates, agregar al contexto:
from licencia import info as lic_info
# ... dentro del endpoint:
lic = lic_info()
# Pasar a template: "licencia": lic
```

En el template base (`base.html` o layout principal), agregar encima del nav:
```html
{% if licencia and licencia.activa and licencia.dias is not none and licencia.dias < 30 %}
<div style="background:#fef3c7;border-bottom:2px solid #f59e0b;padding:8px 16px;
            text-align:center;font-size:13px;color:#92400e;">
    ⚠️ Tu licencia vence en <strong>{{ licencia.dias }} días</strong> 
    ({{ licencia.vence }}).
    <a href="https://wa.me/573167527686?text=Quiero%20renovar%20mi%20licencia%20MetroGest" 
       style="color:#b45309;font-weight:600;margin-left:8px;">Renovar ahora →</a>
</div>
{% endif %}
{% if licencia and licencia.vencida %}
<div style="background:#fee2e2;border-bottom:2px solid #ef4444;padding:8px 16px;
            text-align:center;font-size:13px;color:#991b1b;">
    🔒 Licencia vencida — Modo solo lectura activo. 
    <a href="https://wa.me/573167527686?text=Quiero%20renovar%20mi%20licencia%20MetroGest"
       style="color:#7f1d1d;font-weight:600;margin-left:8px;">Contactar para renovar →</a>
</div>
{% endif %}
```

#### Tarea 4.4: Forzar cambio de contraseña en primer login

En el modelo `Usuario` (models.py), agregar columna:
```python
debe_cambiar_password: bool = Column(Boolean, default=False)
```

En `auth.py:crear_admin_inicial()`, crear el admin con `debe_cambiar_password=True`.

En el router de login (router `usuarios`), después de autenticar exitosamente, verificar:
```python
if usuario.debe_cambiar_password:
    return RedirectResponse(url="/usuarios/cambiar-password?forzado=1", status_code=303)
```

---

## RESUMEN DE ARCHIVOS A MODIFICAR

| Archivo | Cambios |
|---------|---------|
| `main.py` | Agregar LicenciaMiddleware, rutas `/sin-licencia` y `/licencia-vencida`, leer SESSION_SECRET de .env |
| `auth.py` | Invertir fallback `puede_escribir()`, corregir `get_licencia_info()`, mover MASTER_KEY a .env |
| `licencia.py` | Ofuscar `_SECRETO` con base64 |
| `requirements.txt` | Agregar `python-dotenv` |
| `.env` (NUEVO) | Crear con SESSION_SECRET y MASTER_KEY |
| `.gitignore` | Verificar que incluye `.env` y `licencia.json` |
| `models.py` | Agregar campo `debe_cambiar_password` a Usuario |
| `templates/base.html` (o layout) | Agregar banner de licencia próxima a vencer/vencida |

---

## ORDEN DE IMPLEMENTACIÓN RECOMENDADO

1. **Primero:** Fase 3 (`.env` + `python-dotenv`) — sin esto el app deja de iniciar con los cambios de Fase 1
2. **Segundo:** Fase 1 (middleware de licencia + páginas de error)
3. **Tercero:** Fase 2 (corregir fallbacks en auth.py)
4. **Cuarto:** Fase 4 (hardening — ofuscar secreto, banner, forzar cambio de password)

## CÓMO GENERAR UNA LICENCIA DE PRUEBA (para testing)

Desde la carpeta del proyecto, con el venv activo:
```bash
python licencia.py generar "Demo Laboratorio" 2027-12-31
```
Esto genera `licencia_Demo_Laboratorio.json`. Renombrar a `licencia.json` y copiar a la carpeta del proyecto para que el middleware la encuentre.

---

## NOTAS PARA EDISON

- **Antes de cada entrega a un cliente**, generar su `licencia.json` con la fecha correcta y enviársela aparte del instalador.
- **La licencia es el único control de acceso** al software — guardar el archivo `_SECRETO` en un lugar seguro aparte del código fuente en el futuro.
- **El `.env`** nunca va a GitHub — es tu archivo local de configuración del servidor.
