import bcrypt, os, secrets
from datetime import datetime, timedelta
from fastapi import Request
from sqlalchemy.orm import Session
import models

MAX_INTENTOS    = 5
BLOQUEO_MINUTOS = 15

def hash_password(p: str) -> str:
    return bcrypt.hashpw(p.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verificar_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode('utf-8'), hashed.encode('utf-8'))
    except Exception:
        return False

def generar_password_temporal() -> str:
    return secrets.token_urlsafe(12)

def obtener_usuario_actual(request: Request, db: Session):
    uid = request.session.get("user_id")
    if not uid:
        return None
    return db.query(models.Usuario).filter(
        models.Usuario.id == uid, models.Usuario.activo == True).first()

def crear_admin_inicial(db: Session):
    if not db.query(models.Usuario).first():
        temp = generar_password_temporal()
        db.add(models.Usuario(
            nombre="Administrador", email="admin@metrogest.com",
            hashed_password=hash_password(temp), rol="administrador",
            debe_cambiar_password=True))
        db.commit()
        print(f"\n  ⚠ Admin creado: admin@metrogest.com / {temp}")
        print("  Contraseña temporal — se pedirá cambiarla en el primer login.\n")

def esta_bloqueado(email: str, db: Session) -> tuple[bool, int]:
    """Devuelve (bloqueado, minutos_restantes)."""
    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email).first()
    if not registro or not registro.bloqueado_hasta:
        return False, 0
    ahora = datetime.utcnow()
    if registro.bloqueado_hasta > ahora:
        minutos = int((registro.bloqueado_hasta - ahora).total_seconds() / 60) + 1
        return True, minutos
    # Bloqueo expirado — limpiar
    registro.intentos = 0
    registro.bloqueado_hasta = None
    db.commit()
    return False, 0


def registrar_fallo(email: str, db: Session) -> tuple[bool, int]:
    """Incrementa el contador. Devuelve (bloqueado_ahora, minutos_bloqueo)."""
    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email).first()
    if not registro:
        registro = models.IntentoLogin(email=email)
        db.add(registro)
    registro.intentos = (registro.intentos or 0) + 1
    registro.ultimo_intento = datetime.utcnow()
    if registro.intentos >= MAX_INTENTOS:
        registro.bloqueado_hasta = datetime.utcnow() + timedelta(minutes=BLOQUEO_MINUTOS)
        db.commit()
        return True, BLOQUEO_MINUTOS
    db.commit()
    return False, 0


def resetear_intentos(email: str, db: Session) -> None:
    """Limpia el contador al autenticar con éxito."""
    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email).first()
    if registro:
        registro.intentos = 0
        registro.bloqueado_hasta = None
        db.commit()


def puede_escribir(request: Request) -> bool:
    """Verifica si el usuario puede hacer cambios (licencia activa)."""
    try:
        from licencia import puede_escribir as lic_ok
        return lic_ok()
    except Exception:
        return False  # fail secure: si algo falla, negar acceso

def get_licencia_info():
    """Info de licencia para mostrar en la UI."""
    try:
        from licencia import info
        return info()
    except Exception:
        return {"activa": False, "sin_licencia": True, "vencida": False,
                "cliente": None, "modulos": [], "vence": None, "dias": None}
