import sqlite3

con = sqlite3.connect("database.db")
cur = con.cursor()

try:
    cur.execute("ALTER TABLE productos ADD COLUMN tipo TEXT DEFAULT 'normal'")
    print("✅ Columna 'tipo' agregada correctamente")
except sqlite3.OperationalError as e:
    print("⚠️ No se pudo agregar (probablemente ya exista):", e)

con.commit()
con.close()
