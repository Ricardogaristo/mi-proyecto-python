from flask import Flask, render_template, request, redirect, session, send_file, url_for
import sqlite3
from functools import wraps
from datetime import datetime

# Para crear Excel bonito
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side

app = Flask(__name__)
app.secret_key = "clave_secreta_muy_segura"
DB_NAME = "tareas.db"

# --- BASE DE DATOS ---

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def inicializar_todo():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Crear/Actualizar tabla USUARIOS (añadimos email y es_admin)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            password TEXT NOT NULL,
            es_admin INTEGER DEFAULT 0
        )
    """)

    # 2. INTENTAR AÑADIR COLUMNAS NUEVAS (por si la tabla ya existía)
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN email TEXT UNIQUE")
    except sqlite3.OperationalError: pass
    
    try:
        cursor.execute("ALTER TABLE usuarios ADD COLUMN es_admin INTEGER DEFAULT 0")
    except sqlite3.OperationalError: pass

    # 3. Crear/Actualizar tabla TAREAS
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            categoria TEXT,
            fecha TEXT,
            completada INTEGER DEFAULT 0,
            codigo TEXT,
            usuario_id INTEGER,
            FOREIGN KEY (usuario_id) REFERENCES usuarios(id)
        )
    """)
    
    try:
        cursor.execute("ALTER TABLE tareas ADD COLUMN usuario_id INTEGER")
    except sqlite3.OperationalError: pass

    # 4. CREAR ADMIN CON EMAIL (Si no existe)
    cursor.execute("SELECT * FROM usuarios WHERE username='admin' OR email='admin@correo.com'")
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO usuarios (username, email, password, es_admin) 
            VALUES (?, ?, ?, ?)""", 
            ("admin", "admin@correo.com", "1234", 1))

    conn.commit()
    conn.close()
    print("✅ Base de datos actualizada: Admin listo con email.")

def actualizar_base_datos():
    conn = get_connection()
    cursor = conn.cursor()

    # Ver columnas actuales
    cursor.execute("PRAGMA table_info(tareas)")
    columnas = [col[1] for col in cursor.fetchall()]

    # Agregar columna usuario si no existe
    if "usuario" not in columnas:
        cursor.execute("ALTER TABLE tareas ADD COLUMN usuario TEXT")
        print("Columna 'usuario' creada correctamente")

    conn.commit()
    conn.close()




# --- PROTECCIÓN DE RUTAS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

# --- RUTAS ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        identificador = request.form.get("username") # Aquí el usuario escribe su email o nick
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor()
        # Buscamos por username O por email
        cursor.execute("""
            SELECT id, username, es_admin FROM usuarios 
            WHERE (username=? OR email=?) AND password=?
        """, (identificador, identificador, password))
        
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            session["user_id"] = usuario["id"]
            session["user"] = usuario["username"]
            session["es_admin"] = usuario["es_admin"]
            return redirect("/")
        
    return render_template("login.html", error="Credenciales incorrectas")



@app.route("/registro", methods=["GET", "POST"])
def registro():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor()
        
        try:
            # Insertamos el nuevo usuario. El campo es_admin siempre es 0 para nuevos.
            cursor.execute("""
                INSERT INTO usuarios (username, email, password, es_admin) 
                VALUES (?, ?, ?, 0)
            """, (username, email, password))
            conn.commit()
            conn.close()
            # Al terminar, lo mandamos al login para que entre
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            # Esto ocurre si el username o email ya existen (son UNIQUE)
            conn.close()
            return render_template("registro.html", error="El usuario o email ya existe ❌")
            
    return render_template("registro.html")

@app.route("/")
@login_required
def index():
    user_id = session.get("user_id")
    es_admin = session.get("es_admin")
    
    # Manejo de paginación
    page = request.args.get('page', 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    conn = get_connection()
    cursor = conn.cursor()

    if es_admin == 1:
        # VISTA ADMIN: Ve todas las tareas
        cursor.execute("SELECT * FROM tareas ORDER BY id DESC LIMIT ? OFFSET ?", (per_page, offset))
        tareas = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM tareas")
        total_tareas = cursor.fetchone()[0]
    else:
        # VISTA USUARIO: Ve solo las suyas
        cursor.execute("SELECT * FROM tareas WHERE usuario_id = ? ORDER BY id DESC LIMIT ? OFFSET ?", (user_id, per_page, offset))
        tareas = cursor.fetchall()
        cursor.execute("SELECT COUNT(*) FROM tareas WHERE usuario_id = ?", (user_id,))
        total_tareas = cursor.fetchone()[0]
    
    conn.close()

    # Cálculo para evitar el error de Jinja2
    total_pages = (total_tareas + per_page - 1) // per_page if total_tareas > 0 else 1

    return render_template("index.html", 
                           tareas=tareas, 
                           page=page, 
                           total_pages=total_pages)

@app.route("/agregar", methods=["POST"])
@login_required
def agregar():

    codigo = request.form.get("codigo")
    descripcion = request.form.get("descripcion")
    categoria = request.form.get("categoria")
    fecha = request.form.get("fecha")

    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO tareas (codigo, descripcion, categoria, fecha, completada, usuario_id)
        VALUES (?, ?, ?, ?, 0, ?)
    """, (codigo, descripcion, categoria, fecha, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/")


@app.route("/admin")
@login_required
def admin():

    # ==============================
    # Validación segura de admin
    # ==============================
    if session.get("es_admin") != 1:
        return redirect("/")

    # ==============================
    # Parámetros de filtros
    # ==============================
    filtro_cat = request.args.get("categoria", "").strip()
    filtro_est = request.args.get("estado", "").strip()
    page = request.args.get("page", 1, type=int)

    if page < 1:
        page = 1

    per_page = 10

    # ==============================
    # Construcción dinámica del WHERE
    # ==============================
    filtros = []
    params = []

    if filtro_cat:
        filtros.append("LOWER(TRIM(categoria)) = LOWER(TRIM(?))")
        params.append(filtro_cat)

    if filtro_est == "Completada":
        filtros.append("completada = 1")
    elif filtro_est == "Pendiente":
        filtros.append("completada = 0")

    where_clause = ""
    if filtros:
        where_clause = "WHERE " + " AND ".join(filtros)

    # ==============================
    # Conexión segura (context manager)
    # ==============================
    with get_connection() as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # ------------------------------
        # Conteo total filtrado
        # ------------------------------
        cursor.execute(
            f"SELECT COUNT(*) FROM tareas {where_clause}",
            params
        )
        total_filtrado = cursor.fetchone()[0]

        total_pages = max((total_filtrado + per_page - 1) // per_page, 1)

        if page > total_pages:
            page = total_pages

        offset = (page - 1) * per_page

        # ------------------------------
        # Obtener tareas paginadas
        # ------------------------------
        cursor.execute(
            f"""
            SELECT id, descripcion, categoria, fecha,
                   completada, codigo, usuario_id
            FROM tareas
            {where_clause}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset]
        )

        tareas = cursor.fetchall()

        # ------------------------------
        # Obtener categorías
        # ------------------------------
        cursor.execute("""
            SELECT DISTINCT categoria
            FROM tareas
            WHERE categoria IS NOT NULL AND categoria != ''
            ORDER BY categoria
        """)
        categorias_lista = [row[0] for row in cursor.fetchall()]

    # ==============================
    # Renderizado
    # ==============================
    return render_template(
        "admin.html",
        tareas=tareas,
        page=page,
        total_pages=total_pages,
        total=total_filtrado,
        categorias=categorias_lista,
        filtro_cat=filtro_cat,
        filtro_est=filtro_est
    )






@app.route("/completar/<int:id>")
@login_required
def completar(id):
    conn = get_connection()
    cursor = conn.cursor()

    # Si es admin, puede completar cualquier tarea
    if session.get("es_admin") == 1:
        cursor.execute("UPDATE tareas SET completada=1 WHERE id=?", (id,))
    else:
        # Usuario solo puede completar sus propias tareas
        cursor.execute("UPDATE tareas SET completada=1 WHERE id=? AND usuario_id=?", (id, session["user_id"]))

    conn.commit()
    conn.close()

    return redirect("/")

@app.route("/eliminar/<int:id>")
@login_required
def eliminar(id):

    conn = get_connection()
    cursor = conn.cursor()

    if session["es_admin"] == 1:
        cursor.execute("DELETE FROM tareas WHERE id=?", (id,))
    else:
        cursor.execute(
            "DELETE FROM tareas WHERE id=? AND usuario_id=?",
            (id, session["user_id"])
        )

    conn.commit()
    conn.close()

    return redirect("/")




# -----------------------------
# Página dashboard
# -----------------------------
@app.route("/dashboard")
@login_required
def dashboard():
    user_id = session.get("user_id")
    es_admin = session.get("es_admin")
    
    conn = get_connection()
    cursor = conn.cursor()

    # --- LÓGICA DE FILTRADO POR ROL ---
    if es_admin == 1:
        # Estadísticas Globales para el Admin
        cursor.execute("SELECT COUNT(*) as total FROM tareas")
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as completadas FROM tareas WHERE completada = 1")
        completadas = cursor.fetchone()["completadas"]
        
        # Opcional: Obtener las últimas 5 tareas de cualquier usuario para el admin
        cursor.execute("SELECT * FROM tareas ORDER BY id DESC LIMIT 5")
        ultimas_tareas = cursor.fetchall()
    else:
        # Estadísticas Personales para el Usuario
        cursor.execute("SELECT COUNT(*) as total FROM tareas WHERE usuario_id = ?", (user_id,))
        total = cursor.fetchone()["total"]

        cursor.execute("SELECT COUNT(*) as completadas FROM tareas WHERE completada = 1 AND usuario_id = ?", (user_id,))
        completadas = cursor.fetchone()["completadas"]
        
        # Últimas 5 tareas solo del usuario actual
        cursor.execute("SELECT * FROM tareas WHERE usuario_id = ? ORDER BY id DESC LIMIT 5", (user_id,))
        ultimas_tareas = cursor.fetchall()

    # --- CÁLCULOS DE PROGRESO ---
    pendientes = total - completadas
    porcentaje = round((completadas / total) * 100, 1) if total > 0 else 0

    if porcentaje > 70:
        nivel, color_nivel = "Alto", "success"
    elif porcentaje > 40:
        nivel, color_nivel = "Medio", "warning"
    else:
        nivel, color_nivel = "Bajo", "danger"

    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    conn.close()

    return render_template("dashboard.html", 
                           total=total, 
                           completadas=completadas,
                           pendientes=pendientes, 
                           porcentaje=porcentaje,
                           nivel=nivel, 
                           color_nivel=color_nivel,
                           fecha_actual=fecha_actual,
                           ultimas_tareas=ultimas_tareas)



from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from flask import send_file

# ---------------------------------------------------------
# EXPORTAR EXCEL: HISTORIAL + TAREAS DEL DÍA
# ---------------------------------------------------------
@app.route("/exportar")
@login_required
def exportar():
    hoy = datetime.now().strftime("%Y-%m-%d") # Ajusta el formato si usas DD/MM/YYYY
    user_id = session.get("user_id")
    es_admin = session.get("es_admin")
    
    conn = get_connection()
    cursor = conn.cursor()

    # 1. Obtener Historial Completo
    if es_admin == 1:
        cursor.execute("""
            SELECT t.*, u.username FROM tareas t 
            LEFT JOIN usuarios u ON t.usuario_id = u.id ORDER BY t.id
        """)
        historial = cursor.fetchall()
        
        # 2. Obtener Tareas de Hoy
        cursor.execute("""
            SELECT t.*, u.username FROM tareas t 
            LEFT JOIN usuarios u ON t.usuario_id = u.id 
            WHERE t.fecha = ? ORDER BY t.id
        """, (hoy,))
        tareas_hoy = cursor.fetchall()
    else:
        cursor.execute("""
            SELECT t.*, u.username FROM tareas t 
            LEFT JOIN usuarios u ON t.usuario_id = u.id 
            WHERE t.usuario_id = ? ORDER BY t.id
        """, (user_id,))
        historial = cursor.fetchall()

        cursor.execute("""
            SELECT t.*, u.username FROM tareas t 
            LEFT JOIN usuarios u ON t.usuario_id = u.id 
            WHERE t.usuario_id = ? AND t.fecha = ? ORDER BY t.id
        """, (user_id, hoy))
        tareas_hoy = cursor.fetchall()

    conn.close()

    # --- Configuración del Libro ---
    wb = Workbook()
    
    # Estilos comunes
    header_fill = PatternFill(start_color="343A40", end_color="343A40", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))
    center_align = Alignment(horizontal="center", vertical="center")

    # Función auxiliar para llenar hojas y no repetir código
    def llenar_hoja(sheet, datos, titulo):
        sheet.title = titulo
        headers = ["ID", "Código", "Descripción", "Categoría", "Fecha", "Estado", "Usuario"]
        sheet.append(headers)
        
        for col in range(1, len(headers) + 1):
            cell = sheet.cell(row=1, column=col)
            cell.fill, cell.font, cell.alignment, cell.border = header_fill, header_font, center_align, thin_border

        for fila_num, t in enumerate(datos, start=2):
            est_txt = "Completada" if t["completada"] == 1 else "Pendiente"
            row = [t["id"], t["codigo"] or "", t["descripcion"], t["categoria"] or "General", 
                   t["fecha"] or "-", est_txt, t["username"] or "N/A"]
            
            for col_num, value in enumerate(row, start=1):
                cell = sheet.cell(row=fila_num, column=col_num, value=value)
                cell.border, cell.alignment = thin_border, center_align
                if col_num == 6: # Colorear estado
                    color = "28A745" if est_txt == "Completada" else "FFC107"
                    cell.fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            
        # Ajustar ancho
        for col in sheet.columns:
            max_l = max(len(str(c.value)) for c in col)
            sheet.column_dimensions[col[0].column_letter].width = max_l + 4

    # --- Crear Hoja 1: Historial ---
    ws1 = wb.active
    llenar_hoja(ws1, historial, "Historial Completo")

    # --- Crear Hoja 2: Hoy ---
    ws2 = wb.create_sheet(title="Tareas de Hoy")
    llenar_hoja(ws2, tareas_hoy, f"Hoy {hoy}")

    archivo = f"Reporte_Tareas_{hoy}.xlsx"
    wb.save(archivo)
    return send_file(archivo, as_attachment=True)




# -----------------------------
# EDITAR
# -----------------------------


@app.route("/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar(id):
    conn = get_connection()
    cursor = conn.cursor()

    if request.method == "POST":
        codigo = request.form.get("codigo")
        descripcion = request.form.get("descripcion")
        categoria = request.form.get("categoria")
        fecha = request.form.get("fecha")
        completada = request.form.get("completada")  # 👈 NUEVO

        cursor.execute("""
            UPDATE tareas
            SET codigo=?, descripcion=?, categoria=?, fecha=?, completada=?
            WHERE id=?
        """, (codigo, descripcion, categoria, fecha, completada, id))

        conn.commit()
        conn.close()
        return redirect("/")

    else:
        cursor.execute("SELECT * FROM tareas WHERE id=?", (id,))
        tarea = cursor.fetchone()
        conn.close()
        return render_template("editar.html", tarea=tarea)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))



# --- ARRANCAR ---
if __name__ == "__main__":
    inicializar_todo()
    app.run(debug=True, port=5000)