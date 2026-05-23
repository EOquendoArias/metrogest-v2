import sqlite3

conn = sqlite3.connect('metrogest.db')
cur = conn.cursor()

columnas = [
    "ALTER TABLE config_laboratorio ADD COLUMN codigo_formato_ilac TEXT DEFAULT 'FOR-MET-006'",
    "ALTER TABLE config_laboratorio ADD COLUMN version_ilac TEXT DEFAULT '1.0'",
    "ALTER TABLE calibraciones ADD COLUMN usar_incertidumbre INTEGER DEFAULT 1",
    "ALTER TABLE evaluaciones_riesgo ADD COLUMN justificacion_exceso TEXT",
    "ALTER TABLE planes_verificacion ALTER COLUMN frecuencia_meses DROP NOT NULL",
]

for sql in columnas:
    try:
        cur.execute(sql)
        print(f"OK: {sql[:70]}")
    except Exception as e:
        print(f"Ya existe o no aplica: {str(e)[:70]}")

conn.commit()
conn.close()
print("\nMigracion completada. Ya puedes iniciar MetroGest.")
