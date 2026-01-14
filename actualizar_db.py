import sqlite3

DB = "database.db"

con = sqlite3.connect(DB)
cur = con.cursor()

def add_column(table, col, definition):
    try:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {col} {definition}")
        print(f"✔ {table}.{col} agregado")
    except sqlite3.OperationalError:
        print(f"ℹ {table}.{col} ya existe")

# --- ventas ---
add_column("ventas", "tipo_pedido", "TEXT DEFAULT 'mesa'")
add_column("ventas", "direccion_entrega", "TEXT")
add_column("ventas", "estado_pago", "TEXT DEFAULT 'pagado'")
add_column("ventas", "estado_delivery", "TEXT DEFAULT 'pendiente'")
add_column("ventas", "estado_delivery", "TEXT DEFAULT 'pendiente'")
add_column("ventas", "pago_recibido", "INTEGER DEFAULT 0")
add_column("ventas", "vuelto", "INTEGER DEFAULT 0")

# --- detalle_venta ---
add_column("detalle_venta", "extras", "TEXT DEFAULT ''")
add_column("detalle_venta", "observaciones", "TEXT DEFAULT ''")

# --- pedido_detalle (por las dudas, mismo esquema) ---
add_column("pedido_detalle", "extras", "TEXT DEFAULT ''")
add_column("pedido_detalle", "observaciones", "TEXT DEFAULT ''")

con.commit()
con.close()

print("✅ Base de datos actualizada correctamente")
