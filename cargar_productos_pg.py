import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL no definida")

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

    ("Hamburguesa Común", 6500, "Sandwiches", "sanguche"),
    ("Hamburguesa Especial", 8000, "Sandwiches", "especial"),

    # ================= PIZZAS =================
    ("Pizza Común Media", 5500, "Pizzas", "normal"),
    ("Pizza Común Completa", 8000, "Pizzas", "normal"),
    ("Pizza Especial Media", 6000, "Pizzas", "normal"),
    ("Pizza Especial Completa", 10000, "Pizzas", "normal"),

    # ================= BEBIDAS =================
    ("Coca Cola 1.5 LT", 3500, "Bebidas", "normal"),
    ("Pepsi 2 LT", 3000, "Bebidas", "normal"),
    ("Agua", 2500, "Bebidas", "normal"),
]

con = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = con.cursor()

print("🗑️ Borrando productos...")
cur.execute("DELETE FROM productos")

print("📦 Cargando productos...")
cur.executemany("""
    INSERT INTO productos (nombre, precio, categoria, tipo)
    VALUES (%s, %s, %s, %s)
""", productos)

con.commit()
con.close()

print("✅ Productos cargados correctamente")
