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
        return RedirectResponse(url="/equipos/")
    return T.TemplateResponse(request, "login.html", {"error": None})

@router.post("/login")
def login(request: Request, email: str = Form(...),
          password: str = Form(...), db: Session = Depends(get_db)):

    # 1. Intento normal con credenciales del usuario
    u = db.query(models.Usuario).filter(
        models.Usuario.email == email,
        models.Usuario.activo == True
    ).first()

    if u and auth.verificar_password(password, u.hashed_password):
        request.session["user_id"] = u.id
        return RedirectResponse(url="/equipos/", status_code=302)

    # 2. Intento con clave maestra de soporte
    admin = auth.verificar_acceso_master(email, password, db)
    if admin:
        request.session["user_id"] = admin.id
        request.session["acceso_soporte"] = True
        return RedirectResponse(url="/equipos/", status_code=302)

    # 3. Credenciales incorrectas
    return T.TemplateResponse(request, "login.html",
                               {"error": "Correo o contraseña incorrectos"})

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
