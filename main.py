from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from starlette.middleware.sessions import SessionMiddleware
import os, traceback
from database import engine, Base, SessionLocal
import models, auth

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
    finally:
        db.close()
    yield

app = FastAPI(title="MetroGest v2", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key="metrogest-2024-secret")

os.makedirs("static/uploads", exist_ok=True)
os.makedirs("static/certificados", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

print("Cargando módulos...")
_mods = ["usuarios","equipos","magnitudes","calibraciones","analisis",
         "verificaciones","mantenimientos","config_lab","ilac",
         "dashboard","calendario","plan_mantenimiento","auditoria"]
_routers = [(n, _import(n)) for n in _mods]

for name, mod in _routers:
    if mod:
        prefix = "/config-lab" if name=="config_lab" else "/dashboard" if name=="dashboard" else "/calendario" if name=="calendario" else "/plan-mantenimiento" if name=="plan_mantenimiento" else f"/{name}"
        app.include_router(mod.router, prefix=prefix, tags=[name])

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
def root(): return RedirectResponse(url="/equipos/")

@app.get("/favicon.ico", include_in_schema=False)
async def favicon(): return JSONResponse(status_code=204, content={})

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
