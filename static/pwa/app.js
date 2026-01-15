// ===== CONFIGURACIÓN =====
const API_URL = window.location.origin;
const NUM_MESAS = 20;

// ===== ESTADO DE LA APLICACIÓN =====
let mesaActual = null;
let productos = [];
let categorias = [];
let carrito = [];

// ===== ELEMENTOS DEL DOM =====
const viewMesas = document.getElementById('viewMesas');
const viewProductos = document.getElementById('viewProductos');
const mesasGrid = document.getElementById('mesasGrid');
const categoriasContainer = document.getElementById('categoriasContainer');
const productosContainer = document.getElementById('productosContainer');
const footerCarrito = document.getElementById('footerCarrito');
const carritoItems = document.getElementById('carritoItems');
const carritoTotal = document.getElementById('carritoTotal');
const btnEnviar = document.getElementById('btnEnviar');
const mesaBadge = document.getElementById('mesaBadge');
const btnVolver = document.getElementById('btnVolver');
const modalConfirmacion = document.getElementById('modalConfirmacion');
const modalMesa = document.getElementById('modalMesa');
const modalTotal = document.getElementById('modalTotal');
const btnNuevoPedido = document.getElementById('btnNuevoPedido');
const loading = document.getElementById('loading');

// ===== REGISTRO DEL SERVICE WORKER =====
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js')
            .then(reg => console.log('✅ Service Worker registrado'))
            .catch(err => console.log('❌ Error al registrar SW:', err));
    });
}

// ===== INICIALIZACIÓN =====
document.addEventListener('DOMContentLoaded', () => {
    console.log('🚀 Iniciando PWA...');
    inicializarMesas();
    cargarProductos();
    
    btnVolver.addEventListener('click', volverAMesas);
    btnEnviar.addEventListener('click', enviarPedido);
    btnNuevoPedido.addEventListener('click', resetearApp);
});

// ===== FUNCIONES DE MESAS =====
function inicializarMesas() {
    mesasGrid.innerHTML = '';
    
    for (let i = 1; i <= NUM_MESAS; i++) {
        const btn = document.createElement('button');
        btn.className = 'mesa-btn';
        btn.textContent = i;
        btn.onclick = () => seleccionarMesa(i);
        mesasGrid.appendChild(btn);
    }
}

function seleccionarMesa(numero) {
    mesaActual = numero;
    mesaBadge.textContent = `Mesa ${numero}`;
    mesaBadge.style.display = 'inline-block';
    btnVolver.style.display = 'inline-block';
    
    mostrarVista('productos');
    if (categorias.length > 0) {
        renderizarCategorias();
    }
}

function volverAMesas() {
    if (carrito.length > 0) {
        if (!confirm('¿Descartar el pedido actual?')) {
            return;
        }
    }
    
    resetearApp();
}

// ===== FUNCIONES DE PRODUCTOS =====
async function cargarProductos() {
    loading.classList.add('show');
    
    try {
        console.log('📦 Cargando productos desde API...');
        const response = await fetch(`${API_URL}/api/productos`);
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const data = await response.json();
        
        productos = data.productos;
        categorias = data.categorias;
        
        console.log(`✅ ${productos.length} productos cargados en ${categorias.length} categorías`);
        
    } catch (error) {
        console.error('❌ Error cargando productos:', error);
        alert('Error al cargar los productos. Por favor, recarga la página.');
    } finally {
        loading.classList.remove('show');
    }
}

function renderizarCategorias() {
    categoriasContainer.innerHTML = '';
    
    categorias.forEach((cat, index) => {
        const btn = document.createElement('button');
        btn.className = 'categoria-tab';
        if (index === 0) btn.classList.add('active');
        btn.textContent = cat;
        btn.onclick = () => seleccionarCategoria(cat, btn);
        categoriasContainer.appendChild(btn);
    });
    
    if (categorias.length > 0) {
        renderizarProductos(categorias[0]);
    }
}

function seleccionarCategoria(categoria, btnElement) {
    document.querySelectorAll('.categoria-tab').forEach(btn => {
        btn.classList.remove('active');
    });
    btnElement.classList.add('active');
    
    renderizarProductos(categoria);
}

function renderizarProductos(categoria) {
    const productosFiltrados = productos.filter(p => p.categoria === categoria);
    
    productosContainer.innerHTML = '';
    
    if (productosFiltrados.length === 0) {
        productosContainer.innerHTML = '<div class="mensaje"><h3>No hay productos en esta categoría</h3></div>';
        return;
    }
    
    productosFiltrados.forEach(producto => {
        const card = crearProductoCard(producto);
        productosContainer.appendChild(card);
    });
}

function crearProductoCard(producto) {
    const card = document.createElement('div');
    card.className = 'producto-card';
    card.id = `producto-${producto.id}`;
    
    const itemCarrito = carrito.find(item => item.id === producto.id);
    const cantidad = itemCarrito ? itemCarrito.cantidad : 0;
    
    if (cantidad > 0) {
        card.classList.add('selected');
    }
    
    card.innerHTML = `
        <div class="producto-header">
            <div class="producto-info">
                <h3>${producto.nombre}</h3>
                <div class="producto-precio">$${producto.precio}</div>
            </div>
        </div>
        <div class="cantidad-controls">
            <button class="btn-cantidad" onclick="cambiarCantidad('${producto.id}', -1)" ${cantidad === 0 ? 'disabled' : ''}>−</button>
            <div class="cantidad-display" id="cantidad-${producto.id}">${cantidad}</div>
            <button class="btn-cantidad" onclick="cambiarCantidad('${producto.id}', 1)">+</button>
        </div>
        ${crearExtrasHTML(producto)}
    `;
    
    return card;
}

function crearExtrasHTML(producto) {
    const esSanguche = producto.nombre.toLowerCase().includes('milanesa') || 
                      producto.nombre.toLowerCase().includes('lomito') || 
                      producto.nombre.toLowerCase().includes('hamburguesa');
    
    const esEspecial = producto.nombre.toLowerCase().includes('especial');
    
    if (!esSanguche && !esEspecial) {
        return '';
    }
    
    const itemCarrito = carrito.find(item => item.id === producto.id);
    const showClass = itemCarrito && itemCarrito.cantidad > 0 ? 'show' : '';
    
    const extrasComunes = `
        <div class="extra-item">
            <input type="checkbox" id="lechuga-${producto.id}" value="lechuga" onchange="actualizarExtras('${producto.id}')">
            <label for="lechuga-${producto.id}">Lechuga</label>
        </div>
        <div class="extra-item">
            <input type="checkbox" id="tomate-${producto.id}" value="tomate" onchange="actualizarExtras('${producto.id}')">
            <label for="tomate-${producto.id}">Tomate</label>
        </div>
        <div class="extra-item">
            <input type="checkbox" id="mayonesa-${producto.id}" value="mayonesa" onchange="actualizarExtras('${producto.id}')">
            <label for="mayonesa-${producto.id}">Mayonesa</label>
        </div>
        <div class="extra-item">
            <input type="checkbox" id="savora-${producto.id}" value="savora" onchange="actualizarExtras('${producto.id}')">
            <label for="savora-${producto.id}">Savora</label>
        </div>
        <div class="extra-item">
            <input type="checkbox" id="ketchup-${producto.id}" value="ketchup" onchange="actualizarExtras('${producto.id}')">
            <label for="ketchup-${producto.id}">Ketchup</label>
        </div>
        <div class="extra-item">
            <input type="checkbox" id="aji-${producto.id}" value="ají" onchange="actualizarExtras('${producto.id}')">
            <label for="aji-${producto.id}">Ají</label>
        </div>
    `;
    
    if (esSanguche && !esEspecial) {
        return `
            <div class="extras-section ${showClass}" id="extras-${producto.id}">
                <div class="extras-title">¿Qué lleva?</div>
                <div class="extras-grid">${extrasComunes}</div>
                <textarea class="observaciones-input" id="obs-${producto.id}" placeholder="Observaciones..." rows="2" oninput="actualizarExtras('${producto.id}')"></textarea>
            </div>
        `;
    }
    
    if (esEspecial) {
        return `
            <div class="extras-section ${showClass}" id="extras-${producto.id}">
                <div class="extras-title">Ingredientes Especial</div>
                <div class="extras-grid">
                    <div class="extra-item">
                        <input type="checkbox" id="jamon-${producto.id}" value="jamón" onchange="actualizarExtras('${producto.id}')">
                        <label for="jamon-${producto.id}">Jamón</label>
                    </div>
                    <div class="extra-item">
                        <input type="checkbox" id="queso-${producto.id}" value="queso" onchange="actualizarExtras('${producto.id}')">
                        <label for="queso-${producto.id}">Queso</label>
                    </div>
                    <div class="extra-item">
                        <input type="checkbox" id="huevo-${producto.id}" value="huevo" onchange="actualizarExtras('${producto.id}')">
                        <label for="huevo-${producto.id}">Huevo</label>
                    </div>
                    <div class="extra-item">
                        <input type="checkbox" id="papas-${producto.id}" value="papas" onchange="actualizarExtras('${producto.id}')">
                        <label for="papas-${producto.id}">Papas</label>
                    </div>
                    ${extrasComunes}
                </div>
                <textarea class="observaciones-input" id="obs-${producto.id}" placeholder="Observaciones..." rows="2" oninput="actualizarExtras('${producto.id}')"></textarea>
            </div>
        `;
    }
    
    return '';
}

// ===== FUNCIONES DEL CARRITO =====
function cambiarCantidad(productoId, delta) {
    const producto = productos.find(p => p.id === productoId);
    if (!producto) return;
    
    let itemCarrito = carrito.find(item => item.id === productoId);
    
    if (!itemCarrito) {
        itemCarrito = {
            id: productoId,
            nombre: producto.nombre,
            precio: producto.precio,
            cantidad: 0,
            extras: [],
            observaciones: ''
        };
        carrito.push(itemCarrito);
    }
    
    itemCarrito.cantidad = Math.max(0, itemCarrito.cantidad + delta);
    
    if (itemCarrito.cantidad === 0) {
        carrito = carrito.filter(item => item.id !== productoId);
    }
    
    actualizarUI(productoId);
}

function actualizarExtras(productoId) {
    const itemCarrito = carrito.find(item => item.id === productoId);
    if (!itemCarrito) return;
    
    const extrasSection = document.getElementById(`extras-${productoId}`);
    if (!extrasSection) return;
    
    const checkboxes = extrasSection.querySelectorAll('input[type="checkbox"]:checked');
    itemCarrito.extras = Array.from(checkboxes).map(cb => cb.value);
    
    const obsTextarea = document.getElementById(`obs-${productoId}`);
    if (obsTextarea) {
        itemCarrito.observaciones = obsTextarea.value.trim();
    }
}

function actualizarUI(productoId) {
    const cantidadDisplay = document.getElementById(`cantidad-${productoId}`);
    const itemCarrito = carrito.find(item => item.id === productoId);
    const cantidad = itemCarrito ? itemCarrito.cantidad : 0;
    
    if (cantidadDisplay) {
        cantidadDisplay.textContent = cantidad;
    }
    
    const card = document.getElementById(`producto-${productoId}`);
    if (card) {
        if (cantidad > 0) {
            card.classList.add('selected');
        } else {
            card.classList.remove('selected');
        }
        
        const btnMenos = card.querySelector('.btn-cantidad');
        if (btnMenos) {
            btnMenos.disabled = cantidad === 0;
        }
    }
    
    const extrasSection = document.getElementById(`extras-${productoId}`);
    if (extrasSection) {
        if (cantidad > 0) {
            extrasSection.classList.add('show');
        } else {
            extrasSection.classList.remove('show');
        }
    }
    
    actualizarFooter();
}

function actualizarFooter() {
    const totalItems = carrito.reduce((sum, item) => sum + item.cantidad, 0);
    const totalPrecio = carrito.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
    
    if (totalItems > 0) {
        footerCarrito.style.display = 'block';
        carritoItems.textContent = `${totalItems} ${totalItems === 1 ? 'item' : 'items'}`;
        carritoTotal.textContent = `$${totalPrecio}`;
        btnEnviar.disabled = false;
    } else {
        footerCarrito.style.display = 'none';
        btnEnviar.disabled = true;
    }
}

// ===== ENVIAR PEDIDO =====
async function enviarPedido() {
    if (carrito.length === 0 || !mesaActual) return;
    
    loading.classList.add('show');
    
    try {
        const formData = new FormData();
        
        productos.forEach(producto => {
            const itemCarrito = carrito.find(item => item.id === producto.id);
            const cantidad = itemCarrito ? itemCarrito.cantidad : 0;
            formData.append(`prod_${producto.id}`, cantidad);
            
            if (itemCarrito && cantidad > 0) {
                if (itemCarrito.extras && itemCarrito.extras.length > 0) {
                    formData.append(`extras_${producto.id}`, itemCarrito.extras.join(', '));
                }
                
                if (itemCarrito.observaciones) {
                    formData.append(`obs_${producto.id}`, itemCarrito.observaciones);
                }
            }
        });
        
        const response = await fetch(`${API_URL}/mesa/${mesaActual}`, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            mostrarConfirmacion();
        } else {
            throw new Error('Error al enviar pedido');
        }
        
    } catch (error) {
        console.error('Error:', error);
        alert('Error al enviar el pedido. Por favor, intenta de nuevo.');
    } finally {
        loading.classList.remove('show');
    }
}

function mostrarConfirmacion() {
    const totalPrecio = carrito.reduce((sum, item) => sum + (item.precio * item.cantidad), 0);
    
    modalMesa.textContent = mesaActual;
    modalTotal.textContent = `$${totalPrecio}`;
    modalConfirmacion.classList.add('show');
    
    if ('vibrate' in navigator) {
        navigator.vibrate(200);
    }
}

// ===== UTILIDADES =====
function mostrarVista(vista) {
    viewMesas.classList.remove('active');
    viewProductos.classList.remove('active');
    
    if (vista === 'mesas') {
        viewMesas.classList.add('active');
    } else if (vista === 'productos') {
        viewProductos.classList.add('active');
    }
}

function resetearApp() {
    mesaActual = null;
    carrito = [];
    mesaBadge.style.display = 'none';
    btnVolver.style.display = 'none';
    footerCarrito.style.display = 'none';
    modalConfirmacion.classList.remove('show');
    mostrarVista('mesas');
}

// ===== PREVENIR ZOOM EN DOBLE TAP =====
let lastTouchEnd = 0;
document.addEventListener('touchend', (e) => {
    const now = Date.now();
    if (now - lastTouchEnd <= 300) {
        e.preventDefault();
    }
    lastTouchEnd = now;
}, false);