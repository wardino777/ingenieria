import os
import sys
import time
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import logging

# Intentar importar pymysql, de lo contrario instalarlo automáticamente en la máquina local
try:
    import pymysql
except ImportError:
    print("Instalando la librería pymysql de forma automática...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "pymysql"], check=True)
    import pymysql

# Configuración por defecto de MySQL en XAMPP local
MYSQL_HOST = "127.0.0.1"
MYSQL_USER = "root"
MYSQL_PASSWORD = ""  # Por defecto en XAMPP, la contraseña del root está vacía

# OBTENER LA RUTA ABSOLUTA DE LA CARPETA DONDE ESTÁ ESTE ARCHIVO (Admins)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_db_connection(database=None):
    """
    Establece una conexión directa con el motor de MySQL de tu XAMPP local.
    Intenta conectarse usando las credenciales por defecto de XAMPP (root sin contraseña)
    y, en caso de fallar, utiliza las credenciales del usuario administrativo creado ('admin').
    """
    credenciales_a_probar = [
        {"user": "root", "password": ""},
        {"user": "admin", "password": "adminmaipu"}
    ]
    
    last_exception = None
    for cred in credenciales_a_probar:
        try:
            conn_args = {
                'host': MYSQL_HOST,
                'user': cred["user"],
                'password': cred["password"],
                'autocommit': True,
                'charset': 'utf8mb4'
            }
            if database:
                conn_args['database'] = database
            return pymysql.connect(**conn_args)
        except Exception as e:
            last_exception = e
            
    # Si ambas combinaciones fallan, muestra el mensaje de error explicativo
    print(f"\n❌ ERROR DE CONEXIÓN CON XAMPP:")
    print("Asegúrate de tener abierto el panel de XAMPP y que el módulo 'MySQL' esté encendido (en verde).")
    print(f"Detalle del error: {last_exception}\n")
    sys.exit(1)

def inicializar_base_de_datos():
    """
    Crea la base de datos 'central_maipu' y sus tablas relacionales en tu MySQL local.
    Puebla datos semilla realistas de Maipú si el sistema está vacío.
    """
    print("=== [1/2] Verificando e Inicializando Base de Datos Local ===")
    
    # 1. Crear base de datos si no existe
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("CREATE DATABASE IF NOT EXISTS central_maipu;")
    cursor.execute("USE central_maipu;")
    
    # 2. Creación de las Tablas Relacionales (con columnas adicionales para el portal de vecinos)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS operadores (
            id INT AUTO_INCREMENT PRIMARY KEY,
            nombre VARCHAR(100) NOT NULL UNIQUE,
            password VARCHAR(255) NULL, -- NUEVA COLUMNA PARA LA CONTRASEÑA
            rango VARCHAR(50) DEFAULT 'Inspector',
            primer_acceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)

    # Verificar si la columna password existe en operadores (migración)
    cursor.execute("DESCRIBE operadores;")
    columnas_operadores = [col[0] for col in cursor.fetchall()]
    if 'password' not in columnas_operadores:
        print("Actualizando tabla 'operadores' con campo de contraseña...")
        cursor.execute("ALTER TABLE operadores ADD COLUMN password VARCHAR(255) NULL AFTER nombre;")
        # Asignar una contraseña por defecto a los existentes para no romper nada
        cursor.execute("UPDATE operadores SET password = '123' WHERE password IS NULL;")
        print("✅ Columna password añadida.")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS totems (
            id INT AUTO_INCREMENT PRIMARY KEY,
            codigo VARCHAR(10) NOT NULL UNIQUE,
            nombre VARCHAR(100) NOT NULL,
            coor_top INT NOT NULL,
            coor_left INT NOT NULL,
            capacidad_max INT DEFAULT 20,
            estado_sistema VARCHAR(20) DEFAULT 'Disponible'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    
    # Creamos la tabla de donaciones
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS donaciones (
            id INT AUTO_INCREMENT PRIMARY KEY,
            codigo_ticket VARCHAR(20) NULL,
            usuario_email VARCHAR(100) DEFAULT 'vecino.demo@maipu.cl',
            totem_id INT NOT NULL,
            categoria VARCHAR(50) NOT NULL,
            subcategoria VARCHAR(100) NOT NULL,
            descripcion TEXT,
            estado_conservacion VARCHAR(50) DEFAULT 'Nuevo',
            tipo_empaque VARCHAR(50) DEFAULT 'Bolsa',
            fecha_vencimiento VARCHAR(50) DEFAULT 'No perecible',
            estado VARCHAR(30) DEFAULT 'En Tótem', -- 'En Tótem', 'En Ruta', 'En Bodega'
            fecha_ingreso TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (totem_id) REFERENCES totems(id) ON DELETE CASCADE
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    
    # EJECUTAR COMPROBACIÓN DE COLUMNAS (MIGRACIÓN DINÁMICA)
    cursor.execute("DESCRIBE donaciones;")
    columnas_existentes = [col[0] for col in cursor.fetchall()]
    
    if 'codigo_ticket' not in columnas_existentes:
        print("Actualizando tabla 'donaciones' con campos de trazabilidad vecinal...")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN codigo_ticket VARCHAR(20) NULL AFTER id;")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN usuario_email VARCHAR(100) DEFAULT 'vecino.demo@maipu.cl' AFTER codigo_ticket;")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN estado_conservacion VARCHAR(50) DEFAULT 'Nuevo' AFTER descripcion;")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN tipo_empaque VARCHAR(50) DEFAULT 'Bolsa' AFTER estado_conservacion;")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN fecha_vencimiento VARCHAR(50) DEFAULT 'No perecible' AFTER tipo_empaque;")

    # Agregando columnas para las fotos y validaciones
    if 'imagen_base64' not in columnas_existentes:
        print("Añadiendo columna para fotografías...")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN imagen_base64 LONGTEXT AFTER fecha_vencimiento;")
        
    if 'val_status' not in columnas_existentes:
        print("Añadiendo columnas de validación...")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN val_status VARCHAR(50) DEFAULT 'Pendiente' AFTER imagen_base64;")
        cursor.execute("ALTER TABLE donaciones ADD COLUMN motivo TEXT AFTER val_status;")
        print("✅ Base de datos actualizada con sistema de cámara y validación.")

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alertas (
            id INT AUTO_INCREMENT PRIMARY KEY,
            prioridad VARCHAR(20) NOT NULL,
            mensaje VARCHAR(255) NOT NULL,
            ubicacion VARCHAR(100) NOT NULL,
            estado VARCHAR(20) DEFAULT 'En curso',
            fecha_alerta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS viajes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            totem_id INT NOT NULL,
            operador_id INT,
            estado VARCHAR(30) DEFAULT 'Vehículo en Ruta',
            tiempo_estimado_seg INT DEFAULT 300,
            total_insumos INT DEFAULT 0,
            fecha_inicio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (totem_id) REFERENCES totems(id),
            FOREIGN KEY (operador_id) REFERENCES operadores(id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS bitacora (
            id INT AUTO_INCREMENT PRIMARY KEY,
            tipo_suceso VARCHAR(50) NOT NULL,
            descripcion TEXT NOT NULL,
            responsable VARCHAR(100) NOT NULL,
            fecha_suceso TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
    """)
    
    # 3. Poblado de Datos Semilla (Seeders) solo si la tabla totems está vacía
    cursor.execute("SELECT COUNT(*) FROM totems;")
    if cursor.fetchone()[0] == 0:
        print("Poblando base de datos local con datos semilla...")
        
        # Operadores
        operadores_data = [
            ("Constanza Silva", "123", "Inspector Operador"),
            ("Andrés Tobar", "123", "Inspector Operador"),
            ("Sistema Autónomo", "123", "Central Inteligente"),
            ("Benyamin", "admin123", "Jefe de Sección")
        ]
        cursor.executemany("INSERT IGNORE INTO operadores (nombre, password, rango) VALUES (%s, %s, %s);", operadores_data)
        
        # Tótems de Maipú
        totems_data = [
            ("P-01", "P-01 Plaza Maipú", 25, 30, 20, "Disponible"),
            ("B-02", "B-02 Santiago Bueras", 45, 35, 20, "Disponible"),
            ("M-01", "M-01 Mall Arauco", 35, 75, 20, "Disponible"),
            ("I-03", "I-03 Intermodal", 15, 45, 20, "Disponible"),
            ("S-05", "S-05 Satélite", 85, 15, 20, "Disponible"),
            ("A-06", "A-06 El Abrazo", 75, 25, 20, "Disponible"),
            ("H-07", "H-07 Hospital", 55, 55, 20, "Disponible"),
            ("T-08", "T-08 Templo Votivo", 50, 42, 20, "Disponible"),
            ("P-09", "P-09 Tres Poniente", 65, 20, 20, "Disponible"),
            ("MT-10", "MT-10 Monte Tabor", 22, 65, 20, "Disponible"),
            ("LP-11", "LP-11 Las Parcelas", 18, 72, 20, "Disponible"),
            ("DS-12", "DS-12 Del Sol", 28, 58, 20, "Mantenimiento"),
            ("R-13", "R-13 Rinconada", 60, 10, 20, "Disponible"),
            ("V-14", "V-14 Los Héroes", 72, 38, 20, "Disponible"),
            ("MM-15", "MM-15 Mid Mall", 90, 40, 20, "Disponible"),
            ("PJ-16", "PJ-16 Pehuén", 10, 55, 20, "Disponible"),
            ("LI-17", "LI-17 Industrias", 40, 85, 20, "Disponible")
        ]
        cursor.executemany("""
            INSERT INTO totems (codigo, nombre, coor_top, coor_left, capacidad_max, estado_sistema) 
            VALUES (%s, %s, %s, %s, %s, %s);
        """, totems_data)
        
        # Donaciones de prueba
        donaciones_data = [
            (1, "Alimentos", "Arroz y Conservas", "Pack de alimentos no perecibles de 5kg", "En Tótem"),
            (1, "Ropa Invierno", "Abrigo de Invierno", "Chaqueta gruesa térmica de adulto", "En Tótem"),
            (7, "Higiene", "Kit Higiénico", "Caja con jabón, cepillos de dientes y toallitas", "En Tótem")
        ]
        cursor.executemany("""
            INSERT INTO donaciones (totem_id, categoria, subcategoria, descripcion, estado) 
            VALUES (%s, %s, %s, %s, %s);
        """, donaciones_data)
        
        # Alertas críticas
        alertas_data = [
            ("CRÍTICO", "Botón de pánico presionado por disturbio público", "Plaza Maipú", "En curso"),
            ("SALUD", "Adulto mayor descompensado requiere asistencia médica", "Hospital El Carmen", "En curso")
        ]
        cursor.executemany("INSERT INTO alertas (prioridad, mensaje, ubicacion, estado) VALUES (%s, %s, %s, %s);", alertas_data)
        
        # Bitácora
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('REGISTRO', 'Base de datos de MySQL local inicializada correctamente en XAMPP', 'Sistema Autónomo');
        """)
        
        print("✅ Base de datos poblada de forma exitosa.")
    else:
        print("La base de datos local ya cuenta con registros existentes. Conservando datos.")
        
    conn.close()

# =====================================================================
# CONFIGURACIÓN DEL BACKEND API (FLASK)
# =====================================================================
app = Flask("MaipuBackendLocal")
CORS(app)

# Silenciar mensajes de consola HTTP innecesarios para un entorno limpio
log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

@app.route('/')
def serve_index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/index.html')
def serve_index_html():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/portal')
def serve_portal():
    return send_from_directory(BASE_DIR, 'portal.html')

@app.route('/portal.html')
def serve_portal_html():
    return send_from_directory(BASE_DIR, 'portal.html')

@app.route('/terminal')
def serve_terminal():
    """ Sirve la interfaz del Terminal de Asistencia Pro (Tótem físico). """
    return send_from_directory(BASE_DIR, 'terminal.html')

@app.route('/terminal.html')
def serve_terminal_html():
    return send_from_directory(BASE_DIR, 'terminal.html')

@app.route('/api/users/login', methods=['POST'])
def api_login():
    """
    Maneja el inicio de sesión. Si el usuario existe, verifica la contraseña.
    Si no existe, lo crea con la contraseña proporcionada y le asigna un rol.
    """
    data = request.json or {}
    name = data.get('name', '').strip()
    password = data.get('password', '').strip()
    
    if not name or not password:
        return jsonify({'status': 'error', 'message': 'Faltan credenciales'}), 400
        
    # Asignación automática de roles
    # Si es Benyamin, es Jefe de Sección, si no, es Inspector normal (a menos que ya exista)
    rank_to_assign = 'Jefe de Sección' if name.lower() == 'benyamin' else 'Inspector'
    
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        # Verificar si el usuario ya existe
        cursor.execute("SELECT id, password, rango FROM operadores WHERE nombre = %s;", (name,))
        user_record = cursor.fetchone()
        
        if user_record:
            # El usuario existe, verificamos la contraseña
            db_password = user_record[1]
            actual_rank = user_record[2]
            
            # Nota: para los vecinos que ingresan por el portal, su password es 'vecino'
            if db_password != password and password != 'vecino':
                return jsonify({'status': 'error', 'message': 'Contraseña incorrecta.'}), 401
                
            final_rank = actual_rank
        else:
            # El usuario no existe, lo creamos y guardamos su nueva contraseña
            # (En un sistema real la contraseña debería ir hasheada)
            cursor.execute("""
                INSERT INTO operadores (nombre, password, rango) VALUES (%s, %s, %s);
            """, (name, password, rank_to_assign))
            final_rank = rank_to_assign
        
        # Registrar en la bitácora (excepto para los vecinos del portal para no saturar)
        if password != 'vecino':
            cursor.execute("""
                INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
                VALUES ('SESIÓN', %s, %s);
            """, (f"Usuario {name} ({final_rank}) inició sesión en el portal central", name))
            
        return jsonify({'status': 'success', 'user': {'name': name, 'rank': final_rank}})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/donations/ticket/<ticket_id>', methods=['GET'])
def api_get_ticket_status(ticket_id):
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT val_status, motivo FROM donaciones WHERE codigo_ticket = %s LIMIT 1;", (ticket_id,))
        result = cursor.fetchone()
        if result:
            return jsonify({'status': 'success', 'val_status': result[0], 'motivo': result[1]})
        return jsonify({'status': 'error', 'message': 'Ticket no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/totems', methods=['GET'])
def api_get_totems():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT t.id, t.codigo, t.nombre, t.coor_top as t, t.coor_left as l, t.capacidad_max, t.estado_sistema,
                   COUNT(CASE WHEN d.estado = 'En Tótem' THEN d.id END) as itemsCount
            FROM totems t
            LEFT JOIN donaciones d ON t.id = d.totem_id
            GROUP BY t.id;
        """)
        columns = [desc[0] for desc in cursor.description]
        totems = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(totems)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/alerts', methods=['GET'])
def api_get_alerts():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT id, prioridad as prio, mensaje as msg, ubicacion as loc, estado,
                   DATE_FORMAT(fecha_alerta, '%Y-%m-%d %H:%i:%s') as fecha
            FROM alertas 
            WHERE estado = 'En curso' 
            ORDER BY fecha_alerta DESC;
        """)
        columns = [desc[0] for desc in cursor.description]
        alerts = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(alerts)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/alerts/resolve', methods=['POST'])
def api_resolve_alert():
    data = request.json or {}
    alert_id = data.get('id')
    user = data.get('user', 'Sistema')
    if not alert_id:
        return jsonify({'error': 'ID faltante'}), 400
        
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT prioridad, ubicacion FROM alertas WHERE id = %s;", (alert_id,))
        alert_info = cursor.fetchone()
        if alert_info:
            prio, loc = alert_info
            cursor.execute("UPDATE alertas SET estado = 'Solucionado' WHERE id = %s;", (alert_id,))
            cursor.execute("""
                INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
                VALUES ('ALERTA', %s, %s);
            """, (f"Incidente {prio} en {loc} resuelto por operador", user))
            return jsonify({'status': 'success'})
        return jsonify({'error': 'Alerta no encontrada'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/alerts/create', methods=['POST'])
def api_create_alert():
    data = request.json or {}
    prio = data.get('prioridad')
    msg = data.get('mensaje')
    loc = data.get('ubicacion')
    user = data.get('user', 'Simulador')
    
    if not all([prio, msg, loc]):
        return jsonify({'error': 'Campos faltantes'}), 400
        
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO alertas (prioridad, mensaje, ubicacion, estado)
            VALUES (%s, %s, %s, 'En curso');
        """, (prio, msg, loc))
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('ALERTA', %s, %s);
        """, (f"Nueva alerta {prio} en {loc}: {msg}", user))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/donations', methods=['GET'])
def api_get_donations():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.id, d.totem_id, t.nombre as totem, d.categoria as cat, d.subcategoria as sub, d.descripcion as `desc`, d.estado, d.imagen_base64, d.val_status, d.motivo,
                   DATE_FORMAT(d.fecha_ingreso, '%Y-%m-%d %H:%i:%s') as fecha
            FROM donaciones d
            JOIN totems t ON d.totem_id = t.id
            WHERE d.estado != 'En Bodega'
            ORDER BY d.fecha_ingreso DESC;
        """)
        columns = [desc[0] for desc in cursor.description]
        donations = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(donations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/donations/create', methods=['POST'])
def api_create_donation():
    data = request.json or {}
    totem_id = data.get('totem_id')
    cat = data.get('categoria')
    sub = data.get('subcategoria')
    desc = data.get('descripcion', '')
    user = data.get('user', 'Ciudadano')
    
    codigo_ticket = data.get('codigo_ticket', None)
    estado_conservacion = data.get('estado_conservacion', 'Nuevo')
    tipo_empaque = data.get('tipo_empaque', 'Bolsa')
    fecha_vencimiento = data.get('fecha_vencimiento', 'No perecible')
    imagen_base64 = data.get('imagen_base64', None)
    
    if not all([totem_id, cat, sub]):
        return jsonify({'error': 'Campos faltantes'}), 400
        
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO donaciones (totem_id, categoria, subcategoria, descripcion, estado, usuario_email, codigo_ticket, estado_conservacion, tipo_empaque, fecha_vencimiento, imagen_base64)
            VALUES (%s, %s, %s, %s, 'En Tótem', %s, %s, %s, %s, %s, %s);
        """, (totem_id, cat, sub, desc, user, codigo_ticket, estado_conservacion, tipo_empaque, fecha_vencimiento, imagen_base64))
        
        cursor.execute("SELECT nombre FROM totems WHERE id = %s;", (totem_id,))
        t_name = cursor.fetchone()[0]
        
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('DONACIÓN', %s, %s);
        """, (f"Nuevo insumo {cat} ({sub}) depositado en {t_name}", user))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/donations/validate', methods=['POST'])
def api_validate_donation():
    data = request.json or {}
    d_id = data.get('id')
    status = data.get('status')
    motivo = data.get('motivo', '')
    operator = data.get('operator', 'Inspector')

    if not d_id or not status:
        return jsonify({'error': 'Faltan datos'}), 400

    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE donaciones SET val_status = %s, motivo = %s WHERE id = %s;", (status, motivo, d_id))
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('VALIDACIÓN', %s, %s);
        """, (f"Insumo #{d_id} evaluado: {status.upper()}", operator))
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/donations/history/<email>', methods=['GET'])
def api_get_user_history(email):
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.codigo_ticket as id, d.usuario_email as user, 
                   DATE_FORMAT(d.fecha_ingreso, '%d/%m/%Y, %H:%i:%s') as fecha,
                   t.nombre as totem, d.categoria as cat, d.subcategoria as sub, 
                   d.descripcion as `desc`, d.estado_conservacion as estado, 
                   d.tipo_empaque as empaque, d.fecha_vencimiento as venc, d.estado as status,
                   d.val_status, d.motivo
            FROM donaciones d
            JOIN totems t ON d.totem_id = t.id
            WHERE d.usuario_email = %s
            ORDER BY d.id DESC;
        """, (email,))
        columns = [desc[0] for desc in cursor.description]
        logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/trips/start', methods=['POST'])
def api_start_trip():
    data = request.json or {}
    totem_id = data.get('totem_id')
    operator = data.get('operator', 'Sistema')
    
    if not totem_id:
        return jsonify({'error': 'Tótem ID requerido'}), 400
        
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nombre FROM totems WHERE id = %s;", (totem_id,))
        totem_info = cursor.fetchone()
        if not totem_info:
            return jsonify({'error': 'Tótem no encontrado'}), 404
        totem_name = totem_info[0]
        
        cursor.execute("SELECT id FROM donaciones WHERE totem_id = %s AND estado = 'En Tótem';", (totem_id,))
        items = cursor.fetchall()
        item_ids = [item[0] for item in items]
        
        cursor.execute("""
            INSERT INTO viajes (totem_id, operador_id, estado, total_insumos)
            VALUES (%s, (SELECT id FROM operadores WHERE nombre = %s LIMIT 1), 'Vehículo en Ruta', %s);
        """, (totem_id, operator, len(item_ids)))
        
        if item_ids:
            format_strings = ','.join(['%s'] * len(item_ids))
            cursor.execute(f"UPDATE donaciones SET estado = 'En Ruta' WHERE id IN ({format_strings});", tuple(item_ids))
            
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('LOGÍSTICA', %s, %s);
        """, (f"Recolección iniciada en {totem_name} ({len(item_ids)} insumos)", operator))
        
        return jsonify({'status': 'success', 'itemsCount': len(item_ids)})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/trips/confirm', methods=['POST'])
def api_confirm_trip():
    data = request.json or {}
    totem_id = data.get('totem_id')
    operator = data.get('operator', 'Sistema')
    
    if not totem_id:
        return jsonify({'error': 'Tótem ID requerido'}), 400
        
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT nombre FROM totems WHERE id = %s;", (totem_id,))
        totem_name = cursor.fetchone()[0]
        
        cursor.execute("""
            UPDATE donaciones SET estado = 'En Bodega' 
            WHERE totem_id = %s AND estado = 'En Ruta';
        """, (totem_id,))
        
        cursor.execute("""
            UPDATE viajes SET estado = 'Entregado' 
            WHERE totem_id = %s AND estado = 'Vehículo en Ruta';
        """, (totem_id,))
        
        cursor.execute("""
            INSERT INTO bitacora (tipo_suceso, descripcion, responsable)
            VALUES ('LOGÍSTICA', %s, %s);
        """, (f"Carga de {totem_name} ingresada a bodega central", operator))
        
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/inventory', methods=['GET'])
def api_get_inventory():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT d.id, d.categoria as cat, d.subcategoria as sub, d.descripcion as `desc`, t.nombre as totem, d.imagen_base64
            FROM donaciones d
            JOIN totems t ON d.totem_id = t.id
            WHERE d.estado = 'En Bodega'
            ORDER BY d.id DESC;
        """)
        columns = [desc[0] for desc in cursor.description]
        inv = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(inv)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/history', methods=['GET'])
def api_get_history():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT tipo_suceso as type, descripcion as msg, responsable as user,
                   DATE_FORMAT(fecha_suceso, '%d/%m/%Y, %H:%i:%s') as time
            FROM bitacora 
            ORDER BY id DESC;
        """)
        columns = [desc[0] for desc in cursor.description]
        logs = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(logs)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/history/clear', methods=['POST'])
def api_clear_history():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("TRUNCATE TABLE bitacora;")
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/api/users', methods=['GET'])
def api_get_users():
    conn = get_db_connection(database='central_maipu')
    cursor = conn.cursor()
    try:
        cursor.execute("""
            SELECT nombre as name, rango as rank,
                   DATE_FORMAT(primer_acceso, '%d/%m/%Y, %H:%i:%s') as date
            FROM operadores 
            ORDER BY primer_acceso DESC;
        """)
        columns = [desc[0] for desc in cursor.description]
        users = [dict(zip(columns, row)) for row in cursor.fetchall()]
        return jsonify(users)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

if __name__ == "__main__":
    # Inicializa las tablas relacionales y carga los datos de prueba locales
    inicializar_base_de_datos()
    
    # Levanta el servidor backend local
    print("\n=== [2/2] Iniciando Servidor API local ===")
    print("👉 Servidor escuchando en: http://127.0.0.1:5000")
    print("👉 Portal de inspectores: http://127.0.0.1:5000/")
    print("👉 Portal de vecinos solidarios: http://127.0.0.1:5000/portal")
    print("👉 Terminal de Asistencia (Tótem): http://127.0.0.1:5000/terminal")
    print("Para apagar el servidor presiona Ctrl + C en tu terminal de VS Code.\n")
    
    app.run(port=5000, host='127.0.0.1', debug=True, use_reloader=False)