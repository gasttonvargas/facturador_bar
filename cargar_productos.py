import sqlite3

DB_NAME = "database.db"

def db():
    con = sqlite3.connect(DB_NAME)
    con.row_factory = sqlite3.Row
    return con

def crear_tabla():
    con = db()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS productos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nombre TEXT NOT NULL,
        precio INTEGER NOT NULL,
        categoria TEXT NOT NULL,
        tipo TEXT DEFAULT 'normal'
    )
    """)

    con.commit()
    con.close()

def borrar_productos():
    con = db()
    cur = con.cursor()
    cur.execute("DELETE FROM productos")
    con.commit()
    con.close()

def cargar_productos():
    # FORMATO: (nombre, precio, categoria, tipo)
    # tipo puede ser: 'normal', 'sanguche', 'especial'
    
    productos = [

        # ================= SÁNDWICHES =================
        ("Milanesa de Carne Común", 6500, "Sandwiches", "sanguche"),
        ("Milanesa de Carne Especial", 8000, "Sandwiches", "especial"),

        ("Milanesa de Pollo Común", 5000, "Sandwiches", "sanguche"),
        ("Milanesa de Pollo Especial", 6500, "Sandwiches", "especial"),

        ("Milanesa Larga Común", 12500, "Sandwiches", "sanguche"),
        ("Milanesa Larga Especial", 13500, "Sandwiches", "especial"),

        ("Lomito Común", 7500, "Sandwiches", "sanguche"),
        ("Lomito Especial", 9000, "Sandwiches", "especial"),

        ("Lomito Largo Común", 14000, "Sandwiches", "sanguche"),
        ("Lomito Largo Especial", 15000, "Sandwiches", "especial"),

        ("Hamburguesa Común", 6500, "Sandwiches", "sanguche"),
        ("Hamburguesa Especial", 8000, "Sandwiches", "especial"),

        ("Hamburguesa Larga Común", 12500, "Sandwiches", "sanguche"),
        ("Hamburguesa Larga Especial", 13500, "Sandwiches", "especial"),

        # ================= PIZZAS =================
        ("Pizza Común Media", 5500, "Pizzas", "normal"),
        ("Pizza Común Completa", 8000, "Pizzas", "normal"),

        ("Pizza Especial Media", 6000, "Pizzas", "normal"),
        ("Pizza Especial Completa", 10000, "Pizzas", "normal"),

        ("Pizza Fugazzeta Media", 6000, "Pizzas", "normal"),
        ("Pizza Fugazzeta Completa", 10000, "Pizzas", "normal"),

        ("Pizza Napolitana Media", 6000, "Pizzas", "normal"),
        ("Pizza Napolitana Completa", 10000, "Pizzas", "normal"),

        ("Pizza de Ternera Media", 7500, "Pizzas", "normal"),
        ("Pizza de Ternera Completa", 13000, "Pizzas", "normal"),

        # ================= ESPECIALES =================
        ("Mexicano Para Uno", 8000, "Especiales", "normal"),
        ("Mexicano Para Dos", 14500, "Especiales", "normal"),

        ("Napolitana Para Uno", 8500, "Especiales", "normal"),
        ("Napolitana Para Dos", 15000, "Especiales", "normal"),

        # ================= EMPANADAS =================
        ("Empanada Unidad", 1500, "Empanadas", "normal"),
        ("Empanadas Media Docena", 6500, "Empanadas", "normal"),
        ("Empanadas Docena", 12000, "Empanadas", "normal"),

        # ================= GUARNICIONES Y EXTRAS =================
        ("Papas Fritas", 5000, "Guarniciones", "normal"),
        ("Papas Gratinadas", 6000, "Guarniciones", "normal"),
        ("Agregado Extra", 1000, "Extras", "normal"),

        # ================= BEBIDAS =================
        ("Coca Cola 1.5 LT", 3500, "Bebidas", "normal"),
        ("Pepsi / Mirinda / Seven 2 LT", 3000, "Bebidas", "normal"),
        ("Coca Cola 1 LT", 2800, "Bebidas", "normal"),
        ("Agua", 2500, "Bebidas", "normal"),
        ("Jugo Fresh", 2500, "Bebidas", "normal"),
        ("Soda", 2000, "Bebidas", "normal"),

        # ================= MIGA =================
        ("Miga Ternera con Verduras", 0, "Miga", "normal"),
        ("Miga Ternera con Queso", 0, "Miga", "normal"),
        ("Miga Pollo con Verduras", 0, "Miga", "normal"),
        ("Miga Jamón y Queso", 0, "Miga", "normal"),
    ]

    con = db()
    cur = con.cursor()

    cur.executemany("""
        INSERT INTO productos (nombre, precio, categoria, tipo)
        VALUES (?, ?, ?, ?)
    """, productos)

    con.commit()
    con.close()

if __name__ == "__main__":
    print("📦 Inicializando carga de productos...")

    crear_tabla()

    opcion = input("¿Borrar productos existentes? (s/n): ").lower()

    if opcion == "s":
        borrar_productos()
        print("🗑️ Productos anteriores eliminados")

    cargar_productos()
    print("✅ Productos cargados correctamente")
    print("📝 Tipos asignados: 'sanguche' para sándwiches comunes, 'especial' para especiales")