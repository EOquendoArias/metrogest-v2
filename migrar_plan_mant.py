"""Agrega la tabla planes_mantenimiento a la base de datos."""
import sqlite3

conn = sqlite3.connect('metrogest.db')
cur = conn.cursor()

sql = """
CREATE TABLE IF NOT EXISTS planes_mantenimiento (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    equipo_id INTEGER NOT NULL REFERENCES equipos(id),
    activo INTEGER DEFAULT 1,
    frecuencia_meses INTEGER NOT NULL DEFAULT 6,
    tipo_preferido VARCHAR(30) DEFAULT 'preventivo',
    responsable VARCHAR(150),
    empresa_externa VARCHAR(200),
    procedimiento TEXT,
    observaciones TEXT,
    created_at DATETIME DEFAULT (CURRENT_TIMESTAMP)
);
"""
try:
    cur.execute(sql)
    conn.commit()
    print("✓ Tabla planes_mantenimiento creada")
except Exception as e:
    print(f"Info: {e}")

conn.close()
print("Migración completada.")
