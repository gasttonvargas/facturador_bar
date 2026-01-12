from flask import Flask, render_template, request, redirect, session, flash, jsonify
import sqlite3
from datetime import date, datetime
from functools import wraps
from hashlib import sha256
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = 'lavespucio_2025_cambiar_en_produccion'

# ========== SOLUCIÓN AL ERROR "database is locked" ==========
# 1. Timeout aumentado a 30 segundos
# 2. Context manager para cerrar automáticamente
# 3. check_same_thread=False para permitir múltiples hilos
@contextmanager
def get_db():
    """Context manager para manejar conexiones SQLite de forma segura"""
    con = sqlite3.connect("database.db", timeout=30.0, check_same_thread=False)
    con.row_factory = sqlite3.Row
    # Configuración para mejorar concurrencia
    con.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
    try:
        yield con
    finally:
        con.close()

def init_db():
    with get_db() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo INTEGER DEFAULT 1
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            precio INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            tipo TEXT DEFAULT 'normal'
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS turnos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT,
            estado TEXT,
            total INTEGER DEFAULT 0,
            usuario_apertura TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turno_id INTEGER,
            medio_pago TEXT,
            total INTEGER,
            estado TEXT,
            usuario TEXT,
            fecha_hora TEXT,
            tipo_pedido TEXT DEFAULT 'mesa',
            direccion_entrega TEXT,
            estado_pago TEXT DEFAULT 'pagado',
            estado_cocina TEXT DEFAULT 'pendiente',
            estado_delivery TEXT DEFAULT 'pendiente',
            pago_recibido INTEGER DEFAULT 0,
            vuelto INTEGER DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            venta_id INTEGER,
            producto TEXT,
            cantidad INTEGER,
            precio INTEGER,
            extras TEXT DEFAULT '',
            observaciones TEXT DEFAULT ''
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mesa TEXT NOT NULL,
            fecha_hora TEXT,
            estado TEXT DEFAULT 'PENDIENTE',
            total INTEGER DEFAULT 0
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pedido_detalle (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pedido_id INTEGER,
            producto TEXT,
            cantidad INTEGER,
            precio INTEGER,
            extras TEXT DEFAULT '',
            observaciones TEXT DEFAULT ''
        )
        """)

        con.commit()

# ---------- DECORADORES ----------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        if session.get('rol') != 'ADMIN':
            flash('Acceso solo para administradores', 'danger')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

# ---------- TURNO ----------
def turno_activo():
    with get_db() as con:
        cur = con.cursor()
        turno = cur.execute("SELECT * FROM turnos WHERE estado='ABIERTO'").fetchone()
        
        if not turno:
            cur.execute(
                "INSERT INTO turnos (fecha, estado, usuario_apertura) VALUES (?, 'ABIERTO', ?)",
                (date.today().isoformat(), session.get('username', 'Sistema'))
            )
            con.commit()
            turno = cur.execute("SELECT * FROM turnos WHERE estado='ABIERTO'").fetchone()
        
        return turno

# ---------- LOGIN ----------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = sha256(request.form["password"].encode()).hexdigest()
        
        with get_db() as con:
            user = con.execute(
                "SELECT * FROM usuarios WHERE username=? AND password=? AND activo=1",
                (username, password)
            ).fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['rol'] = user['rol']
            return redirect(f"/comanda/{venta_id}")
        else:
            flash("Credenciales incorrectas", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- DASHBOARD ----------
@app.route("/dashboard")
@admin_required
def dashboard():
    with get_db() as con:
        turno = turno_activo()
        
        ventas_hoy = con.execute(
            "SELECT COUNT(*) as total FROM ventas WHERE DATE(fecha_hora) = DATE('now') AND estado='OK'"
        ).fetchone()['total']
        
        total_hoy = con.execute(
            "SELECT IFNULL(SUM(total),0) as total FROM ventas WHERE DATE(fecha_hora) = DATE('now') AND estado='OK'"
        ).fetchone()['total']
        
        productos_activos = con.execute("SELECT COUNT(*) as total FROM productos").fetchone()['total']
    
    stats = {
        'turno': turno,
        'ventas_hoy': ventas_hoy,
        'total_hoy': total_hoy,
        'productos_activos': productos_activos
    }
    
    return render_template('dashboard.html', stats=stats)

# ---------- VENTAS MEJORADAS ----------
@app.route("/", methods=["GET", "POST"])
@login_required
def ventas():
    with get_db() as con:
        productos = con.execute("SELECT * FROM productos ORDER BY categoria, nombre").fetchall()
        turno = turno_activo()
        
        if request.method == "POST":
            medio = request.form["medio_pago"]
            tipo_pedido = request.form.get("tipo_pedido", "mesa")
            direccion = request.form.get("direccion_entrega", "")
            estado_pago = request.form.get("estado_pago", "pagado")
            pago_recibido = request.form.get("pago_recibido")
            pago_recibido = int(pago_recibido) if pago_recibido and pago_recibido.isdigit() else 0
            
            total = 0
            
            cur = con.cursor()
            cur.execute("""
                INSERT INTO ventas (turno_id, medio_pago, total, estado, usuario, fecha_hora, 
                                   tipo_pedido, direccion_entrega, estado_pago, estado_cocina, estado_delivery,
                                   pago_recibido, vuelto)
                VALUES (?, ?, 0, 'OK', ?, ?, ?, ?, ?, 'pendiente', 'pendiente', 0, 0)
            """, (turno["id"], medio, session['username'], datetime.now().isoformat(), 
                  tipo_pedido, direccion, estado_pago))
            venta_id = cur.lastrowid
            
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    cur.execute("""
                        INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (venta_id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            # Calcular vuelto
            vuelto = max(0, pago_recibido - total)
            
            cur.execute("UPDATE ventas SET total=?, vuelto=? WHERE id=?", (total, vuelto, venta_id))
            con.commit()
            
            flash(f'Venta #{venta_id} registrada - ${total} - {tipo_pedido.upper()} - Vuelto: ${vuelto}', 'success')
            return redirect("/")
        
        ventas = con.execute("""
            SELECT * FROM ventas WHERE turno_id=? AND estado='OK' ORDER BY id DESC
        """, (turno["id"],)).fetchall()
        
        categorias = {}
        for p in productos:
            categorias.setdefault(p["categoria"], []).append(p)
    
    return render_template("ventas.html", categorias=categorias, ventas=ventas, turno=turno)

# ---------- PEDIDOS QR (CORREGIDO) ----------
@app.route("/mesa/<mesa>", methods=["GET", "POST"])
def mesa(mesa):
    with get_db() as con:
        productos = con.execute("SELECT * FROM productos WHERE precio > 0 ORDER BY categoria, nombre").fetchall()
        
        categorias = {}
        for p in productos:
            categorias.setdefault(p["categoria"], []).append(p)
        
        if request.method == "POST":
            total = 0
            cur = con.cursor()
            
            # Insertar pedido
            cur.execute(
                "INSERT INTO pedidos (mesa, fecha_hora, estado, total) VALUES (?, ?, 'PENDIENTE', 0)",
                (mesa, datetime.now().isoformat())
            )
            pedido_id = cur.lastrowid
            
            # Insertar detalles
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    cur.execute("""
                        INSERT INTO pedido_detalle (pedido_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (pedido_id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            # Actualizar total
            cur.execute("UPDATE pedidos SET total=? WHERE id=?", (total, pedido_id))
            con.commit()
            
            return render_template("pedido_confirmado.html", mesa=mesa, total=total)
    
    return render_template("mesa.html", categorias=categorias, mesa=mesa)

# ---------- COMANDA MEJORADA ----------
@app.route("/comanda/<int:venta_id>")
@login_required
def imprimir_comanda(venta_id):
    with get_db() as con:
        venta = con.execute("SELECT * FROM ventas WHERE id=?", (venta_id,)).fetchone()
        detalle = con.execute("SELECT * FROM detalle_venta WHERE venta_id=?", (venta_id,)).fetchall()
    
    if not venta:
        flash('Venta no encontrada', 'danger')
        return redirect("/")
    
    return render_template("comanda.html", venta=venta, detalle=detalle)

# ---------- PEDIDOS ----------
@app.route("/pedidos")
@login_required
def pedidos():
    with get_db() as con:
        pedidos_db = con.execute("SELECT * FROM pedidos WHERE estado='PENDIENTE' ORDER BY id ASC").fetchall()
        pedidos_lista = []
        for p in pedidos_db:
            detalle = con.execute("SELECT * FROM pedido_detalle WHERE pedido_id=?", (p["id"],)).fetchall()
            pedidos_lista.append({
                "id": p["id"],
                "mesa": p["mesa"],
                "total": p["total"],
                "fecha_hora": p["fecha_hora"],
                "detalle": detalle
            })
    
    return render_template("pedidos.html", pedidos=pedidos_lista)

@app.route("/pedidos/confirmar/<int:id>")
@login_required
def confirmar_pedido(id):
    with get_db() as con:
        pedido = con.execute("SELECT * FROM pedidos WHERE id=?", (id,)).fetchone()
        if pedido:
            turno = turno_activo()
            cur = con.cursor()
            cur.execute("""
                INSERT INTO ventas (turno_id, medio_pago, total, estado, usuario, fecha_hora,
                                   tipo_pedido, estado_cocina, estado_delivery, pago_recibido, vuelto)
                VALUES (?, 'Mesa', ?, 'OK', ?, ?, 'mesa', 'pendiente', 'no_aplica', 0, 0)
            """, (turno["id"], pedido["total"], session['username'], datetime.now().isoformat()))
            venta_id = cur.lastrowid
            
            detalle = con.execute("SELECT * FROM pedido_detalle WHERE pedido_id=?", (id,)).fetchall()
            for d in detalle:
                cur.execute("""
                    INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (venta_id, d["producto"], d["cantidad"], d["precio"], d["extras"], d["observaciones"]))
            
            cur.execute("UPDATE pedidos SET estado='CONFIRMADO' WHERE id=?", (id,))
            con.commit()
            flash(f'Pedido Mesa {pedido["mesa"]} confirmado como Venta #{venta_id}', 'success')
    
    return redirect("/pedidos")

@app.route("/pedidos/cancelar/<int:id>")
@login_required
def cancelar_pedido(id):
    with get_db() as con:
        con.execute("UPDATE pedidos SET estado='CANCELADO' WHERE id=?", (id,))
        con.commit()
    
    flash('Pedido cancelado', 'warning')
    return redirect("/pedidos")

# ---------- COCINA ----------
@app.route("/cocina")
@login_required
def cocina():
    with get_db() as con:
        ventas_pendientes = con.execute("""
            SELECT v.*, GROUP_CONCAT(dv.cantidad || 'x ' || dv.producto || 
                   CASE WHEN dv.extras != '' THEN ' [' || dv.extras || ']' ELSE '' END ||
                   CASE WHEN dv.observaciones != '' THEN ' (' || dv.observaciones || ')' ELSE '' END, ', ') as detalle
            FROM ventas v
            LEFT JOIN detalle_venta dv ON v.id = dv.venta_id
            WHERE v.estado_cocina = 'pendiente'
            GROUP BY v.id
            ORDER BY v.id ASC
        """).fetchall()
    
    return render_template("cocina.html", ventas=ventas_pendientes)

@app.route("/cocina/listo/<int:venta_id>")
@login_required
def cocina_listo(venta_id):
    with get_db() as con:
        con.execute("UPDATE ventas SET estado_cocina='listo' WHERE id=?", (venta_id,))
        con.commit()
    
    flash(f'Venta #{venta_id} lista para delivery', 'success')
    return redirect("/cocina")

# ---------- DELIVERY ----------
@app.route("/delivery")
@login_required
def delivery():
    with get_db() as con:
        ventas_delivery = con.execute("""
            SELECT v.*, GROUP_CONCAT(dv.cantidad || 'x ' || dv.producto, ', ') as detalle
            FROM ventas v
            LEFT JOIN detalle_venta dv ON v.id = dv.venta_id
            WHERE v.tipo_pedido = 'delivery' AND v.estado_cocina = 'listo' AND v.estado_delivery = 'pendiente'
            GROUP BY v.id
            ORDER BY v.id ASC
        """).fetchall()
    
    return render_template("delivery.html", ventas=ventas_delivery)

@app.route("/delivery/entregado/<int:venta_id>")
@login_required
def delivery_entregado(venta_id):
    with get_db() as con:
        con.execute("UPDATE ventas SET estado_delivery='entregado' WHERE id=?", (venta_id,))
        con.commit()
    
    flash(f'Venta #{venta_id} marcada como entregada', 'success')
    return redirect("/delivery")

# ---------- API ----------
@app.route("/api/pedidos/nuevos")
@login_required
def api_pedidos_nuevos():
    with get_db() as con:
        count = con.execute("SELECT COUNT(*) as total FROM pedidos WHERE estado='PENDIENTE'").fetchone()['total']
    
    return jsonify({"count": count})

@app.route("/api/pedidos/nuevos/detalle")
@login_required
def api_pedidos_nuevos_detalle():
    with get_db() as con:
        pedidos_db = con.execute("SELECT id, mesa, total FROM pedidos WHERE estado='PENDIENTE' ORDER BY id ASC").fetchall()
        pedidos_lista = []
        for p in pedidos_db:
            detalle = con.execute("SELECT producto, cantidad, precio, extras, observaciones FROM pedido_detalle WHERE pedido_id=?", (p["id"],)).fetchall()
            pedidos_lista.append({
                "id": p["id"],
                "mesa": p["mesa"],
                "total": p["total"],
                "detalle": [{"producto": d["producto"], "cantidad": d["cantidad"], "precio": d["precio"], 
                            "extras": d["extras"], "observaciones": d["observaciones"]} for d in detalle]
            })
    
    return jsonify({"pedidos": pedidos_lista})

# ---------- PRODUCTOS ----------
@app.route("/productos", methods=["GET", "POST"])
@admin_required
def productos():
    with get_db() as con:
        if request.method == "POST":
            tipo = request.form.get("tipo", "normal")
            con.execute("INSERT INTO productos (nombre, precio, categoria, tipo) VALUES (?, ?, ?, ?)",
                        (request.form["nombre"], request.form["precio"], request.form["categoria"], tipo))
            con.commit()
            flash('Producto agregado', 'success')
            return redirect("/productos")
        
        productos = con.execute("SELECT * FROM productos ORDER BY categoria, nombre").fetchall()
    
    return render_template("productos.html", productos=productos)

@app.route("/editar_producto/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_producto(id):
    with get_db() as con:
        producto = con.execute("SELECT * FROM productos WHERE id=?", (id,)).fetchone()
        if not producto:
            flash('Producto no encontrado', 'danger')
            return redirect("/productos")
        
        if request.method == "POST":
            tipo = request.form.get("tipo", "normal")
            con.execute("UPDATE productos SET nombre=?, precio=?, categoria=?, tipo=? WHERE id=?",
                        (request.form["nombre"], request.form["precio"], request.form["categoria"], tipo, id))
            con.commit()
            flash('Producto actualizado', 'success')
            return redirect("/productos")
    
    return render_template("editar_producto.html", producto=producto)

@app.route("/eliminar_producto/<int:id>")
@admin_required
def eliminar_producto(id):
    with get_db() as con:
        con.execute("DELETE FROM productos WHERE id=?", (id,))
        con.commit()
    
    flash('Producto eliminado', 'warning')
    return redirect("/productos")

# ---------- EDITAR VENTA ----------
@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_venta(id):
    with get_db() as con:
        venta = con.execute("SELECT * FROM ventas WHERE id=?", (id,)).fetchone()
        
        if not venta:
            flash('Venta no encontrada', 'danger')
            return redirect("/")
        
        detalle = con.execute("SELECT * FROM detalle_venta WHERE venta_id=?", (id,)).fetchall()
        productos = con.execute("SELECT * FROM productos").fetchall()
        
        if request.method == "POST":
            con.execute("DELETE FROM detalle_venta WHERE venta_id=?", (id,))
            
            total = 0
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    con.execute("""
                        INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            con.execute("UPDATE ventas SET total=? WHERE id=?", (total, id))
            con.commit()
            flash(f'Venta #{id} actualizada', 'success')
            return redirect("/")
    
    return render_template("editar_venta.html", venta=venta, detalle=detalle, productos=productos)

@app.route("/ventas/eliminar/<int:id>")
@login_required
def eliminar_venta(id):
    with get_db() as con:
        venta = con.execute(
            "SELECT * FROM ventas WHERE id=?",
            (id,)
        ).fetchone()

        if not venta:
            flash("La venta no existe", "danger")
            return redirect("/")

        # Eliminar detalle
        con.execute("DELETE FROM detalle_venta WHERE venta_id=?", (id,))

        # Eliminar venta
        con.execute("DELETE FROM ventas WHERE id=?", (id,))

        con.commit()

    flash(f"Venta #{id} eliminada correctamente", "warning")
    return redirect("/")



# ---------- TURNOS ----------
@app.route("/turnos")
@admin_required
def turnos():
    with get_db() as con:
        turnos = con.execute("SELECT * FROM turnos ORDER BY id DESC LIMIT 30").fetchall()
        mensual = con.execute("SELECT IFNULL(SUM(total),0) total FROM turnos WHERE estado='CERRADO'").fetchone()["total"]
    
    return render_template("turnos.html", turnos=turnos, mensual=mensual)

@app.route("/cerrar_turno")
@admin_required
def cerrar_turno():
    with get_db() as con:
        turno = con.execute("SELECT * FROM turnos WHERE estado='ABIERTO'").fetchone()
        if turno:
            total = con.execute("SELECT IFNULL(SUM(total),0) total FROM ventas WHERE turno_id=? AND estado='OK'", (turno["id"],)).fetchone()["total"]
            detalle_productos = con.execute("""
                SELECT producto, SUM(cantidad) as cantidad, SUM(cantidad * precio) as total
                FROM detalle_venta
                WHERE venta_id IN (SELECT id FROM ventas WHERE turno_id=? AND estado='OK')
                GROUP BY producto
                ORDER BY cantidad DESC
            """, (turno["id"],)).fetchall()
            con.execute("UPDATE turnos SET estado='CERRADO', total=? WHERE id=?", (total, turno["id"]))
            con.commit()
            return render_template("cierre_turno.html", turno=turno, total=total, detalle=detalle_productos)
        
        flash('No hay turno abierto', 'warning')
        return redirect("/turnos")

# ---------- MAIN ----------
if __name__ == "__main__":
    init_db()
    app.run(debug=True, host='0.0.0.0', port=5000)