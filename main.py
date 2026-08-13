from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import RedirectResponse as SR
from dotenv import load_dotenv
import os, sys, time, logging
from pathlib import Path

load_dotenv()

# ── Logging estructurado: consola + archivo (mismo patrón que script_alertas.py
# y backup_db.py). Antes main.py solo usaba print(), sin nivel ni archivo. ──────
_LOG_DIR = Path(__file__).parent / "logs"
_LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(_LOG_DIR / "app.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("metrogest")

from database import engine, Base, SessionLocal
import models, auth
import utils.auditoria_trail as auditoria_trail  # registra los listeners de auditoría al importarse
from utils.pdf_executor import pool as _pdf_executor  # ver ADR-001

Base.metadata.create_all(bind=engine)

def _import(name):
    try:
        m = __import__(f"routers.{name}", fromlist=[name])
        logger.info("Router cargado: %s", name); return m
    except Exception as e:
        logger.exception("Error cargando router %s: %s", name, e); return None

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
        # La revisión de alertas de calibración/licencia YA NO se dispara aquí
        # (ver ADR-001 en docs/arquitectura/DECISIONES.md): con varios workers
        # de Uvicorn (--workers), cada uno corre su propio lifespan al arrancar,
        # así que mandaba las mismas alertas por correo una vez por worker.
        # Además, disparar la revisión solo al reiniciar el servidor no
        # garantizaba una alerta diaria real. La tarea programada de Windows
        # (`configurar_tarea_windows.bat` → `script_alertas.py`, todos los
        # días a las 8:00 AM) es ahora la única vía — ver README.md.
    finally:
        db.close()
    yield
    _pdf_executor.shutdown(wait=False)

app = FastAPI(title="MetroGest v2", lifespan=lifespan)

# FORZAR_HTTPS=true cuando el servidor real corra detrás de TLS (ver validación
# de multi-worker/TLS ya hecha). En local sobre HTTP plano debe quedar en false,
# si no el navegador nunca enviaría la cookie de sesión y nadie podría loguearse.
_FORZAR_HTTPS = os.getenv("FORZAR_HTTPS", "false").lower() == "true"

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

class CabecerasSeguridadMiddleware(BaseHTTPMiddleware):
    """
    Cabeceras de seguridad estándar (OWASP). CSP permite 'unsafe-inline' en
    script-src/style-src porque casi todas las páginas tienen <script>/<style>
    inline (ver plantillas) — migrar eso a nonces por request o a archivos .js
    separados es un refactor propio, no algo para meter de paso aquí.
    """
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://cdnjs.cloudflare.com; "
            "font-src 'self' https://cdnjs.cloudflare.com; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "object-src 'none'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        if _FORZAR_HTTPS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return response

app.add_middleware(CabecerasSeguridadMiddleware)

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
    logger.critical("SESSION_SECRET no está configurado en .env. "
                     "Ejecuta: python -c \"import secrets; print(secrets.token_hex(32))\" "
                     "y copia el resultado en .env como SESSION_SECRET=<valor>")
    sys.exit(1)
app.add_middleware(SessionMiddleware, secret_key=_session_key, max_age=None,
                    https_only=_FORZAR_HTTPS, same_site="lax")

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

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log de acceso: método, ruta, status, duración y usuario — sin tener que
    instrumentar cada endpoint uno por uno. Se registra como la última
    middleware (queda más externa, ver nota de orden más arriba) para medir
    el tiempo total incluyendo el resto de la pila.
    """
    RUTAS_SIN_RUIDO = ("/static/",)  # css/img/favicon en cada carga de página

    async def dispatch(self, request, call_next):
        if request.url.path.startswith(self.RUTAS_SIN_RUIDO):
            return await call_next(request)
        inicio = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duracion_ms = (time.perf_counter() - inicio) * 1000
            logger.exception("%s %s -> excepción sin manejar (%.1fms)",
                              request.method, request.url.path, duracion_ms)
            raise
        duracion_ms = (time.perf_counter() - inicio) * 1000
        # request.session es una property que lanza AssertionError (no
        # AttributeError) si SessionMiddleware nunca llegó a tocar este
        # scope — hasattr() no protege contra eso, solo contra
        # AttributeError. Pasa exactamente cuando LicenciaMiddleware
        # corta la cadena ANTES de SessionMiddleware (redirect a
        # /sin-licencia o /licencia-vencida, ver docs/calidad/
        # PLAN_PRUEBAS_FUNCIONALES.md ítem 3): sin este chequeo correcto,
        # esas dos páginas — las que deberían avisarle al cliente que su
        # licencia venció, en vez de mostrarle una app "rota" — crasheaban
        # con un 500 sin manejar. Chequear la clave en scope (un dict
        # plano) sí es seguro.
        uid = request.session.get("user_id") if "session" in request.scope else None
        nivel = logging.WARNING if response.status_code >= 400 else logging.INFO
        logger.log(nivel, "%s %s -> %d (%.1fms) usuario=%s",
                    request.method, request.url.path, response.status_code, duracion_ms, uid or "-")
        return response

app.add_middleware(RequestLoggingMiddleware)

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/certificados", exist_ok=True)

# static/uploads y static/certificados tienen contenido subido por usuarios
# (fotos, manuales, certificados de calibración) — antes se servían por el
# mount público de abajo, sin ninguna verificación de sesión ni rol, así que
# cualquiera que conociera/adivinara la URL podía descargarlos. Estas dos
# rutas explícitas capturan esos prefijos ANTES del mount genérico (FastAPI
# resuelve rutas en el orden en que se registran) y exigen sesión iniciada.
# Los paths guardados en la BD (ej. "/static/uploads/foto_x.jpg") no cambian.
_UPLOADS_DIR = os.path.abspath("static/uploads")
_CERTIFICADOS_DIR = os.path.abspath("static/certificados")

def _servir_archivo_protegido(base_dir: str, nombre: str, request: Request):
    from starlette.responses import FileResponse
    db = SessionLocal()
    try:
        u = auth.obtener_usuario_actual(request, db)
    finally:
        db.close()
    if not u:
        return RedirectResponse(url="/usuarios/login")
    if "/" in nombre or "\\" in nombre or ".." in nombre:
        raise HTTPException(status_code=404)
    ruta = os.path.abspath(os.path.join(base_dir, nombre))
    if not ruta.startswith(base_dir + os.sep) or not os.path.isfile(ruta):
        raise HTTPException(status_code=404)
    return FileResponse(ruta)

@app.get("/static/uploads/{nombre}", include_in_schema=False)
async def servir_upload(nombre: str, request: Request):
    return _servir_archivo_protegido(_UPLOADS_DIR, nombre, request)

@app.get("/static/certificados/{nombre}", include_in_schema=False)
async def servir_certificado(nombre: str, request: Request):
    return _servir_archivo_protegido(_CERTIFICADOS_DIR, nombre, request)

app.mount("/static", StaticFiles(directory="static"), name="static")

logger.info("Cargando módulos...")
_mods = ["usuarios","equipos","magnitudes","calibraciones","analisis",
         "verificaciones","mantenimientos","config_lab","ilac",
         "dashboard","calendario","plan_mantenimiento","auditoria","notificaciones",
         "registro_auditoria","busqueda"]
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
    # El detalle completo (incluye el mensaje de la excepción, que puede traer
    # datos internos) solo va al log del servidor — nunca a la respuesta HTTP.
    # Antes se insertaba str(exc) directo en el HTML sin escapar: fuga de
    # información interna + XSS reflejado si el mensaje traía datos del usuario.
    logger.exception("Excepción sin manejar en %s %s", request.method, request.url.path)
    html = """<html><body style="font-family:monospace;padding:20px;background:#fff5f5;">
    <h2 style="color:#dc2626">Error del servidor</h2>
    <p>Ocurrió un error inesperado. Ya quedó registrado para revisión.</p>
    <p><a href="/">Volver al inicio</a></p>
    </body></html>"""
    return HTMLResponse(content=html, status_code=500)

@app.get("/")
def root(): return RedirectResponse(url="/dashboard/")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    from starlette.responses import Response
    return Response(status_code=204)  # 204 no debe llevar cuerpo (content={} rompía Content-Length)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
