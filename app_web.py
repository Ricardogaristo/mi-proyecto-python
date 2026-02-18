from flask import Flask, render_template, request, redirect, session, send_file
import sqlite3
from functools import wraps
from datetime import datetime

app = Flask(__name__)
app.secret_key = "clave_secreta"
DB_NAME = "tareas.db"

# -----------------------------
# BASE DE DATOS
# -----------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def crear_tablas_y_admin():
    conn = get_connection()
    cursor = conn.cursor()

    # Crear tabla tareas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            categoria TEXT,
            fecha TEXT,
            completada INTEGER DEFAULT 0
        )
    """)
    # Agregar columna 'codigo' si no existe
    try:
        cursor.execute("ALTER TABLE tareas ADD COLUMN codigo TEXT")
    except sqlite3.OperationalError:
        pass  # la columna ya existe
    # Crear tabla usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    # Crear admin si no existe
    cursor.execute("SELECT * FROM usuarios WHERE username='admin'")
    if not cursor.fetchone():
        cursor.execute("INSERT INTO usuarios (username, password) VALUES (?, ?)", ("admin", "1234"))

    conn.commit()
    conn.close()

crear_tablas_y_admin()

# -----------------------------
# DECORADOR LOGIN
# -----------------------------
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return decorated_function

# -----------------------------
# LOGIN / LOGOUT
# -----------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM usuarios WHERE username=? AND password=?", (username, password))
        usuario = cursor.fetchone()
        conn.close()

        if usuario:
            session["user"] = username
            return redirect("/")
        else:
            error = "Usuario o contraseña incorrectos ❌"

    return render_template("login.html", error=error)

@app.route("/logout")
@login_required
def logout():
    session.pop("user", None)
    return redirect("/login")

# -----------------------------
# RUTAS PRINCIPALES
# -----------------------------
@app.route("/")
@login_required
def index():
    conn = get_connection()
    cursor = conn.cursor()

    # Paginación simple
    page = request.args.get("page", 1, type=int)
    per_page = 10
    offset = (page - 1) * per_page

    cursor.execute("SELECT COUNT(*) FROM tareas")
    total = cursor.fetchone()[0]

    cursor.execute("SELECT * FROM tareas LIMIT ? OFFSET ?", (per_page, offset))
    tareas = cursor.fetchall()
    conn.close()

    total_pages = (total + per_page - 1) // per_page

    return render_template("index.html", tareas=tareas, page=page, total_pages=total_pages)

@app.route("/agregar", methods=["POST"])
@login_required
def agregar():
    descripcion = request.form["descripcion"]
    categoria = request.form.get("categoria", "")
    fecha = request.form.get("fecha", "")
    codigo = request.form.get("codigo", "")

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tareas (descripcion, categoria, fecha, codigo) VALUES (?, ?, ?, ?)",
        (descripcion, categoria, fecha, codigo)
    )
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/completar/<int:id>")
@login_required
def completar(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/eliminar/<int:id>")
@login_required
def eliminar(id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tareas WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect("/")

@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM tareas")
    total = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as completadas FROM tareas WHERE completada = 1")
    completadas = cursor.fetchone()["completadas"]

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

    return render_template("dashboard.html", total=total, completadas=completadas,
                           pendientes=pendientes, porcentaje=porcentaje,
                           nivel=nivel, color_nivel=color_nivel,
                           fecha_actual=fecha_actual)


# -----------------------------
# EXPORTAR EXCEL
# -----------------------------
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from flask import send_file

@app.route("/exportar")
@login_required
def exportar():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tareas ORDER BY id")
    tareas = cursor.fetchall()
    conn.close()

    wb = Workbook()
    ws = wb.active
    ws.title = "Tareas"

    # Cabecera
    headers = ["ID", "Código", "Descripción", "Categoría", "Fecha", "Estado"]
    
    header_fill = PatternFill(start_color="343A40", end_color="343A40", fill_type="solid")
    header_font = Font(bold=True, color="FFFFFF")
    header_alignment = Alignment(horizontal="center", vertical="center")
    
    thin_border = Border(
        left=Side(style='thin'), right=Side(style='thin'),
        top=Side(style='thin'), bottom=Side(style='thin')
    )
    
    for col_num, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col_num, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = header_alignment
        cell.border = thin_border

    # Filas de tareas
    for row_num, tarea in enumerate(tareas, start=2):
        estado = "Completada" if tarea["completada"] == 1 else "Pendiente"
        row = [
            tarea["id"],
            tarea["codigo"] if tarea["codigo"] else "-",
            tarea["descripcion"],
            tarea["categoria"] if tarea["categoria"] else "-",
            tarea["fecha"] if tarea["fecha"] else "-",
            estado
        ]
        for col_num, value in enumerate(row, 1):
            cell = ws.cell(row=row_num, column=col_num, value=value)
            cell.border = thin_border
            cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Colorear columna Estado
            if col_num == 6:
                if estado == "Completada":
                    cell.fill = PatternFill(start_color="28A745", end_color="28A745", fill_type="solid")
                    cell.font = Font(bold=True, color="FFFFFF")
                else:
                    cell.fill = PatternFill(start_color="FFC107", end_color="FFC107", fill_type="solid")
                    cell.font = Font(bold=True, color="000000")

    # Ajustar ancho de columnas automáticamente
    for column_cells in ws.columns:
        length = max(len(str(cell.value)) for cell in column_cells)
        ws.column_dimensions[column_cells[0].column_letter].width = length + 5

    archivo = "tareas_export.xlsx"
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

# -----------------------------
# RUTA ADMIN
# -----------------------------

@app.route("/admin")
@login_required
def admin():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) as total FROM tareas")
    total_tareas = cursor.fetchone()["total"]

    cursor.execute("SELECT COUNT(*) as completadas FROM tareas WHERE completada = 1")
    completadas = cursor.fetchone()["completadas"]

    pendientes = total_tareas - completadas
    exportadas = total_tareas

    cursor.execute("SELECT * FROM tareas ORDER BY id DESC")
    tareas = cursor.fetchall()

    cursor.execute("SELECT DISTINCT categoria FROM tareas")
    categorias = [row["categoria"] for row in cursor.fetchall() if row["categoria"]]

    conn.close()

    return render_template("admin.html",
                           tareas=tareas,
                           categorias=categorias,
                           total=total_tareas,
                           completadas=completadas,
                           pendientes=pendientes,
                           exportadas=exportadas,
                           page=1,
                           total_pages=1)


# -----------------------------
# INICIAR SERVIDOR
# -----------------------------
if __name__ == "__main__":
    app.run(debug=True)

