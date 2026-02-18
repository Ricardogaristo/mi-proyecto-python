import tkinter as tk
from tkinter import messagebox
from database import get_connection, crear_tabla

# Crear tabla si no existe
crear_tabla()

def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def agregar_columna_codigo():
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("ALTER TABLE tareas ADD COLUMN codigo TEXT")
        print("Columna 'codigo' agregada")
    except sqlite3.OperationalError:
        # Esto ocurre si la columna ya existe
        print("Columna 'codigo' ya existe")
    conn.commit()
    conn.close()

# ---------- FUNCIONES ----------
def agregar():
    codigo = entrada_codigo.get().strip()
    desc = entrada_desc.get().strip()
    cat = entrada_cat.get().strip()
    fecha = entrada_fecha.get().strip()

    if not desc:
        messagebox.showwarning("Error", "La descripción es obligatoria")
        return
    if not codigo:
        messagebox.showwarning("Error", "El código es obligatorio")
        return

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tareas (codigo, descripcion, categoria, fecha) VALUES (?, ?, ?, ?)",
        (codigo, desc, cat, fecha)
    )
    conn.commit()
    conn.close()
    limpiar()
    mostrar()

def mostrar():
    lista.delete(0, tk.END)
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, codigo, descripcion, categoria, fecha, completada FROM tareas")
    for tarea in cursor.fetchall():
        estado = "✔" if tarea[5] else "✘"
        lista.insert(tk.END, f"{tarea[0]} - [{estado}] {tarea[1]} | {tarea[2]} | {tarea[3]} | {tarea[4]}")
    conn.close()

def completar():
    seleccion = lista.curselection()
    if not seleccion:
        return
    item = lista.get(seleccion)
    id_tarea = item.split(" - ")[0]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tareas SET completada = 1 WHERE id = ?", (id_tarea,))
    conn.commit()
    conn.close()
    mostrar()

def limpiar():
    entrada_codigo.delete(0, tk.END)
    entrada_desc.delete(0, tk.END)
    entrada_cat.delete(0, tk.END)
    entrada_fecha.delete(0, tk.END)

# ---------- INTERFAZ ----------
root = tk.Tk()
root.title("Gestor Profesional de Tareas Ricardo Garisto")

# Entradas
tk.Label(root, text="Código").pack()
entrada_codigo = tk.Entry(root)
entrada_codigo.pack()

tk.Label(root, text="Descripción").pack()
entrada_desc = tk.Entry(root)
entrada_desc.pack()

tk.Label(root, text="Categoría").pack()
entrada_cat = tk.Entry(root)
entrada_cat.pack()

tk.Label(root, text="Fecha (YYYY-MM-DD)").pack()
entrada_fecha = tk.Entry(root)
entrada_fecha.pack()

# Botones
tk.Button(root, text="Agregar", command=agregar, bg="#0d6efd", fg="white").pack(pady=2)
tk.Button(root, text="Completar", command=completar, bg="#198754", fg="white").pack(pady=2)
tk.Button(root, text="Limpiar campos", command=limpiar, bg="#ffc107").pack(pady=2)

# Lista
lista = tk.Listbox(root, width=100)
lista.pack(pady=5)

# Mostrar datos al iniciar
mostrar()

root.mainloop()
