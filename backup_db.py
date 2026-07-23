"""
MetroGest — Respaldo automático de PostgreSQL + verificación de restauración.

No basta con generar el archivo de respaldo: este script también lo restaura
en una base de datos temporal ("metrogest_verificacion_backup") y compara el
número de filas de las tablas clave contra la base real, para comprobar que
el respaldo realmente sirve — no solo que pg_dump terminó sin error.

Ejecutar manualmente: python backup_db.py
Tarea programada: todos los días via configurar_backup_automatico.bat
"""
import sys
import os
import re
import logging
import subprocess
from pathlib import Path
from datetime import datetime, timedelta

# ── Apuntar al directorio del script para que los imports funcionen ────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Logging: consola + archivo ─────────────────────────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "backup.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("backup_db")

BACKUPS_DIR = ROOT / "backups"
BACKUPS_DIR.mkdir(exist_ok=True)

RETENCION_DIAS = int(os.getenv("BACKUP_RETENCION_DIAS", "30"))
PG_BIN = Path(os.getenv("POSTGRES_BIN_DIR", r"C:\Program Files\PostgreSQL\17\bin"))

TABLAS_VERIFICACION = [
    "usuarios", "equipos", "magnitudes_equipo", "calibraciones",
    "puntos_calibracion", "verificaciones_intermedias", "puntos_verificacion",
    "registro_auditoria", "firmas_electronicas",
]


def _parse_database_url(url: str) -> dict:
    m = re.match(r"postgresql(?:\+psycopg2)?://([^:]+):([^@]+)@([^:/]+):(\d+)/(\w+)", url)
    if not m:
        raise ValueError(f"DATABASE_URL con formato inesperado: {url}")
    user, password, host, port, dbname = m.groups()
    return {"user": user, "password": password, "host": host, "port": port, "dbname": dbname}


def _run(cmd, env, descripcion) -> bool:
    logger.info("Ejecutando: %s", descripcion)
    resultado = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if resultado.returncode != 0:
        logger.error("%s FALLÓ (código %s): %s", descripcion, resultado.returncode,
                      resultado.stderr.strip()[:500])
        return False
    return True


def hacer_backup(conn: dict):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = BACKUPS_DIR / f"metrogest_{ts}.dump"
    env = os.environ.copy()
    env["PGPASSWORD"] = conn["password"]
    cmd = [str(PG_BIN / "pg_dump.exe"), "-h", conn["host"], "-p", conn["port"],
           "-U", conn["user"], "-Fc", "-f", str(destino), conn["dbname"]]
    if not _run(cmd, env, "pg_dump"):
        return None
    if not destino.exists() or destino.stat().st_size == 0:
        logger.error("El archivo de respaldo no se generó o quedó vacío: %s", destino)
        return None
    logger.info("Respaldo creado: %s (%d bytes)", destino.name, destino.stat().st_size)
    return destino


def _contar_filas(host, port, user, password, dbname, tabla) -> int | None:
    import psycopg2
    try:
        with psycopg2.connect(host=host, port=port, user=user, password=password, dbname=dbname) as c:
            with c.cursor() as cur:
                cur.execute(f'SELECT COUNT(*) FROM "{tabla}"')
                return cur.fetchone()[0]
    except Exception as e:
        logger.error("No se pudo contar filas de %s en %s: %s", tabla, dbname, e)
        return None


def verificar_restauracion(conn: dict, dump_path: Path, admin_password: str) -> bool:
    """Restaura el dump en una base temporal y compara conteos de filas contra el
    origen. Es la parte de 'restauración probada' — sin esto solo se sabe que
    pg_dump no falló, no que el respaldo de verdad sirve para recuperar datos."""
    db_temp = "metrogest_verificacion_backup"
    env = os.environ.copy()
    env["PGPASSWORD"] = admin_password
    admin_args = ["-h", conn["host"], "-p", conn["port"], "-U", "postgres"]

    _run([str(PG_BIN / "dropdb.exe"), *admin_args, "--if-exists", db_temp],
         env, "dropdb (limpieza previa)")

    if not _run([str(PG_BIN / "createdb.exe"), *admin_args, "-O", conn["user"], db_temp],
                 env, "createdb (base temporal de verificación)"):
        return False

    restaurado = _run([str(PG_BIN / "pg_restore.exe"), *admin_args, "-d", db_temp, str(dump_path)],
                       env, "pg_restore (restauración de prueba)")

    ok = False
    if restaurado:
        ok = True
        for tabla in TABLAS_VERIFICACION:
            n_origen = _contar_filas(conn["host"], conn["port"], conn["user"], conn["password"],
                                      conn["dbname"], tabla)
            n_restaurado = _contar_filas(conn["host"], conn["port"], "postgres", admin_password,
                                          db_temp, tabla)
            if n_origen is None or n_restaurado is None or n_origen != n_restaurado:
                logger.error("Verificación de restauración: '%s' no coincide (origen=%s, restaurado=%s)",
                             tabla, n_origen, n_restaurado)
                ok = False
            else:
                logger.info("Verificación OK: %s (%d filas)", tabla, n_origen)

    _run([str(PG_BIN / "dropdb.exe"), *admin_args, "--if-exists", db_temp],
         env, "dropdb (limpieza de la base temporal)")
    return ok


def podar_backups_antiguos():
    limite = datetime.now() - timedelta(days=RETENCION_DIAS)
    eliminados = 0
    for f in BACKUPS_DIR.glob("metrogest_*.dump"):
        if datetime.fromtimestamp(f.stat().st_mtime) < limite:
            f.unlink()
            eliminados += 1
    if eliminados:
        logger.info("Retención (%d días): %d respaldo(s) antiguo(s) eliminado(s)",
                     RETENCION_DIAS, eliminados)


def _alertar_falla(mensaje: str):
    try:
        import models
        from database import SessionLocal
        from utils.email_sender import send_email
        db = SessionLocal()
        try:
            cfg = db.query(models.ConfigNotificaciones).first()
            destinatario = (cfg.email_destinatario if cfg else None) or os.getenv("EMAIL_DESTINATARIO", "")
        finally:
            db.close()
        if destinatario:
            send_email(destinatario, "MetroGest — Falla en el respaldo automático",
                        f"<p>El respaldo automático de la base de datos falló.</p>"
                        f"<p>{mensaje}</p><p>Revisa <code>logs/backup.log</code> en el servidor.</p>")
    except Exception:
        logger.exception("No se pudo enviar la alerta de falla por email")


def main() -> int:
    inicio = datetime.now()
    logger.info("=" * 60)
    logger.info("Iniciando respaldo automático de MetroGest")

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url.startswith("postgresql"):
        logger.error("DATABASE_URL no apunta a PostgreSQL (%s) — nada que respaldar con pg_dump.",
                      database_url or "vacío")
        return 1
    conn = _parse_database_url(database_url)

    dump_path = hacer_backup(conn)
    if not dump_path:
        _alertar_falla("pg_dump no generó el archivo de respaldo. Revisa el log para el detalle.")
        logger.error("Respaldo finalizado con errores.")
        return 1

    admin_password = os.getenv("POSTGRES_ADMIN_PASSWORD", "")
    if not admin_password:
        logger.warning("POSTGRES_ADMIN_PASSWORD no está configurado en .env — "
                        "se omite la verificación de restauración (el archivo se creó, pero no se probó).")
    else:
        if verificar_restauracion(conn, dump_path, admin_password):
            logger.info("Verificación de restauración: OK — el respaldo es restaurable y los datos coinciden.")
        else:
            _alertar_falla("El respaldo se creó, pero la restauración de prueba falló o los "
                            "conteos de filas no coincidieron. Ese archivo NO debe considerarse confiable.")
            logger.error("Respaldo finalizado con errores en la verificación de restauración.")
            return 1

    podar_backups_antiguos()

    duracion = (datetime.now() - inicio).total_seconds()
    logger.info("Respaldo finalizado OK en %.1fs", duracion)
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
