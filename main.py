from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as SR
from dotenv import load_dotenv
import os, sys, traceback

load_dotenv()

from database import engine, Base, SessionLocal
import models, auth
import utils.auditoria_trail as auditoria_trail  # registra los listeners de auditoría al importarse

Base.metadata.create_all(bind=engine)

def _import(name):
    try:
        m = __import__(f"routers.{name}", fromlist=[name])
        print(f"  OK {name}"); return m
    except Exception as e:
        print(f"  ERROR {name}: {e}"); traceback.print_exc(); return None

@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        auth.crear_admin_inicial(db)
        if not db.query(models.ConfigLaboratorio).first():
            db.add(models.ConfigLaboratorio()); db.commit()
        if not db.query(models.ConfigNotificaciones).first():
            cfg = models.ConfigNotificaciones()
            cfg.email_destinatario = os.getenv("EMAIL_DESTINATARIO", "")
            db.add(cfg); db.commit()
        from utils.alertas_calibracion import (verificar_calibraciones_por_vencer,
                                               verificar_licencia_por_vencer)
        verificar_licencia_por_vencer(db)
        verificar_calibraciones_por_vencer(db)
    finally:
        db.close()
    yield

app = FastAPI(title="MetroGest v2", lifespan=lifespan)

class AuditoriaContextMiddleware(BaseHTTPMiddleware):
    """Deja el id del usuario autenticado disponible para utils/auditoria_trail.py,
    que lo lee desde los listeners de SQLAlchemy al capturar cada cambio."""
    async def dispatch(self, request, call_next):
        token = auditoria_trail.usuario_actual_id.set(request.session.get("user_id"))
        try:
            return await call_next(request)
        finally:
            auditoria_trail.usuario_actual_id.reset(token)

app.add_middleware(AuditoriaContextMiddleware)

RUTAS_LIBRES_PASSWORD = {"/usuarios/login", "/usuarios/logout",
                          "/usuarios/cambiar-password-inicial", "/static", "/favicon.ico"}

class ForzarCambioPasswordMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if any(path.startswith(r) for r in RUTAS_LIBRES_PASSWORD):
            return await call_next(request)
        uid = request.session.get("user_id")
        if uid:
            db = SessionLocal()
            try:
                u = db.query(models.Usuario).filter(models.Usuario.id == uid).first()
                if u and u.debe_cambiar_password:
                    return SR(url="/usuarios/cambiar-password-inicial")
            finally:
                db.close()
        return await call_next(request)

# Nota de orden: ForzarCambioPasswordMiddleware y AuditoriaContextMiddleware se
# agregan ANTES que SessionMiddleware para que, en la pila de Starlette (el
# último agregado queda más externo), Session se ejecute primero y
# request.session ya exista cuando ellas corran.
app.add_middleware(ForzarCambioPasswordMiddleware)

_session_key = os.getenv("SESSION_SECRET", "")
if not _session_key or len(_session_key) < 32:
    print("\n⛔ ERROR: SESSION_SECRET no está configurado en .env")
    print("   Ejecuta: python -c \"import secrets; print(secrets.token_hex(32))\"")
    print("   Copia el resultado en .env como SESSION_SECRET=<valor>")
    sys.exit(1)
app.add_middleware(SessionMiddleware, secret_key=_session_key, max_age=None)

import licencia as lic

RUTAS_LIBRES = {"/usuarios/login", "/static", "/favicon.ico", "/sin-licencia", "/licencia-vencida"}

class LicenciaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        path = request.url.path
        if any(path.startswith(r) for r in RUTAS_LIBRES):
            return await call_next(request)
        if lic.sin_licencia():
            if request.headers.get("accept", "").startswith("application/json"):
                return JSONResponse({"error": "Sin licencia"}, status_code=403)
            return SR(url="/sin-licencia")
        if lic.esta_vencida():
            if request.method in ("POST", "PUT", "DELETE", "PATCH"):
                if request.headers.get("accept", "").startswith("application/json"):
                    return JSONResponse({"error": "Licencia vencida — modo solo lectura"}, status_code=403)
                return SR(url="/licencia-vencida")
        return await call_next(request)

app.add_middleware(LicenciaMiddleware)

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/certificados", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

print("Cargando módulos...")
_mods = ["usuarios","equipos","magnitudes","calibraciones","analisis",
         "verificaciones","mantenimientos","config_lab","ilac",
         "dashboard","calendario","plan_mantenimiento","auditoria","notificaciones",
         "registro_auditoria"]
_routers = [(n, _import(n)) for n in _mods]

for name, mod in _routers:
    if mod:
        prefix = "/config-lab" if name=="config_lab" else "/dashboard" if name=="dashboard" else "/calendario" if name=="calendario" else "/plan-mantenimiento" if name=="plan_mantenimiento" else "/registro-auditoria" if name=="registro_auditoria" else f"/{name}"
        app.include_router(mod.router, prefix=prefix, tags=[name])

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
            <div class="icon">&#128274;</div>
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
    i = lic.info()
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
            <div class="icon">&#9888;&#65039;</div>
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


@app.exception_handler(Exception)
async def err(request: Request, exc: Exception):
    tb = traceback.format_exc()
    print(f"\n=== ERROR ===\n{tb}")
    from fastapi.responses import HTMLResponse
    msg = str(exc)[:500]
    html = f"""<html><body style="font-family:monospace;padding:20px;background:#fff5f5;">
    <h2 style="color:#dc2626">Error del servidor</h2>
    <pre style="background:#f8fafc;padding:16px;border-radius:8px;overflow:auto">{msg}</pre>
    <p><a href="/">Volver al inicio</a></p>
    </body></html>"""
    return HTMLResponse(content=html, status_code=500)

@app.get("/")
def root(): return RedirectResponse(url="/dashboard/")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon(): return JSONResponse(status_code=204, content={})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
