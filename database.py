import sqlite3

DB_NAME = "tareas.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def crear_tablas():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descripcion TEXT NOT NULL,
            categoria TEXT,
            fecha TEXT,
            completada INTEGER DEFAULT 0,
            codigo TEXT
        )
    """)

    # Tabla usuarios
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    """)

    try:
    cursor.execute("ALTER TABLE tareas ADD COLUMN codigo TEXT")
    print("Columna 'codigo' agregada correctamente.")
    except sqlite3.OperationalError:
    # Si la columna ya existe, no hace nada
    print("La columna 'codigo' ya existe, no se agrega.")

    conn.commit()
    conn.close()