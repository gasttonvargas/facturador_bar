import sqlite3

DB = "database.db"

con = sqlite3.connect(DB)
cur = con.cursor()

def add_column(table, col, definition):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        print(f"✅ {table}.{col} agregado")
    except sqlite3.OperationalError:
        print(f"ℹ️ {table}.{col} ya existe")

print("🔧 Actualizando base de datos...")
print()

# --- CAMPOS PARA REPOSICIÓN DE VENTAS ---
add_column("ventas", "repuesta", "INTEGER DEFAULT 0")
add_column("ventas", "fecha_reposicion", "TEXT")
add_column("ventas", "usuario_reposicion", "TEXT")
add_column("ventas", "motivo_reposicion", "TEXT")

print()
print("✅ Base de datos actualizada correctamente")
print()
print("📝 Campos agregados:")
print("   - ventas.repuesta (0 = normal, 1 = repuesta)")
print("   - ventas.fecha_reposicion")
print("   - ventas.usuario_reposicion")
print("   - ventas.motivo_reposicion")

con.commit()
con.close()