"""
formacion.py  —  Módulo de Formación para el Gestor de Tareas
Base de datos independiente: formacion.db
"""

from flask import Blueprint, render_template, request, redirect, session, url_for, jsonify
from functools import wraps
from datetime import datetime
import sqlite3
import openpyxl
import io
import os
import unicodedata

# ── Blueprint ──────────────────────────────────────────────────────────────────
formacion_bp = Blueprint(
    "formacion", __name__,
    template_folder="templates"
)

FORM_DB = "formacion.db"

# ── Decorador de login ─────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ── Conexión ───────────────────────────────────────────────────────────────────
def get_form_conn():
    conn = sqlite3.connect(FORM_DB)
    conn.row_factory = sqlite3.Row
    return conn

# ── Inicialización de tablas ───────────────────────────────────────────────────
def inicializar_formacion():
    conn = get_form_conn()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS alumnos (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            curso           TEXT,
            nombre          TEXT NOT NULL,
            progreso        REAL DEFAULT 0,
            examenes        INTEGER DEFAULT 0,
            fecha_inicio    TEXT,
            fecha_fin       TEXT,
            supera_75       INTEGER DEFAULT 0,
            telefono        TEXT,
            tutor_id        INTEGER,
            created_at      TEXT DEFAULT (datetime('now'))
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS historial_snapshots (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            tutor_id    INTEGER,
            fecha       TEXT,
            label       TEXT,
            total       INTEGER,
            superan_75  INTEGER,
            pct_exito   REAL,
            avg_progreso REAL,
            created_at  TEXT DEFAULT (datetime('now'))
        )
    """)
    # Migraciones seguras
    for col, ddl in [
        ("curso",      "ALTER TABLE alumnos ADD COLUMN curso TEXT"),
        ("telefono",   "ALTER TABLE alumnos ADD COLUMN telefono TEXT"),
        ("supera_75",  "ALTER TABLE alumnos ADD COLUMN supera_75 INTEGER DEFAULT 0"),
        ("tutor_id",   "ALTER TABLE alumnos ADD COLUMN tutor_id INTEGER"),
        ("created_at", "ALTER TABLE alumnos ADD COLUMN created_at TEXT DEFAULT (datetime('now'))"),
    ]:
        try:
            cursor.execute(ddl)
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()
    print("✅ formacion.db inicializada correctamente.")

# ── Helpers ────────────────────────────────────────────────────────────────────
def _safe_float(val):
    """Convierte a float; devuelve 0.0 si no es posible."""
    try:
        return float(str(val).replace("%", "").replace(",", ".").strip())
    except (ValueError, TypeError):
        return 0.0

def _safe_int(val):
    try:
        return int(float(str(val).strip()))
    except (ValueError, TypeError):
        return 0

def _safe_date(val):
    """Devuelve la fecha como string 'YYYY-MM-DD' o None."""
    if val is None:
        return None
    from datetime import datetime, date
    if isinstance(val, (datetime, date)):
        return val.strftime("%Y-%m-%d")
    s = str(val).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return s if s else None

# ── Ruta: listado de alumnos + carga de Excel ──────────────────────────────────
@formacion_bp.route("/formacion", methods=["GET", "POST"])
@login_required
def formacion():
    tutor_id = session.get("user_id")
    errores  = []
    exito    = None

    if request.method == "POST":
        archivo = request.files.get("excel")
        if not archivo or not archivo.filename.endswith((".xlsx", ".xls")):
            errores.append("Por favor sube un archivo Excel válido (.xlsx o .xls).")
        else:
            try:
                wb = openpyxl.load_workbook(io.BytesIO(archivo.read()), data_only=True)
                ws = wb.active

                # Detectar encabezados en la primera fila
                headers = [str(c.value).strip().lower() if c.value else "" for c in next(ws.iter_rows(min_row=1, max_row=1))]

                # Normalizar: quitar tildes para comparación más robusta
                def norm(s):
                    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
                headers_norm = [norm(h) for h in headers]

                print(f"📋 Encabezados RAW: {headers}")
                print(f"📋 Encabezados NORM: {headers_norm}")

                def col_idx(posibles):
                    for p in posibles:
                        pn = norm(p)
                        for i, h in enumerate(headers_norm):
                            if pn in h:
                                return i
                    return None

                def col_idx_excl(posibles, excluir):
                    for p in posibles:
                        pn = norm(p)
                        for i, h in enumerate(headers_norm):
                            if pn in h and i != excluir:
                                return i
                    return None

                idx_curso    = col_idx(["del curso", "curso", "materia", "asignatura"])
                idx_nombre   = col_idx_excl(["nombre", "alumno", "estudiante"], idx_curso)
                idx_progreso = col_idx(["progreso", "avance", "progress"])
                idx_examenes = col_idx(["examen", "exam", "evaluac", "prueba"])
                idx_inicio   = col_idx(["fecha inicio", "fecha de inicio", "f. inicio", "inicio"])
                # fecha fin: buscar explícitamente "fin" pero no "inicio"
                idx_fin = None
                for i, h in enumerate(headers_norm):
                    if "fin" in h and "inicio" not in h:
                        idx_fin = i
                        break
                idx_telefono = col_idx(["telefono", "phone", "celular", "whatsapp"])

                print(f"   curso={idx_curso}, nombre={idx_nombre}, progreso={idx_progreso}")
                print(f"   examenes={idx_examenes}, inicio={idx_inicio}, fin={idx_fin}, telefono={idx_telefono}")

                if idx_nombre is None:
                    errores.append("No se encontró columna de Nombre. Revisa el Excel.")
                else:
                    conn  = get_form_conn()
                    curs  = conn.cursor()
                    count = 0

                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if not any(row):
                            continue
                        nombre = str(row[idx_nombre]).strip() if idx_nombre is not None and row[idx_nombre] else None
                        if not nombre or nombre.lower() in ("none", "nan", ""):
                            continue

                        progreso  = _safe_float(row[idx_progreso])  if idx_progreso  is not None and idx_progreso  < len(row) else 0.0
                        examenes  = _safe_int(row[idx_examenes])    if idx_examenes  is not None and idx_examenes  < len(row) else 0
                        f_inicio  = _safe_date(row[idx_inicio])     if idx_inicio    is not None and idx_inicio    < len(row) else None
                        f_fin     = _safe_date(row[idx_fin])        if idx_fin       is not None and idx_fin       < len(row) else None
                        telefono  = str(row[idx_telefono]).strip()  if idx_telefono  is not None and idx_telefono  < len(row) and row[idx_telefono] else None
                        curso     = str(row[idx_curso]).strip()     if idx_curso     is not None and idx_curso     < len(row) and row[idx_curso]    else None
                        supera_75 = 1 if progreso >= 75 else 0

                        curs.execute("""
                            INSERT INTO alumnos (curso, nombre, progreso, examenes, fecha_inicio, fecha_fin,
                                                 supera_75, telefono, tutor_id)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (curso, nombre, progreso, examenes, f_inicio, f_fin, supera_75, telefono, tutor_id))
                        count += 1

                    conn.commit()
                    conn.close()
                    exito = f"✅ {count} alumnos importados correctamente."

            except Exception as e:
                errores.append(f"Error al procesar el archivo: {e}")

    # Cargar alumnos del tutor actual
    conn = get_form_conn()
    alumnos = conn.execute(
        "SELECT * FROM alumnos WHERE tutor_id=? ORDER BY id DESC", (tutor_id,)
    ).fetchall()
    conn.close()

    return render_template("formacion.html", alumnos=alumnos, errores=errores, exito=exito)


# ── Ruta: editar alumno (teléfono) ─────────────────────────────────────────────
@formacion_bp.route("/formacion/editar/<int:alumno_id>", methods=["POST"])
@login_required
def editar_alumno(alumno_id):
    telefono = request.form.get("telefono", "").strip()
    conn = get_form_conn()
    conn.execute("UPDATE alumnos SET telefono=? WHERE id=? AND tutor_id=?",
                 (telefono, alumno_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("formacion.formacion"))


# ── Ruta: eliminar alumno ──────────────────────────────────────────────────────
@formacion_bp.route("/formacion/eliminar/<int:alumno_id>")
@login_required
def eliminar_alumno(alumno_id):
    conn = get_form_conn()
    conn.execute("DELETE FROM alumnos WHERE id=? AND tutor_id=?",
                 (alumno_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("formacion.formacion"))


# ── Ruta: borrar TODOS los alumnos ────────────────────────────────────────────
@formacion_bp.route("/formacion/borrar_todos", methods=["POST"])
@login_required
def borrar_todos():
    conn = get_form_conn()
    conn.execute("DELETE FROM alumnos WHERE tutor_id=?", (session["user_id"],))
    conn.commit()
    conn.close()
    return redirect(url_for("formacion.formacion"))


# ── Ruta: guardar snapshot del estado actual ───────────────────────────────────
@formacion_bp.route("/formacion/guardar_snapshot", methods=["POST"])
@login_required
def guardar_snapshot():
    tutor_id = session["user_id"]
    label    = request.form.get("label", "").strip() or datetime.now().strftime("%d/%m/%Y")
    fecha    = datetime.now().strftime("%Y-%m-%d")

    conn    = get_form_conn()
    alumnos = conn.execute(
        "SELECT * FROM alumnos WHERE tutor_id=?", (tutor_id,)
    ).fetchall()

    total        = len(alumnos)
    superan_75   = sum(1 for a in alumnos if a["supera_75"] == 1)
    pct_exito    = round(superan_75 / total * 100, 1) if total else 0
    avg_progreso = round(sum(a["progreso"] for a in alumnos) / total, 1) if total else 0

    conn.execute("""
        INSERT INTO historial_snapshots (tutor_id, fecha, label, total, superan_75, pct_exito, avg_progreso)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (tutor_id, fecha, label, total, superan_75, pct_exito, avg_progreso))
    conn.commit()
    conn.close()
    return redirect(url_for("formacion.formacion_dashboard"))


# ── Ruta: borrar snapshot ──────────────────────────────────────────────────────
@formacion_bp.route("/formacion/borrar_snapshot/<int:snap_id>")
@login_required
def borrar_snapshot(snap_id):
    conn = get_form_conn()
    conn.execute("DELETE FROM historial_snapshots WHERE id=? AND tutor_id=?",
                 (snap_id, session["user_id"]))
    conn.commit()
    conn.close()
    return redirect(url_for("formacion.formacion_dashboard"))


# ── Ruta: dashboard de formación ───────────────────────────────────────────────
@formacion_bp.route("/formacion/dashboard")
@login_required
def formacion_dashboard():
    tutor_id = session.get("user_id")
    conn     = get_form_conn()

    # Convertir a dicts para que tojson pueda serializarlos en el template
    alumnos = [dict(a) for a in conn.execute(
        "SELECT * FROM alumnos WHERE tutor_id=? ORDER BY progreso DESC", (tutor_id,)
    ).fetchall()]
    conn.close()

    # Normalizar campos que pueden ser None
    for a in alumnos:
        a["progreso"]  = float(a.get("progreso") or 0)
        a["examenes"]  = int(a.get("examenes") or 0)
        a["supera_75"] = int(a.get("supera_75") or 0)
        a["curso"]     = a.get("curso") or ""

    # Cursos únicos ordenados
    cursos = sorted(set(a["curso"] for a in alumnos if a["curso"]))

    total          = len(alumnos)
    superan_75     = sum(1 for a in alumnos if a["supera_75"] == 1)
    no_superan     = total - superan_75
    pct_exito      = round(superan_75 / total * 100, 1) if total else 0
    avg_progreso   = round(sum(a["progreso"] for a in alumnos) / total, 1) if total else 0
    total_examenes = sum(a["examenes"] for a in alumnos)

    # Snapshots históricos (también como dicts)
    conn2     = get_form_conn()
    snapshots = [dict(s) for s in conn2.execute(
        "SELECT * FROM historial_snapshots WHERE tutor_id=? ORDER BY fecha ASC", (tutor_id,)
    ).fetchall()]
    conn2.close()

    snap_labels = [s["label"]        for s in snapshots]
    snap_pct    = [s["pct_exito"]    for s in snapshots]
    snap_avg    = [s["avg_progreso"] for s in snapshots]
    snap_total  = [s["total"]        for s in snapshots]

    return render_template(
        "formacion_dashboard.html",
        alumnos=alumnos,
        cursos=cursos,
        total=total,
        superan_75=superan_75,
        no_superan=no_superan,
        pct_exito=pct_exito,
        avg_progreso=avg_progreso,
        total_examenes=total_examenes,
        snapshots=snapshots,
        snap_labels=snap_labels,
        snap_pct=snap_pct,
        snap_avg=snap_avg,
        snap_total=snap_total,
    )


# ── Ruta: descargar modelo de importación ─────────────────────────────────────
@formacion_bp.route("/formacion/descargar_modelo")
@login_required
def descargar_modelo():
    import os
    from flask import send_file, current_app
    # Buscar el modelo en varias ubicaciones posibles
    posibles = [
        os.path.join(current_app.root_path, "static", "MODELO_IMPORTAR.xlsx"),
        os.path.join(current_app.root_path, "MODELO_IMPORTAR.xlsx"),
        os.path.join(os.path.dirname(__file__), "MODELO_IMPORTAR.xlsx"),
        os.path.join(os.path.dirname(__file__), "static", "MODELO_IMPORTAR.xlsx"),
    ]
    for ruta in posibles:
        if os.path.exists(ruta):
            return send_file(ruta, as_attachment=True, download_name="MODELO_IMPORTAR.xlsx")
    # Si no se encuentra el archivo físico, devolver 404 con mensaje claro
    from flask import abort
    abort(404, "El archivo MODELO_IMPORTAR.xlsx no se encontró en el servidor. "
               "Colócalo en la carpeta 'static/' junto a la aplicación.")


# ── Ruta: API WhatsApp link ────────────────────────────────────────────────────
@formacion_bp.route("/formacion/whatsapp/<int:alumno_id>")
@login_required
def whatsapp_alumno(alumno_id):
    conn   = get_form_conn()
    alumno = conn.execute("SELECT * FROM alumnos WHERE id=?", (alumno_id,)).fetchone()
    conn.close()

    if not alumno:
        return redirect(url_for("formacion.formacion"))

    telefono = (alumno["telefono"] or "").strip().replace(" ", "").replace("-", "").replace("+", "")
    if not telefono:
        return redirect(url_for("formacion.formacion"))

    nombre   = alumno["nombre"]
    progreso = alumno["progreso"]
    inicio   = alumno["fecha_inicio"] or "—"
    fin      = alumno["fecha_fin"]    or "—"

    mensaje = (
        f"Hola {nombre} 👋\n"
        f"Te comparto tu resumen de progreso en el curso:\n\n"
        f"📅 Fecha de inicio: {inicio}\n"
        f"📅 Fecha de fin: {fin}\n"
        f"📊 Progreso actual: {progreso}%\n\n"
        f"{'🎉 ¡Superaste el 75% requerido! Excelente trabajo.' if progreso >= 75 else '⚡ Sigue adelante, ¡puedes lograrlo!'}\n\n"
        f"Cualquier consulta, aquí estoy. ¡Éxitos!"
    )

    import urllib.parse
    url = f"https://wa.me/{telefono}?text={urllib.parse.quote(mensaje)}"
    from flask import redirect as redir
    return redir(url)# ── Ruta: exportar alumnos a Excel ────────────────────────────────────────────
@formacion_bp.route("/formacion/exportar_excel")
@login_required
def exportar_excel():
    import io as _io
    from datetime import datetime as _dt, date as _date
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from openpyxl.formatting.rule import DataBarRule
    from flask import send_file

    tutor_id = session["user_id"]
    conn     = get_form_conn()
    alumnos  = [dict(a) for a in conn.execute(
        "SELECT * FROM alumnos WHERE tutor_id=? ORDER BY curso, nombre", (tutor_id,)
    ).fetchall()]
    conn.close()

    # ── Colores ──
    C_DARK   = "1E3A5F"
    C_GREEN  = "2D9D78"
    C_AMBER  = "D4A017"
    C_RED    = "C0392B"
    C_ALT    = "F0F4F8"
    C_WHITE  = "FFFFFF"
    C_BORDER = "CBD5E1"

    def thin():
        s = Side(style="thin", color=C_BORDER)
        return Border(left=s, right=s, top=s, bottom=s)

    def hdr(cell, text, bg=None):
        cell.value     = text
        cell.font      = Font(bold=True, color=C_WHITE, name="Arial", size=10)
        cell.fill      = PatternFill("solid", fgColor=bg or C_DARK)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border    = thin()

    wb = Workbook()

    # ════════════════════════════════════════
    #  HOJA 1 — Todos los alumnos
    # ════════════════════════════════════════
    ws = wb.active
    ws.title = "Alumnos"

    # Título
    ws.merge_cells("A1:K1")
    c = ws["A1"]
    c.value     = f"Informe de Formación — {_dt.now().strftime('%d/%m/%Y %H:%M')}  ·  {len(alumnos)} alumnos"
    c.font      = Font(bold=True, size=13, color=C_DARK, name="Arial")
    c.fill      = PatternFill("solid", fgColor="E8F0FA")
    c.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 26
    ws.row_dimensions[2].height = 6

    # Cabeceras
    COLS = ["#","Curso","Nombre","Progreso (%)","Exámenes","Fecha Inicio",
            "Fecha Fin","Supera 75%","Teléfono","Estado","Importado"]
    ws.row_dimensions[3].height = 30
    for c_i, h in enumerate(COLS, 1):
        hdr(ws.cell(3, c_i), h)

    # Datos
    for r, a in enumerate(alumnos, 4):
        ws.row_dimensions[r].height = 18
        rf = PatternFill("solid", fgColor=C_ALT if r % 2 == 0 else C_WHITE)
        p  = a.get("progreso", 0) or 0

        def dc(col, val, fmt=None, bold=False, center=False, color=None):
            cell = ws.cell(r, col, val)
            cell.fill      = rf
            cell.font      = Font(name="Arial", size=9, bold=bold, color=color or "1E293B")
            cell.border    = thin()
            cell.alignment = Alignment(horizontal="center" if center else "left", vertical="center")
            if fmt: cell.number_format = fmt

        prog_color = C_GREEN if p >= 75 else (C_AMBER if p >= 50 else C_RED)
        dc(1,  r-3,                       center=True, color="64748B")
        dc(2,  a.get("curso","—") or "—")
        dc(3,  a.get("nombre",""),         bold=True)
        dc(4,  p,                          fmt='0.0"%"', center=True, bold=True, color=prog_color)
        dc(5,  a.get("examenes",0) or 0,  center=True)
        dc(6,  a.get("fecha_inicio","—") or "—", center=True)
        dc(7,  a.get("fecha_fin","—")    or "—", center=True)
        dc(8,  "✔ Sí" if a.get("supera_75") else "✖ No", center=True, bold=True,
           color=C_GREEN if a.get("supera_75") else C_AMBER)
        dc(9,  a.get("telefono","—") or "—")
        dc(10, "✅ Supera 75%" if a.get("supera_75") else "⚠ Bajo 75%",
           center=True, bold=True,
           color=C_GREEN if a.get("supera_75") else C_AMBER)
        dc(11, (a.get("created_at","") or "")[:10], center=True, color="64748B")

    last_data = 3 + len(alumnos)
    if len(alumnos) > 0:
        ws.conditional_formatting.add(
            f"D4:D{last_data}",
            DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="2D9D78")
        )
    ws.auto_filter.ref = f"A3:{get_column_letter(len(COLS))}{last_data}"
    ws.freeze_panes    = "A4"
    for i, w in enumerate([5,32,22,14,10,14,14,12,18,16,18], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # ════════════════════════════════════════
    #  HOJA 2 — Resumen por curso
    # ════════════════════════════════════════
    ws2 = wb.create_sheet("Resumen por Curso")
    ws2.merge_cells("A1:H1")
    c2 = ws2["A1"]
    c2.value     = "Resumen de rendimiento por curso"
    c2.font      = Font(bold=True, size=13, color=C_DARK, name="Arial")
    c2.fill      = PatternFill("solid", fgColor="E8F0FA")
    c2.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 26
    ws2.row_dimensions[2].height = 6

    COLS2 = ["Curso","Total Alumnos","Superan 75%","Bajo 75%",
             "Tasa Éxito (%)","Prog. Promedio (%)","Total Exámenes","Prom. Exámenes"]
    ws2.row_dimensions[3].height = 30
    for c_i, h in enumerate(COLS2, 1):
        hdr(ws2.cell(3, c_i), h)

    from collections import defaultdict
    resumen = defaultdict(lambda: {"total":0,"superan":0,"prog":0,"exam":0})
    for a in alumnos:
        k = a.get("curso") or "Sin curso"
        resumen[k]["total"]  += 1
        resumen[k]["superan"] += int(a.get("supera_75") or 0)
        resumen[k]["prog"]   += float(a.get("progreso") or 0)
        resumen[k]["exam"]   += int(a.get("examenes") or 0)

    totales = {"total":0,"superan":0,"prog":0,"exam":0}
    for r, (curso, d) in enumerate(sorted(resumen.items()), 4):
        ws2.row_dimensions[r].height = 18
        rf2 = PatternFill("solid", fgColor=C_ALT if r % 2 == 0 else C_WHITE)
        n   = d["total"]
        sup = d["superan"]
        pct = round(sup/n*100, 1) if n else 0
        avg = round(d["prog"]/n, 1) if n else 0
        avg_e = round(d["exam"]/n, 1) if n else 0
        totales["total"]  += n
        totales["superan"] += sup
        totales["prog"]   += d["prog"]
        totales["exam"]   += d["exam"]

        for c_i, (val, fmt, center, bold, color) in enumerate([
            (curso,   None,       False, True,  "1E293B"),
            (n,       None,       True,  False, "1E293B"),
            (sup,     None,       True,  True,  C_GREEN),
            (n-sup,   None,       True,  False, C_AMBER),
            (pct,     '0.0"%"',  True,  True,  C_GREEN if pct>=75 else (C_AMBER if pct>=50 else C_RED)),
            (avg,     '0.0"%"',  True,  False, "1E293B"),
            (d["exam"],None,      True,  False, "1E293B"),
            (avg_e,   "0.0",     True,  False, "1E293B"),
        ], 1):
            cell = ws2.cell(r, c_i, val)
            cell.fill      = rf2
            cell.font      = Font(name="Arial", size=9, bold=bold, color=color)
            cell.border    = thin()
            cell.alignment = Alignment(horizontal="center" if center else "left", vertical="center")
            if fmt: cell.number_format = fmt

    # Fila totales
    tr = 4 + len(resumen)
    tn  = totales["total"]
    tsu = totales["superan"]
    tp  = round(tsu/tn*100, 1) if tn else 0
    ta  = round(totales["prog"]/tn, 1) if tn else 0
    te  = totales["exam"]
    tae = round(te/tn, 1) if tn else 0
    for c_i, (val, fmt) in enumerate([
        ("TOTAL GENERAL",None),(tn,None),(tsu,None),(tn-tsu,None),
        (tp,'0.0"%"'),(ta,'0.0"%"'),(te,None),(tae,"0.0"),
    ], 1):
        cell = ws2.cell(tr, c_i, val)
        cell.font      = Font(bold=True, color=C_WHITE, name="Arial", size=9)
        cell.fill      = PatternFill("solid", fgColor=C_DARK)
        cell.alignment = Alignment(horizontal="center" if c_i>1 else "left", vertical="center")
        cell.border    = thin()
        if fmt: cell.number_format = fmt

    ws2.freeze_panes = "A4"
    for i, w in enumerate([32,14,14,12,16,18,14,16], 1):
        ws2.column_dimensions[get_column_letter(i)].width = w

    # ════════════════════════════════════════
    #  HOJA 3 — Seguimiento pendiente
    # ════════════════════════════════════════
    ws3 = wb.create_sheet("Seguimiento Pendiente")
    ws3.merge_cells("A1:J1")
    c3 = ws3["A1"]
    c3.value     = "⚠ Alumnos que requieren seguimiento — Progreso inferior al 75%"
    c3.font      = Font(bold=True, size=13, color="7B2D00", name="Arial")
    c3.fill      = PatternFill("solid", fgColor="FFF3E0")
    c3.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 26
    ws3.row_dimensions[2].height = 6

    COLS3 = ["#","Curso","Nombre","Progreso (%)","Exámenes","Fecha Inicio",
             "Fecha Fin","Teléfono","Días restantes","Prioridad"]
    ws3.row_dimensions[3].height = 30
    for c_i, h in enumerate(COLS3, 1):
        hdr(ws3.cell(3, c_i), h, bg="8B2500")

    pendientes = sorted([a for a in alumnos if not a.get("supera_75")],
                        key=lambda x: x.get("progreso",0))
    hoy = _date.today()

    for r, a in enumerate(pendientes, 4):
        ws3.row_dimensions[r].height = 18
        rf3 = PatternFill("solid", fgColor=C_ALT if r%2==0 else C_WHITE)
        try:
            ff   = _date.fromisoformat(a.get("fecha_fin",""))
            dias = (ff - hoy).days
        except:
            dias = None

        if dias is None:       prio, pc = "—",           "64748B"
        elif dias < 0:         prio, pc = "🔴 Vencido",  C_RED
        elif dias <= 14:       prio, pc = "🟡 Urgente",  C_AMBER
        else:                  prio, pc = "🟢 En plazo", C_GREEN

        for c_i, (val, fmt, center, bold, color) in enumerate([
            (r-3,                                   None,      True,  False, "64748B"),
            (a.get("curso","—") or "—",             None,      False, False, "1E293B"),
            (a.get("nombre",""),                    None,      False, True,  "1E293B"),
            (a.get("progreso",0),                   '0.0"%"', True,  True,  C_RED),
            (a.get("examenes",0) or 0,              None,      True,  False, "1E293B"),
            (a.get("fecha_inicio","—") or "—",      None,      True,  False, "1E293B"),
            (a.get("fecha_fin","—")    or "—",      None,      True,  False, "1E293B"),
            (a.get("telefono","—")     or "—",      None,      False, False, "1E293B"),
            (dias if dias is not None else "—",     None,      True,  False, "1E293B"),
            (prio,                                  None,      True,  True,  pc),
        ], 1):
            cell = ws3.cell(r, c_i, val)
            cell.fill      = rf3
            cell.font      = Font(name="Arial", size=9, bold=bold, color=color)
            cell.border    = thin()
            cell.alignment = Alignment(horizontal="center" if center else "left", vertical="center")
            if fmt: cell.number_format = fmt

    if pendientes:
        ws3.conditional_formatting.add(
            f"D4:D{3+len(pendientes)}",
            DataBarRule(start_type="num", start_value=0, end_type="num", end_value=100, color="C0392B")
        )
    ws3.auto_filter.ref = f"A3:J{3+len(pendientes)}" if pendientes else "A3:J3"
    ws3.freeze_panes    = "A4"
    for i, w in enumerate([5,32,22,12,10,14,14,18,14,14], 1):
        ws3.column_dimensions[get_column_letter(i)].width = w

    # ── Serializar y enviar ──
    buf = _io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    filename = f"formacion_{_dt.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        buf,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )