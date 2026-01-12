import sqlite3
from hashlib import sha256

def crear_usuarios():
    """Crea los usuarios por defecto en la base de datos"""
    
    con = sqlite3.connect("database.db")
    cur = con.cursor()
    
    # Verificar que existe la tabla usuarios
    cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER DEFAULT 1
        )
    """)
    
    usuarios = [
        ('admin', 'admin123', 'ADMIN'),
        ('caja1', 'caja123', 'USUARIO'),
        ('mozo1', 'mozo123', 'USUARIO')
    ]
    
    print("🔐 Creando usuarios...")
    print()
    
    for username, password, rol in usuarios:
        password_hash = sha256(password.encode()).hexdigest()
        
        try:
            cur.execute(
                "INSERT INTO usuarios (username, password, rol) VALUES (?, ?, ?)",
                (username, password_hash, rol)
            )
            print(f"✅ Usuario '{username}' creado - Rol: {rol} - Pass: {password}")
        except sqlite3.IntegrityError:
            print(f"⚠️  Usuario '{username}' ya existe")
    
    con.commit()
    con.close()
    
    print()
    print("=" * 60)
    print("🎉 Usuarios listos")
    print("=" * 60)
    print()
    print("🔐 CREDENCIALES:")
    print("   ADMIN:   admin / admin123")
    print("   CAJA:    caja1 / caja123")
    print("   MOZO:    mozo1 / mozo123")
    print()
    print("⚠️  CAMBIAR EN PRODUCCIÓN")
    print()

if __name__ == "__main__":
    crear_usuarios()