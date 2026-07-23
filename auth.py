import bcrypt, os, secrets
from datetime import datetime, timedelta, timezone
from fastapi import Request
from sqlalchemy.orm import Session
import models

MAX_INTENTOS_CUENTA = 5    # por (email, ip) — bloquear solo esa combinación
MAX_INTENTOS_IP     = 20   # por ip, sin importar qué cuenta se intente
BLOQUEO_MINUTOS     = 15


def _ahora_utc() -> datetime:
    """datetime.utcnow() está deprecado desde Python 3.12; esto es el
    equivalente naive-UTC (la columna en BD es DateTime sin tz)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

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

def esta_bloqueado(email: str, ip: str, db: Session) -> tuple[bool, int]:
    """
    Devuelve (bloqueado, minutos_restantes). Revisa dos límites independientes
    — el que esté bloqueado (o el que dure más) manda:
      - por (email, ip): evita que alguien bloquee la cuenta de otra persona
        solo sabiendo su correo, desde afuera — la víctima sigue pudiendo
        entrar desde su propia IP.
      - por ip (cualquier cuenta): evita que una sola IP pruebe muchas
        cuentas distintas (spray / credential stuffing).
    """
    ahora = _ahora_utc()
    minutos = 0

    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email, models.IntentoLogin.ip == ip).first()
    if registro and registro.bloqueado_hasta:
        if registro.bloqueado_hasta > ahora:
            minutos = max(minutos, int((registro.bloqueado_hasta - ahora).total_seconds() / 60) + 1)
        else:
            registro.intentos = 0
            registro.bloqueado_hasta = None
            db.commit()

    registro_ip = db.query(models.IntentoLoginIP).filter(models.IntentoLoginIP.ip == ip).first()
    if registro_ip and registro_ip.bloqueado_hasta:
        if registro_ip.bloqueado_hasta > ahora:
            minutos = max(minutos, int((registro_ip.bloqueado_hasta - ahora).total_seconds() / 60) + 1)
        else:
            registro_ip.intentos = 0
            registro_ip.bloqueado_hasta = None
            db.commit()

    return minutos > 0, minutos


def registrar_fallo(email: str, ip: str, db: Session) -> tuple[bool, int]:
    """Incrementa ambos contadores (cuenta+ip e ip global). Devuelve
    (bloqueado_ahora, minutos_bloqueo) según cuál de los dos disparó."""
    ahora = _ahora_utc()
    bloqueado_ahora = False

    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email, models.IntentoLogin.ip == ip).first()
    if not registro:
        registro = models.IntentoLogin(email=email, ip=ip)
        db.add(registro)
    registro.intentos = (registro.intentos or 0) + 1
    registro.ultimo_intento = ahora
    if registro.intentos >= MAX_INTENTOS_CUENTA:
        registro.bloqueado_hasta = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
        bloqueado_ahora = True

    registro_ip = db.query(models.IntentoLoginIP).filter(models.IntentoLoginIP.ip == ip).first()
    if not registro_ip:
        registro_ip = models.IntentoLoginIP(ip=ip)
        db.add(registro_ip)
    registro_ip.intentos = (registro_ip.intentos or 0) + 1
    registro_ip.ultimo_intento = ahora
    if registro_ip.intentos >= MAX_INTENTOS_IP:
        registro_ip.bloqueado_hasta = ahora + timedelta(minutes=BLOQUEO_MINUTOS)
        bloqueado_ahora = True

    db.commit()
    return bloqueado_ahora, BLOQUEO_MINUTOS


def resetear_intentos(email: str, ip: str, db: Session) -> None:
    """Limpia el contador de (email, ip) al autenticar con éxito. El contador
    global por IP no se toca — un acierto en una cuenta no debe borrar el
    historial de abuso de esa IP contra otras cuentas."""
    registro = db.query(models.IntentoLogin).filter(
        models.IntentoLogin.email == email, models.IntentoLogin.ip == ip).first()
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
