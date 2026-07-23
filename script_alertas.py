"""
MetroGest — Script de alertas diarias
Ejecutar: python script_alertas.py
Tarea programada: todos los días a las 8:00 AM via configurar_tarea_windows.bat
"""
import sys
import os
import logging
from pathlib import Path
from datetime import datetime

# ── Apuntar al directorio del script para que los imports funcionen ────────────
ROOT = Path(__file__).parent.resolve()
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# ── Cargar variables de entorno antes de cualquier import del proyecto ─────────
from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── Configurar logging: consola + archivo rotativo ────────────────────────────
LOG_DIR = ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "alertas.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)

logger = logging.getLogger("script_alertas")


def _rotar_log(max_bytes: int = 1_000_000) -> None:
    """Mantiene el log por debajo de max_bytes eliminando las líneas más antiguas."""
    if not LOG_FILE.exists():
        return
    if LOG_FILE.stat().st_size < max_bytes:
        return
    lineas = LOG_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    mitad  = len(lineas) // 2
    LOG_FILE.write_text("".join(lineas[mitad:]), encoding="utf-8")
    logger.info("Log rotado: se eliminaron %d líneas antiguas", mitad)


def main() -> int:
    inicio = datetime.now()
    logger.info("=" * 60)
    logger.info("Iniciando script de alertas MetroGest")
    logger.info("Directorio: %s", ROOT)

    errores = 0

    from database import SessionLocal
    from utils.alertas_calibracion import (verificar_licencia_por_vencer,
                                           verificar_calibraciones_por_vencer)

    db = SessionLocal()
    try:
        # ── 1. Alerta de licencia ──────────────────────────────────────────────
        logger.info("-- Verificando licencia ------------------------------------------")
        try:
            verificar_licencia_por_vencer(db)
        except Exception as exc:
            logger.exception("Error en verificar_licencia_por_vencer: %s", exc)
            errores += 1

        # ── 2. Alerta de calibraciones ─────────────────────────────────────────
        logger.info("-- Verificando calibraciones -------------------------------------")
        try:
            verificar_calibraciones_por_vencer(db)
        except Exception as exc:
            logger.exception("Error en verificar_calibraciones_por_vencer: %s", exc)
            errores += 1
    finally:
        db.close()

    # ── Resumen ────────────────────────────────────────────────────────────────
    duracion = (datetime.now() - inicio).total_seconds()
    if errores:
        logger.error("Script finalizado con %d error(es) en %.1fs", errores, duracion)
    else:
        logger.info("Script finalizado OK en %.1fs", duracion)
    logger.info("=" * 60)

    _rotar_log()
    return errores


if __name__ == "__main__":
    sys.exit(main())
