"""
Traslada los datos de metrogest.db (SQLite) a la base PostgreSQL definida en DATABASE_URL.

Requiere que el esquema ya exista en PostgreSQL (alembic upgrade head).
Uso: python migrar_a_postgres.py
"""
import sqlite3

from sqlalchemy import Boolean, create_engine, insert
from sqlalchemy.orm import Session

import models
from database import Base, DATABASE_URL

SQLITE_PATH = "metrogest.db"


def main():
    if DATABASE_URL.startswith("sqlite"):
        raise SystemExit("DATABASE_URL sigue apuntando a SQLite. Configura la URL de Postgres en .env antes de migrar.")

    pg_engine = create_engine(DATABASE_URL)
    sqlite_conn = sqlite3.connect(SQLITE_PATH)
    sqlite_conn.row_factory = sqlite3.Row

    total_filas = 0
    with pg_engine.begin() as pg_conn:
        for table in Base.metadata.sorted_tables:
            cur = sqlite_conn.execute(f'SELECT * FROM "{table.name}"')
            rows = cur.fetchall()
            if not rows:
                print(f"  {table.name}: 0 filas (omitida)")
                continue

            bool_cols = {c.name for c in table.columns if isinstance(c.type, Boolean)}
            registros = []
            for row in rows:
                registro = dict(row)
                for col in bool_cols:
                    if col in registro and registro[col] is not None:
                        registro[col] = bool(registro[col])
                registros.append(registro)

            pg_conn.execute(insert(table), registros)
            total_filas += len(registros)
            print(f"  {table.name}: {len(registros)} filas")

            # Reajustar la secuencia del PK para que el próximo INSERT sin id explícito no choque
            pk_cols = [c.name for c in table.primary_key.columns]
            if len(pk_cols) == 1 and pk_cols[0] == "id":
                pg_conn.exec_driver_sql(
                    f"SELECT setval(pg_get_serial_sequence('{table.name}', 'id'), "
                    f"COALESCE((SELECT MAX(id) FROM {table.name}), 1), "
                    f"(SELECT MAX(id) FROM {table.name}) IS NOT NULL)"
                )

    sqlite_conn.close()
    print(f"\nListo: {total_filas} filas migradas en total.")


if __name__ == "__main__":
    main()
