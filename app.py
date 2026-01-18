from flask import Flask, render_template, request, redirect, session, flash, jsonify, send_from_directory
import os
from datetime import date, datetime, timedelta
from functools import wraps
from hashlib import sha256
from contextlib import contextmanager

import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev_secret")

# ========= DATABASE =========
DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError("❌ DATABASE_URL no está definida en las variables de entorno")

# Fix postgres:// -> postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)


# ========= DB CONNECTION =========
@contextmanager
def get_db():
    con = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()

# ========= INIT DB =========
def init_db():
    with get_db() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            rol TEXT NOT NULL,
            activo BOOLEAN DEFAULT TRUE
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS productos (
            id SERIAL PRIMARY KEY,
            nombre TEXT NOT NULL,
            precio INTEGER NOT NULL,
            categoria TEXT NOT NULL,
            tipo TEXT DEFAULT 'normal'
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS turnos (
            id SERIAL PRIMARY KEY,
            fecha DATE,
            estado TEXT,
            total INTEGER DEFAULT 0,
            usuario_apertura TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS ventas (
            id SERIAL PRIMARY KEY,
            turno_id INTEGER,
            medio_pago TEXT,
            total INTEGER,
            estado TEXT,
            usuario TEXT,
            fecha_hora TIMESTAMP,
            tipo_pedido TEXT DEFAULT 'mesa',
            direccion_entrega TEXT,
            estado_pago TEXT DEFAULT 'pagado',
            estado_delivery TEXT DEFAULT 'pendiente',
            pago_recibido INTEGER DEFAULT 0,
            vuelto INTEGER DEFAULT 0,
            reposicion BOOLEAN DEFAULT FALSE,
            fecha_reposicion TIMESTAMP,
            usuario_reposicion TEXT,
            motivo_reposicion TEXT
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS detalle_venta (
            id SERIAL PRIMARY KEY,
            venta_id INTEGER,
            producto TEXT,
            cantidad INTEGER,
            precio INTEGER,
            extras TEXT DEFAULT '',
            observaciones TEXT DEFAULT ''
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pedidos (
            id SERIAL PRIMARY KEY,
            mesa TEXT NOT NULL,
            fecha_hora TIMESTAMP,
            estado TEXT DEFAULT 'PENDIENTE',
            total INTEGER DEFAULT 0
        );
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pedido_detalle (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER,
            producto TEXT,
            cantidad INTEGER,
            precio INTEGER,
            extras TEXT DEFAULT '',
            observaciones TEXT DEFAULT ''
        );
        """)

# ========= AUTO INIT =========
if __name__ == "__main__":
    init_db()



# ========== DECORADORES DE SEGURIDAD ==========
def login_required(f):
    """Requiere que el usuario esté logueado"""
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
        if session.get('rol', '').lower() != 'admin':
            flash('⛔ Acceso solo para administradores', 'danger')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

def caja_or_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/login')
        if session.get('rol', '').lower() not in ['admin', 'caja']:
            flash('⛔ Acceso solo para administradores o personal de caja', 'danger')
            return redirect('/')
        return f(*args, **kwargs)
    return decorated

# ========== TURNO ==========
def turno_activo():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM turnos WHERE estado='ABIERTO'")
        turno = cur.fetchone()
        
        if not turno:
            cur.execute(
                "INSERT INTO turnos (fecha, estado, usuario_apertura) VALUES (%s, 'ABIERTO', %s)",
                (date.today().isoformat(), session.get('username', 'Sistema'))
            )
            con.commit()
            cur.execute("SELECT * FROM turnos WHERE estado='ABIERTO'")
            turno = cur.fetchone()
        
        return turno

# ========== LOGIN ==========
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = sha256(request.form["password"].encode()).hexdigest()
        
        with get_db() as con:
            cur = con.cursor()
            cur.execute(
                "SELECT * FROM usuarios WHERE username=%s AND password=%s AND activo=TRUE",
                (username, password)
            )
            user = cur.fetchone()
        
        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['rol'] = user['rol']
            return redirect("/")
        else:
            flash("Credenciales incorrectas", "danger")
    
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ========== DASHBOARD ==========
@app.route("/dashboard")
@admin_required
def dashboard():
    with get_db() as con:
        cur = con.cursor()
        turno = turno_activo()
        
        cur.execute(
            "SELECT COUNT(*) as total FROM ventas WHERE DATE(fecha_hora) = CURRENT_DATE AND estado='OK'"
        )
        ventas_hoy = cur.fetchone()['total']
        
        cur.execute(
            "SELECT COALESCE(SUM(total),0) as total FROM ventas WHERE DATE(fecha_hora) = CURRENT_DATE AND estado='OK'"
        )
        total_hoy = cur.fetchone()['total']
        
        cur.execute("SELECT COUNT(*) as total FROM productos")
        productos_activos = cur.fetchone()['total']
    
    stats = {
        'turno': turno,
        'ventas_hoy': ventas_hoy,
        'total_hoy': total_hoy,
        'productos_activos': productos_activos
    }
    
    return render_template('dashboard.html', stats=stats)

# ========== VENTAS ==========
@app.route("/", methods=["GET", "POST"])
@login_required
def ventas():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM productos ORDER BY categoria, nombre")
        productos = cur.fetchall()
        turno = turno_activo()
        
        if request.method == "POST":
            medio = request.form["medio_pago"]
            tipo_pedido = request.form.get("tipo_pedido", "mesa")
            direccion = request.form.get("direccion_entrega", "")
            estado_pago = request.form.get("estado_pago", "pagado")
            pago_recibido = request.form.get("pago_recibido")
            pago_recibido = int(pago_recibido) if pago_recibido and pago_recibido.isdigit() else 0
            
            # Determinar estado_delivery según tipo de pedido
            if tipo_pedido == 'delivery':
                estado_delivery = 'listo'
            else:
                estado_delivery = 'no_aplica'
            
            total = 0
            
            cur.execute("""
                INSERT INTO ventas (turno_id, medio_pago, total, estado, usuario, fecha_hora, 
                                   tipo_pedido, direccion_entrega, estado_pago, estado_delivery,
                                   pago_recibido, vuelto, reposicion)
                VALUES (%s, %s, 0, 'OK', %s, %s, %s, %s, %s, %s, 0, 0, FALSE)
                RETURNING id
            """, (turno["id"], medio, session['username'], datetime.now(), 
                  tipo_pedido, direccion, estado_pago, estado_delivery))
            venta_id = cur.fetchone()['id']
            
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    cur.execute("""
                        INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (venta_id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            vuelto = max(0, pago_recibido - total)
            
            cur.execute("UPDATE ventas SET total=%s, vuelto=%s WHERE id=%s", (total, vuelto, venta_id))
            con.commit()
            
            flash(f'Venta #{venta_id} registrada - ${total} - {tipo_pedido.upper()} - Vuelto: ${vuelto}', 'success')
            return redirect("/")
        
        cur.execute("""
            SELECT * FROM ventas WHERE turno_id=%s AND estado='OK' ORDER BY id DESC
        """, (turno["id"],))
        ventas = cur.fetchall()
        
        categorias = {}
        for p in productos:
            categorias.setdefault(p["categoria"], []).append(p)
    
    return render_template("ventas.html", categorias=categorias, ventas=ventas, turno=turno)

# ========== EDITAR VENTA ==========
@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_venta(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM ventas WHERE id=%s", (id,))
        venta = cur.fetchone()
        
        if not venta:
            flash('Venta no encontrada', 'danger')
            return redirect("/")
        
        cur.execute("SELECT * FROM detalle_venta WHERE venta_id=%s", (id,))
        detalle = cur.fetchall()
        cur.execute("SELECT * FROM productos")
        productos = cur.fetchall()
        
        if request.method == "POST":
            cur.execute("DELETE FROM detalle_venta WHERE venta_id=%s", (id,))
            
            total = 0
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    cur.execute("""
                        INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            cur.execute("UPDATE ventas SET total=%s WHERE id=%s", (total, id))
            con.commit()
            flash(f'Venta #{id} actualizada', 'success')
            return redirect("/")
    
    return render_template("editar_venta.html", venta=venta, detalle=detalle, productos=productos)

# ========== ELIMINAR VENTA ==========
@app.route("/ventas/eliminar/<int:id>")
@login_required
def eliminar_venta(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM ventas WHERE id=%s", (id,))
        venta = cur.fetchone()

        if not venta:
            flash("La venta no existe", "danger")
            return redirect("/")

        cur.execute("UPDATE ventas SET estado='ELIMINADA' WHERE id=%s", (id,))
        con.commit()

    flash(f"Venta #{id} eliminada correctamente", "warning")
    return redirect("/")

# ========== REPONER VENTA ==========
@app.route("/ventas/reponer/<int:id>", methods=["GET", "POST"])
@admin_required
def reponer_venta(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM ventas WHERE id=%s", (id,))
        venta = cur.fetchone()
        
        if not venta:
            flash("La venta no existe", "danger")
            return redirect("/turnos")
        
        if venta['estado'] != 'ELIMINADA':
            flash("Solo se pueden reponer ventas eliminadas", "warning")
            return redirect("/turnos")
        
        if request.method == "POST":
            motivo = request.form.get("motivo", "Sin motivo especificado")
            
            cur.execute("""
                UPDATE ventas 
                SET estado='OK', 
                    reposicion=TRUE, 
                    fecha_reposicion=%s, 
                    usuario_reposicion=%s,
                    motivo_reposicion=%s
                WHERE id=%s
            """, (datetime.now(), session['username'], motivo, id))
            
            con.commit()
            flash(f"✅ Venta #{id} repuesta correctamente", "success")
            return redirect("/turnos")
    
        cur.execute("SELECT * FROM detalle_venta WHERE venta_id=%s", (id,))
        detalle = cur.fetchall()
    
    return render_template("reponer_venta.html", venta=venta, detalle=detalle)

# ========== PEDIDOS QR ==========
@app.route("/mesa/<mesa>", methods=["GET", "POST"])
def mesa(mesa):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM productos WHERE precio > 0 ORDER BY categoria, nombre")
        productos = cur.fetchall()
        
        categorias = {}
        for p in productos:
            categorias.setdefault(p["categoria"], []).append(p)
        
        if request.method == "POST":
            total = 0
            
            cur.execute(
                "INSERT INTO pedidos (mesa, fecha_hora, estado, total) VALUES (%s, %s, 'PENDIENTE', 0) RETURNING id",
                (mesa, datetime.now())
            )
            pedido_id = cur.fetchone()['id']
            
            for p in productos:
                cant = int(request.form.get(f"prod_{p['id']}", 0))
                if cant > 0:
                    total += cant * p["precio"]
                    extras = request.form.get(f"extras_{p['id']}", "")
                    observaciones = request.form.get(f"obs_{p['id']}", "")
                    
                    cur.execute("""
                        INSERT INTO pedido_detalle (pedido_id, producto, cantidad, precio, extras, observaciones)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (pedido_id, p["nombre"], cant, p["precio"], extras, observaciones))
            
            cur.execute("UPDATE pedidos SET total=%s WHERE id=%s", (total, pedido_id))
            con.commit()
            
            return render_template("pedido_confirmado.html", mesa=mesa, total=total)
    
    return render_template("mesa.html", categorias=categorias, mesa=mesa)

# ========== COMANDA ==========
@app.route("/comanda/<int:venta_id>")
@login_required
def imprimir_comanda(venta_id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM ventas WHERE id=%s", (venta_id,))
        venta = cur.fetchone()
        cur.execute("SELECT * FROM detalle_venta WHERE venta_id=%s", (venta_id,))
        detalle = cur.fetchall()
    
    if not venta:
        flash('Venta no encontrada', 'danger')
        return redirect("/")
    
    return render_template("comanda.html", venta=venta, detalle=detalle)

# ========== PEDIDOS ==========
@app.route("/pedidos")
@login_required
def pedidos():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM pedidos WHERE estado='PENDIENTE' ORDER BY id ASC")
        pedidos_db = cur.fetchall()
        pedidos_lista = []
        for p in pedidos_db:
            cur.execute("SELECT * FROM pedido_detalle WHERE pedido_id=%s", (p["id"],))
            detalle = cur.fetchall()
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
        cur = con.cursor()
        cur.execute("SELECT * FROM pedidos WHERE id=%s", (id,))
        pedido = cur.fetchone()
        if pedido:
            turno = turno_activo()
            cur.execute("""
                INSERT INTO ventas (turno_id, medio_pago, total, estado, usuario, fecha_hora,
                                   tipo_pedido, estado_delivery, pago_recibido, vuelto, reposicion)
                VALUES (%s, 'Mesa', %s, 'OK', %s, %s, 'mesa', 'no_aplica', 0, 0, FALSE)
                RETURNING id
            """, (turno["id"], pedido["total"], session['username'], datetime.now()))
            venta_id = cur.fetchone()['id']
            
            cur.execute("SELECT * FROM pedido_detalle WHERE pedido_id=%s", (id,))
            detalle = cur.fetchall()
            for d in detalle:
                cur.execute("""
                    INSERT INTO detalle_venta (venta_id, producto, cantidad, precio, extras, observaciones)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, (venta_id, d["producto"], d["cantidad"], d["precio"], d["extras"], d["observaciones"]))
            
            cur.execute("UPDATE pedidos SET estado='CONFIRMADO' WHERE id=%s", (id,))
            con.commit()
            flash(f'Pedido Mesa {pedido["mesa"]} confirmado como Venta #{venta_id}', 'success')
    
    return redirect("/pedidos")

@app.route("/pedidos/cancelar/<int:id>")
@login_required
def cancelar_pedido(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("UPDATE pedidos SET estado='CANCELADO' WHERE id=%s", (id,))
        con.commit()
    
    flash('Pedido cancelado', 'warning')
    return redirect("/pedidos")

# ========== DELIVERY ==========
@app.route("/delivery")
@login_required
def delivery():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            SELECT *
            FROM ventas
            WHERE tipo_pedido = 'delivery'
              AND estado = 'OK'
              AND estado_delivery IN ('listo', 'enviado')
            ORDER BY id ASC
        """)
        ventas_delivery = cur.fetchall()

        deliveries = []
        for v in ventas_delivery:
            cur.execute("""
                SELECT cantidad, producto, extras, observaciones
                FROM detalle_venta
                WHERE venta_id = %s
            """, (v["id"],))
            detalle = cur.fetchall()

            deliveries.append({
                "id": v["id"],
                "fecha_hora": v["fecha_hora"],
                "direccion_entrega": v["direccion_entrega"],
                "medio_pago": v["medio_pago"],
                "estado_pago": v["estado_pago"],
                "estado_delivery": v["estado_delivery"],
                "total": v["total"],
                "detalle": detalle
            })

        cur.execute("""
            SELECT *
            FROM ventas
            WHERE tipo_pedido = 'delivery'
              AND estado_delivery = 'finalizado'
              AND DATE(fecha_hora) = CURRENT_DATE
            ORDER BY id DESC
            LIMIT 10
        """)
        entregados = cur.fetchall()

        cur.execute("""
            SELECT
                COUNT(*) AS total_pedidos,
                COALESCE(SUM(total), 0) AS total_facturado,
                SUM(CASE WHEN estado_delivery = 'listo' THEN 1 ELSE 0 END) AS listos_enviar,
                SUM(CASE WHEN estado_delivery = 'enviado' THEN 1 ELSE 0 END) AS salio,
                SUM(CASE WHEN estado_delivery = 'finalizado' THEN 1 ELSE 0 END) AS entregados
            FROM ventas
            WHERE tipo_pedido = 'delivery'
              AND estado = 'OK'
              AND DATE(fecha_hora) = CURRENT_DATE
        """)
        stats = cur.fetchone()

    return render_template("delivery.html", deliveries=deliveries, entregados=entregados, stats=stats)

@app.route("/delivery/salio/<int:venta_id>")
@login_required
def delivery_salio(venta_id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("UPDATE ventas SET estado_delivery='enviado' WHERE id=%s", (venta_id,))
        con.commit()
    flash(f'Venta #{venta_id} marcada como Salió', 'info')
    return redirect("/delivery")

@app.route("/delivery/finalizado/<int:venta_id>")
@login_required
def delivery_finalizado(venta_id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("UPDATE ventas SET estado_delivery='finalizado' WHERE id=%s", (venta_id,))
        con.commit()
    flash(f'Venta #{venta_id} marcada como Finalizada', 'success')
    return redirect("/delivery")

# ========== API ==========
@app.route("/api/pedidos/nuevos")
@login_required
def api_pedidos_nuevos():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT COUNT(*) as total FROM pedidos WHERE estado='PENDIENTE'")
        count = cur.fetchone()['total']
    
    return jsonify({"count": count})

@app.route("/api/pedidos/nuevos/detalle")
@login_required
def api_pedidos_nuevos_detalle():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT id, mesa, total FROM pedidos WHERE estado='PENDIENTE' ORDER BY id ASC")
        pedidos_db = cur.fetchall()
        pedidos_lista = []
        for p in pedidos_db:
            cur.execute("SELECT producto, cantidad, precio, extras, observaciones FROM pedido_detalle WHERE pedido_id=%s", (p["id"],))
            detalle = cur.fetchall()
            pedidos_lista.append({
                "id": p["id"],
                "mesa": p["mesa"],
                "total": p["total"],
                "detalle": [{"producto": d["producto"], "cantidad": d["cantidad"], "precio": d["precio"], 
                            "extras": d["extras"], "observaciones": d["observaciones"]} for d in detalle]
            })
    
    return jsonify({"pedidos": pedidos_lista})

# ========== PRODUCTOS ==========
@app.route("/api/productos")
def api_productos():
    try:
        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT * FROM productos WHERE precio > 0 ORDER BY categoria, nombre")
            productos_db = cur.fetchall()
            
            productos_lista = []
            categorias_set = set()
            
            for p in productos_db:
                producto_dict = {
                    "id": str(p["id"]),
                    "nombre": p["nombre"],
                    "precio": p["precio"],
                    "categoria": p["categoria"],
                    "tipo": p.get("tipo", "normal") or "normal"
                }
                
                productos_lista.append(producto_dict)
                categorias_set.add(p["categoria"])
            
            categorias_lista = sorted(list(categorias_set))
        
        return jsonify({
            "productos": productos_lista,
            "categorias": categorias_lista
        })
    
    except Exception as e:
        print(f"❌ Error en /api/productos: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/productos", methods=["GET", "POST"])
@admin_required
def productos():
    with get_db() as con:
        cur = con.cursor()
        if request.method == "POST":
            nombre = request.form.get("nombre")
            precio = request.form.get("precio")
            categoria = request.form.get("categoria")
            tipo = request.form.get("tipo", "normal")

            if not nombre or not precio or not categoria:
                flash("Todos los campos son obligatorios", "danger")
                return redirect("/productos")

            cur.execute("""
                INSERT INTO productos (nombre, precio, categoria, tipo)
                VALUES (%s, %s, %s, %s)
            """, (nombre, int(precio), categoria, tipo))

            con.commit()
            flash("Producto agregado", "success")
            return redirect("/productos")

        cur.execute("SELECT * FROM productos ORDER BY categoria, nombre")
        productos = cur.fetchall()

    return render_template("productos.html", productos=productos)

@app.route("/editar_producto/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_producto(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM productos WHERE id=%s", (id,))
        producto = cur.fetchone()
        if not producto:
            flash('Producto no encontrado', 'danger')
            return redirect("/productos")
        
        if request.method == "POST":
            tipo = request.form.get("tipo", "normal")
            cur.execute("UPDATE productos SET nombre=%s, precio=%s, categoria=%s, tipo=%s WHERE id=%s",
                        (request.form["nombre"], request.form["precio"], request.form["categoria"], tipo, id))
            con.commit()
            flash('Producto actualizado', 'success')
            return redirect("/productos")
    
    return render_template("editar_producto.html", producto=producto)

@app.route("/eliminar_producto/<int:id>")
@admin_required
def eliminar_producto(id):
    with get_db() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM productos WHERE id=%s", (id,))
        con.commit()
    
    flash('Producto eliminado', 'warning')
    return redirect("/productos")

# ========== TURNOS ==========
@app.route("/turnos")
@caja_or_admin_required
def turnos():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM turnos ORDER BY id DESC LIMIT 30")
        turnos = cur.fetchall()
        cur.execute("SELECT COALESCE(SUM(total),0) total FROM turnos WHERE estado='CERRADO'")
        mensual = cur.fetchone()["total"]
        
        ventas_eliminadas = []
        if session.get('rol') == 'ADMIN':
            cur.execute("""
                SELECT v.*, t.fecha as turno_fecha
                FROM ventas v
                LEFT JOIN turnos t ON v.turno_id = t.id
                WHERE v.estado='ELIMINADA'
                ORDER BY v.fecha_hora DESC
                LIMIT 20
            """)
            ventas_eliminadas = cur.fetchall()
    
    return render_template("turnos.html", turnos=turnos, mensual=mensual, ventas_eliminadas=ventas_eliminadas)

@app.route("/cerrar_turno")
@caja_or_admin_required
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

@app.route("/turnos/editar/<int:id>", methods=["GET", "POST"])
@admin_required
def editar_turno(id):
    with get_db() as con:
        turno = con.execute("SELECT * FROM turnos WHERE id=?", (id,)).fetchone()
        
        if not turno:
            flash("Turno no encontrado", "danger")
            return redirect("/turnos")
        
        if turno['estado'] != 'CERRADO':
            flash("Solo se pueden editar turnos cerrados", "warning")
            return redirect("/turnos")
        
        if request.method == "POST":
            nueva_fecha = request.form.get("fecha")
            
            if not nueva_fecha:
                flash("Debe ingresar una fecha válida", "danger")
                return redirect(f"/turnos/editar/{id}")
            
            con.execute("UPDATE turnos SET fecha=? WHERE id=?", (nueva_fecha, id))
            con.commit()
            
            flash(f"✅ Turno #{id} actualizado correctamente", "success")
            return redirect("/turnos")
        
        ventas_turno = con.execute("""
            SELECT * FROM ventas WHERE turno_id=? AND estado='OK' ORDER BY fecha_hora
        """, (id,)).fetchall()
        
        return render_template("editar_turno.html", turno=turno, ventas=ventas_turno)

from datetime import timedelta

# ========== REPORTES ==========
@app.route("/reportes")
@login_required
def reportes():
    """Panel de reportes semanales y mensuales"""
    with get_db() as con:
        hoy = date.today()
        
        # REPORTE SEMANAL
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        
        ventas_semana = con.execute("""
            SELECT COUNT(*) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_semana.isoformat(), fin_semana.isoformat())).fetchone()['total']
        
        total_semana = con.execute("""
            SELECT IFNULL(SUM(total), 0) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_semana.isoformat(), fin_semana.isoformat())).fetchone()['total']
        
        top_semana = con.execute("""
            SELECT 
                dv.producto, 
                SUM(dv.cantidad) as cantidad,
                SUM(dv.cantidad * dv.precio) as total
            FROM detalle_venta dv
            INNER JOIN ventas v ON dv.venta_id = v.id
            WHERE DATE(v.fecha_hora) BETWEEN ? AND ? 
            AND v.estado='OK'
            GROUP BY dv.producto
            ORDER BY cantidad DESC
            LIMIT 10
        """, (inicio_semana.isoformat(), fin_semana.isoformat())).fetchall()
        
        ventas_por_dia_semana = con.execute("""
            SELECT 
                DATE(fecha_hora) as fecha,
                COUNT(*) as ventas,
                SUM(total) as total
            FROM ventas
            WHERE DATE(fecha_hora) BETWEEN ? AND ?
            AND estado='OK'
            GROUP BY DATE(fecha_hora)
            ORDER BY fecha
        """, (inicio_semana.isoformat(), fin_semana.isoformat())).fetchall()
        
        # REPORTE MENSUAL
        inicio_mes = hoy.replace(day=1)
        if hoy.month == 12:
            fin_mes = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            fin_mes = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
        
        ventas_mes = con.execute("""
            SELECT COUNT(*) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchone()['total']
        
        total_mes = con.execute("""
            SELECT IFNULL(SUM(total), 0) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchone()['total']
        
        top_mes = con.execute("""
            SELECT 
                dv.producto, 
                SUM(dv.cantidad) as cantidad,
                SUM(dv.cantidad * dv.precio) as total
            FROM detalle_venta dv
            INNER JOIN ventas v ON dv.venta_id = v.id
            WHERE DATE(v.fecha_hora) BETWEEN ? AND ? 
            AND v.estado='OK'
            GROUP BY dv.producto
            ORDER BY cantidad DESC
            LIMIT 15
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchall()
        
        ventas_por_dia_mes = con.execute("""
            SELECT 
                DATE(fecha_hora) as fecha,
                COUNT(*) as ventas,
                SUM(total) as total
            FROM ventas
            WHERE DATE(fecha_hora) BETWEEN ? AND ?
            AND estado='OK'
            GROUP BY DATE(fecha_hora)
            ORDER BY fecha
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchall()
        
        ventas_por_tipo = con.execute("""
            SELECT 
                tipo_pedido,
                COUNT(*) as cantidad,
                SUM(total) as total
            FROM ventas
            WHERE DATE(fecha_hora) BETWEEN ? AND ?
            AND estado='OK'
            GROUP BY tipo_pedido
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchall()
        
        ventas_por_medio = con.execute("""
            SELECT 
                medio_pago,
                COUNT(*) as cantidad,
                SUM(total) as total
            FROM ventas
            WHERE DATE(fecha_hora) BETWEEN ? AND ?
            AND estado='OK'
            GROUP BY medio_pago
        """, (inicio_mes.isoformat(), fin_mes.isoformat())).fetchall()
        
        # COMPARATIVAS
        inicio_semana_ant = inicio_semana - timedelta(days=7)
        fin_semana_ant = inicio_semana_ant + timedelta(days=6)
        
        total_semana_ant = con.execute("""
            SELECT IFNULL(SUM(total), 0) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_semana_ant.isoformat(), fin_semana_ant.isoformat())).fetchone()['total']
        
        if inicio_mes.month == 1:
            inicio_mes_ant = inicio_mes.replace(year=inicio_mes.year - 1, month=12)
        else:
            inicio_mes_ant = inicio_mes.replace(month=inicio_mes.month - 1)
        
        if inicio_mes_ant.month == 12:
            fin_mes_ant = inicio_mes_ant.replace(year=inicio_mes_ant.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            fin_mes_ant = inicio_mes_ant.replace(month=inicio_mes_ant.month + 1, day=1) - timedelta(days=1)
        
        total_mes_ant = con.execute("""
            SELECT IFNULL(SUM(total), 0) as total
            FROM ventas 
            WHERE DATE(fecha_hora) BETWEEN ? AND ? 
            AND estado='OK'
        """, (inicio_mes_ant.isoformat(), fin_mes_ant.isoformat())).fetchone()['total']
        
        var_semana = ((total_semana - total_semana_ant) / total_semana_ant * 100) if total_semana_ant > 0 else 0
        var_mes = ((total_mes - total_mes_ant) / total_mes_ant * 100) if total_mes_ant > 0 else 0
    
    return render_template('reportes.html',
        inicio_semana=inicio_semana,
        fin_semana=fin_semana,
        ventas_semana=ventas_semana,
        total_semana=total_semana,
        top_semana=top_semana,
        ventas_por_dia_semana=ventas_por_dia_semana,
        total_semana_ant=total_semana_ant,
        var_semana=var_semana,
        inicio_mes=inicio_mes,
        fin_mes=fin_mes,
        ventas_mes=ventas_mes,
        total_mes=total_mes,
        top_mes=top_mes,
        ventas_por_dia_mes=ventas_por_dia_mes,
        ventas_por_tipo=ventas_por_tipo,
        ventas_por_medio=ventas_por_medio,
        total_mes_ant=total_mes_ant,
        var_mes=var_mes
    )

# ========== EXPORTAR REPORTE A CSV ==========
@app.route("/reportes/exportar/<tipo>")
@login_required
def exportar_reporte(tipo):
    """Exportar reporte a CSV"""
    from io import StringIO
    import csv
    from flask import make_response
    
    hoy = date.today()
    
    if tipo == 'semana':
        inicio = hoy - timedelta(days=hoy.weekday())
        fin = inicio + timedelta(days=6)
        nombre = f"reporte_semanal_{inicio.isoformat()}.csv"
    else:
        inicio = hoy.replace(day=1)
        if hoy.month == 12:
            fin = hoy.replace(year=hoy.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            fin = hoy.replace(month=hoy.month + 1, day=1) - timedelta(days=1)
        nombre = f"reporte_mensual_{inicio.strftime('%Y-%m')}.csv"
    
    with get_db() as con:
        ventas = con.execute("""
            SELECT 
                v.id,
                v.fecha_hora,
                v.usuario,
                v.tipo_pedido,
                v.medio_pago,
                v.total,
                GROUP_CONCAT(dv.cantidad || 'x ' || dv.producto, ', ') as productos
            FROM ventas v
            LEFT JOIN detalle_venta dv ON v.id = dv.venta_id
            WHERE DATE(v.fecha_hora) BETWEEN ? AND ?
            AND v.estado='OK'
            GROUP BY v.id
            ORDER BY v.fecha_hora DESC
        """, (inicio.isoformat(), fin.isoformat())).fetchall()
    
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['ID', 'Fecha/Hora', 'Usuario', 'Tipo', 'Medio Pago', 'Total', 'Productos'])
    
    for v in ventas:
        writer.writerow([
            v['id'],
            v['fecha_hora'],
            v['usuario'],
            v['tipo_pedido'],
            v['medio_pago'],
            v['total'],
            v['productos'] or ''
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename={nombre}"
    output.headers["Content-type"] = "text/csv"
    return output


# ========== PWA ROUTES ==========
# ========== PWA ROUTES ==========

@app.route("/mozo")
def mozo_index():
    return send_from_directory("static/pwa", "index.html")

@app.route("/mozo/<path:filename>")
def mozo_static(filename):
    return send_from_directory("static/pwa", filename)
    

# ========== MAIN ==========
if __name__ == "__main__":
    app.run(host="0.0.0.0", debug=True)