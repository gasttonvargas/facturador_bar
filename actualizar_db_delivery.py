import sqlite3
con = sqlite3.connect("database.db")
cur = con.cursor()

# Verificar estructura de ventas
info = cur.execute("PRAGMA table_info(ventas)").fetchall()
columnas = [i[1] for i in info]
print("Columnas en ventas:")
print(columnas)

# Buscar si existen los campos necesarios
campos_necesarios = ['estado_delivery', 'estado_delivery', 'direccion_entrega', 'estado_pago']
for campo in campos_necesarios:
    if campo in columnas:
        print(f"✅ {campo} existe")
    else:
        print(f"❌ {campo} NO EXISTE - hay que agregarlo")

con.close()