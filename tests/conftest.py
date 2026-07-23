"""
Fixtures compartidas. Corre contra una base de datos Postgres de PRUEBA
separada (nunca la real) — se deriva de DATABASE_URL agregando "_test" al
nombre, o se puede fijar explícitamente con TEST_DATABASE_URL en el entorno
(así es como lo hace el workflow de CI). No se hardcodea ninguna credencial
aquí.

Aislamiento entre tests: cada test corre dentro de una transacción que se
revierte al final (ver fixture `db`), así que ningún test deja datos para
el siguiente.
"""
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")


def _test_database_url() -> str:
    explicita = os.getenv("TEST_DATABASE_URL")
    if explicita:
        return explicita
    base = os.getenv("DATABASE_URL", "")
    if not base:
        raise RuntimeError(
            "Configura TEST_DATABASE_URL o DATABASE_URL en .env para correr los tests."
        )
    partes = urlsplit(base)
    dbname_test = partes.path.lstrip("/") + "_test"
    return urlunsplit((partes.scheme, partes.netloc, f"/{dbname_test}", partes.query, partes.fragment))


@pytest.fixture(scope="session")
def engine():
    import models  # registra las tablas en Base.metadata
    from database import Base

    eng = create_engine(_test_database_url())
    Base.metadata.drop_all(bind=eng)
    Base.metadata.create_all(bind=eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine):
    """
    Sesión ligada a una transacción externa que se revierte al final del
    test, incluso si el código bajo prueba llama db.commit() (la mayoría de
    las funciones de la app lo hacen). Patrón documentado de SQLAlchemy para
    test suites: cada "commit" de la app en realidad cierra un SAVEPOINT, y
    el listener de abajo abre uno nuevo de inmediato — el rollback final de
    la transacción externa deshace todo de una vez.
    """
    from sqlalchemy import event
    from sqlalchemy.orm import Session as SQLASession

    conexion = engine.connect()
    transaccion = conexion.begin()
    sesion = SQLASession(bind=conexion)

    sesion.begin_nested()

    @event.listens_for(sesion, "after_transaction_end")
    def _reabrir_savepoint(sesion_, transaccion_):
        if transaccion_.nested and not transaccion_._parent.nested:
            sesion_.begin_nested()

    try:
        yield sesion
    finally:
        sesion.close()
        transaccion.rollback()
        conexion.close()


@pytest.fixture()
def client(db, monkeypatch):
    """
    TestClient que reutiliza la MISMA sesión `db` (transacción + savepoint)
    para el dependency override de get_db() — así lo que un test prepara
    directamente con la fixture `db` es visible para sus propias requests
    HTTP, y absolutamente todo se revierte al final igual que en `db`.

    El lifespan real (crear admin inicial, revisar licencia/alertas) se
    reemplaza por uno vacío: no queremos que cada test dispare esos efectos
    secundarios (creación de usuario, posible envío de correo) contra la
    base de datos de prueba.
    """
    from contextlib import asynccontextmanager

    from fastapi.testclient import TestClient

    import database as database_module
    import main as main_module

    @asynccontextmanager
    async def _lifespan_vacio(app):
        yield

    monkeypatch.setattr(main_module.app.router, "lifespan_context", _lifespan_vacio)

    # ForzarCambioPasswordMiddleware y _servir_archivo_protegido abren su
    # propia SessionLocal() directo (no vía Depends(get_db)) — sin este
    # parche apuntarían a la base real en vez de a la de prueba.
    monkeypatch.setattr(main_module, "SessionLocal", sessionmaker(bind=db.get_bind()))

    def _get_db_test():
        yield db

    main_module.app.dependency_overrides[database_module.get_db] = _get_db_test

    with TestClient(main_module.app) as c:
        yield c

    main_module.app.dependency_overrides.clear()
