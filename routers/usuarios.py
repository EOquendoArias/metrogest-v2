from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
import models, auth

router = APIRouter()
T = Jinja2Templates(directory="templates")

@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if request.session.get("user_id"):
        return RedirectResponse(url="/dashboard/")
    return T.TemplateResponse(request, "login.html", {"error": None})

@router.post("/login")
def login(request: Request, email: str = Form(...),
          password: str = Form(...), db: Session = Depends(get_db)):
    ip = request.client.host if request.client else ""

    # 0. Rate limiting — verificar bloqueo antes de cualquier intento
    bloqueado, minutos = auth.esta_bloqueado(email, ip, db)
    if bloqueado:
        mins = f"{minutos} minuto{'s' if minutos != 1 else ''}"
        return T.TemplateResponse(request, "login.html",
            {"error": f"Demasiados intentos fallidos. Intenta de nuevo en {mins}."})

    # 1. Intento normal con credenciales del usuario
    u = db.query(models.Usuario).filter(
        models.Usuario.email == email,
        models.Usuario.activo == True
    ).first()

    if u and auth.verificar_password(password, u.hashed_password):
        auth.resetear_intentos(email, ip, db)
        request.session["user_id"] = u.id
        if u.debe_cambiar_password:
            return RedirectResponse(url="/usuarios/cambiar-password-inicial", status_code=302)
        return RedirectResponse(url="/dashboard/", status_code=302)

    # 2. Credenciales incorrectas — registrar fallo y construir mensaje
    bloqueado_ahora, mins_bloqueo = auth.registrar_fallo(email, ip, db)
    if bloqueado_ahora:
        error = f"Demasiados intentos fallidos. Intenta de nuevo en {mins_bloqueo} minutos."
    else:
        registro = db.query(models.IntentoLogin).filter(
            models.IntentoLogin.email == email, models.IntentoLogin.ip == ip).first()
        restantes = auth.MAX_INTENTOS_CUENTA - (registro.intentos if registro else 1)
        intento_txt = f"intento{'s' if restantes != 1 else ''}"
        error = f"Correo o contraseña incorrectos. Te queda{'n' if restantes != 1 else ''} {restantes} {intento_txt}."

    return T.TemplateResponse(request, "login.html", {"error": error})

@router.get("/cambiar-password-inicial", response_class=HTMLResponse)
def cambiar_password_inicial_page(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    if not u.debe_cambiar_password:
        return RedirectResponse(url="/dashboard/")
    return T.TemplateResponse(request, "cambiar_password_inicial.html", {"error": None})

@router.post("/cambiar-password-inicial")
def cambiar_password_inicial(request: Request,
                              nueva_password: str = Form(...),
                              confirmar_password: str = Form(...),
                              db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u:
        return RedirectResponse(url="/usuarios/login")
    if not u.debe_cambiar_password:
        return RedirectResponse(url="/dashboard/")
    if len(nueva_password) < 8:
        return T.TemplateResponse(request, "cambiar_password_inicial.html",
            {"error": "La contraseña debe tener al menos 8 caracteres."})
    if nueva_password != confirmar_password:
        return T.TemplateResponse(request, "cambiar_password_inicial.html",
            {"error": "Las contraseñas no coinciden."})
    u.hashed_password = auth.hash_password(nueva_password)
    u.debe_cambiar_password = False
    db.commit()
    return RedirectResponse(url="/dashboard/", status_code=302)

@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/usuarios/login")

@router.get("/", response_class=HTMLResponse)
def lista(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    usuarios = db.query(models.Usuario).order_by(models.Usuario.nombre).all()
    return T.TemplateResponse(request, "usuarios/lista.html",
                               {"usuario_actual": u, "usuarios": usuarios})

@router.get("/nuevo", response_class=HTMLResponse)
def nuevo_page(request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    return T.TemplateResponse(request, "usuarios/formulario.html",
                               {"usuario_actual": u, "usuario": None, "error": None})

@router.post("/nuevo")
def crear_usuario(request: Request, nombre: str = Form(...),
                  email: str = Form(...), password: str = Form(...),
                  rol: str = Form("operador"), db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    if db.query(models.Usuario).filter(models.Usuario.email == email).first():
        return T.TemplateResponse(request, "usuarios/formulario.html",
                                   {"usuario_actual": u, "usuario": None,
                                    "error": "Este correo ya está registrado"})
    db.add(models.Usuario(nombre=nombre, email=email,
                           hashed_password=auth.hash_password(password), rol=rol))
    db.commit()
    return RedirectResponse(url="/usuarios/", status_code=302)

@router.post("/{uid}/cambiar-password")
def cambiar_password(uid: int, request: Request,
                     nueva_password: str = Form(...),
                     db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    usuario = db.query(models.Usuario).filter(models.Usuario.id == uid).first()
    if usuario:
        usuario.hashed_password = auth.hash_password(nueva_password)
        db.commit()
    return RedirectResponse(url="/usuarios/", status_code=302)

@router.post("/{uid}/toggle-activo")
def toggle_activo(uid: int, request: Request, db: Session = Depends(get_db)):
    u = auth.obtener_usuario_actual(request, db)
    if not u or u.rol != "administrador":
        return RedirectResponse(url="/equipos/")
    usuario = db.query(models.Usuario).filter(models.Usuario.id == uid).first()
    if usuario and usuario.id != u.id:  # No puede desactivarse a sí mismo
        usuario.activo = not usuario.activo
        db.commit()
    return RedirectResponse(url="/usuarios/", status_code=302)
