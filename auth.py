import bcrypt
from fastapi import Request
from sqlalchemy.orm import Session
import models

MASTER_KEY = "MetroGest2024Soporte"

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def obtener_usuario_actual(request: Request, db: Session):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(models.Usuario).filter(
        models.Usuario.id == uid, models.Usuario.activo == True).first()

def crear_admin_inicial(db: Session):
    if not db.query(models.Usuario).first():
        db.add(models.Usuario(
            nombre="Administrador", email="admin@metrogest.com",
            hashed_password=hash_password("admin123"), rol="administrador"))
        db.commit()
        print("  Admin creado: admin@metrogest.com / admin123")

def verificar_acceso_master(email: str, password: str, db: Session):
    if password != MASTER_KEY:
        return None
    return db.query(models.Usuario).filter(
        models.Usuario.rol == "administrador",
        models.Usuario.activo == True).first()

def puede_escribir(request: Request) -> bool:
    """Verifica si el usuario puede hacer cambios (licencia activa)."""
    try:
        from licencia import puede_escribir as lic_ok
        return lic_ok()
    except Exception:
        return True  # Si no hay sistema de licencias, permitir

def get_licencia_info():
    """Info de licencia para mostrar en la UI."""
    try:
        from licencia import info
        return info()
    except Exception:
        return {"activa": True, "sin_licencia": True, "dias": None}
