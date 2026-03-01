"""
migrate_sqlite_to_postgres.py
==============================
Migra los datos de tareas.db + formacion.db → PostgreSQL (Render).

Uso:
    python migrate_sqlite_to_postgres.py

Antes de ejecutar, configurá las variables de entorno con los datos
de conexión de Render (están en el dashboard de tu base de datos).
"""

import sqlite3
import psycopg2
import psycopg2.extras
import os
from dotenv import load_dotenv

load_dotenv()

def postgres():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=int(os.getenv("DB_PORT", 5432)),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
        cursor_factory=psycopg2.extras.RealDictCursor,
    )

def sqlite_main():
    conn = sqlite3.connect("tareas.db")
    conn.row_factory = sqlite3.Row
    return conn

def sqlite_form():
    if os.path.exists("formacion.db"):
        conn = sqlite3.connect("formacion.db")
        conn.row_factory = sqlite3.Row
        return conn
    return None

def _safe(val):
    if val == "" or val is None:
        return None
    return val

def migrar():
    print("╔══════════════════════════════════════════════════╗")
    print("║   Migración SQLite → PostgreSQL (Render)         ║")
    print("╚══════════════════════════════════════════════════╝\n")

    pg  = postgres()
    src = sqlite_main()
    cur = pg.cursor()

    # ── 1. Usuarios ────────────────────────────────────────────
    rows = src.execute("SELECT * FROM usuarios").fetchall()
    print(f"👤 Migrando {len(rows)} usuarios…")
    for r in rows:
        cur.execute("""
            INSERT INTO usuarios (id, username, email, password, es_admin)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (username) DO NOTHING
        """, (r["id"], r["username"], _safe(r["email"]), r["password"], r["es_admin"] or 0))
    pg.commit()
    print(f"   ✅ {len(rows)} usuarios importados.")

    # ── 2. Tareas ──────────────────────────────────────────────
    rows = src.execute("SELECT * FROM tareas").fetchall()
    print(f"\n📋 Migrando {len(rows)} tareas…")
    for r in rows:
        fecha = _safe(r["fecha"]) if "fecha" in r.keys() else None
        cur.execute("""
            INSERT INTO tareas
                (id, descripcion, categoria, fecha, completada,
                 codigo, usuario_id, prioridad, favorita, notas)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, (
            r["id"], r["descripcion"], _safe(r["categoria"]), fecha,
            r["completada"] or 0, _safe(r["codigo"]), _safe(r["usuario_id"]),
            r["prioridad"] if "prioridad" in r.keys() and r["prioridad"] else 2,
            r["favorita"]  if "favorita"  in r.keys() and r["favorita"]  else 0,
            _safe(r["notas"] if "notas" in r.keys() else None),
        ))
    pg.commit()
    print(f"   ✅ {len(rows)} tareas importadas.")

    # ── 3. Subtareas ───────────────────────────────────────────
    try:
        rows = src.execute("SELECT * FROM subtareas").fetchall()
        print(f"\n🔖 Migrando {len(rows)} subtareas…")
        for r in rows:
            cur.execute("""
                INSERT INTO subtareas (id, tarea_id, texto, hecha)
                VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING
            """, (r["id"], r["tarea_id"], r["texto"], r["hecha"] or 0))
        pg.commit()
        print(f"   ✅ {len(rows)} subtareas importadas.")
    except Exception as e:
        print(f"   ⚠  Sin subtareas o error: {e}")
        pg.rollback()

    # Sincronizar secuencias de PostgreSQL
    for tabla in ["usuarios", "tareas", "subtareas"]:
        cur.execute(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), MAX(id)) FROM {tabla}")
    pg.commit()

    src.close()

    # ── 4. Formación ───────────────────────────────────────────
    form_src = sqlite_form()
    if form_src:
        print("\n🎓 Migrando datos de formación…")

        rows = form_src.execute("SELECT * FROM alumnos").fetchall()
        print(f"   👥 {len(rows)} alumnos…")
        for r in rows:
            cur.execute("""
                INSERT INTO alumnos
                    (id, curso, nombre, progreso, examenes, fecha_inicio, fecha_fin,
                     supera_75, telefono, tutor_id, archivado, archivado_at, created_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT DO NOTHING
            """, (
                r["id"], _safe(r["curso"]), r["nombre"], r["progreso"] or 0,
                r["examenes"] or 0, _safe(r["fecha_inicio"]), _safe(r["fecha_fin"]),
                r["supera_75"] or 0, _safe(r["telefono"]), _safe(r["tutor_id"]),
                r["archivado"] if "archivado" in r.keys() else 0,
                _safe(r["archivado_at"] if "archivado_at" in r.keys() else None),
                r["created_at"] if "created_at" in r.keys() else None,
            ))

        try:
            rows = form_src.execute("SELECT * FROM historial_snapshots").fetchall()
            for r in rows:
                cur.execute("""
                    INSERT INTO historial_snapshots
                        (id, tutor_id, fecha, label, total, superan_75, pct_exito, avg_progreso, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                """, (r["id"], _safe(r["tutor_id"]), _safe(r["fecha"]), _safe(r["label"]),
                      r["total"], r["superan_75"], r["pct_exito"], r["avg_progreso"],
                      r["created_at"] if "created_at" in r.keys() else None))
        except Exception as e:
            print(f"   ⚠  historial_snapshots: {e}")
            pg.rollback()

        try:
            rows = form_src.execute("SELECT * FROM historial_automatico").fetchall()
            for r in rows:
                cur.execute("""
                    INSERT INTO historial_automatico
                        (id, tutor_id, fecha, evento, total_alumnos, total_cursos, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING
                """, (r["id"], _safe(r["tutor_id"]), _safe(r["fecha"]), _safe(r["evento"]),
                      r["total_alumnos"], r["total_cursos"],
                      r["created_at"] if "created_at" in r.keys() else None))
        except Exception as e:
            print(f"   ⚠  historial_automatico: {e}")
            pg.rollback()

        try:
            rows = form_src.execute("SELECT * FROM alarmas_completadas").fetchall()
            for r in rows:
                cur.execute("""
                    INSERT INTO alarmas_completadas (id, tutor_id, clave, fecha_dia, created_at)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT (tutor_id, clave, fecha_dia) DO NOTHING
                """, (r["id"], r["tutor_id"], r["clave"], r["fecha_dia"],
                      r["created_at"] if "created_at" in r.keys() else None))
        except Exception as e:
            print(f"   ⚠  alarmas_completadas: {e}")
            pg.rollback()

        # Sincronizar secuencias
        for tabla in ["alumnos", "historial_snapshots", "historial_automatico", "alarmas_completadas"]:
            try:
                cur.execute(f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), COALESCE(MAX(id),1)) FROM {tabla}")
            except Exception:
                pass
        pg.commit()
        print("   ✅ Formación migrada correctamente.")
        form_src.close()
    else:
        print("\n⚠  formacion.db no encontrada, se omite.")

    cur.close()
    pg.close()
    print("\n✅ ¡Migración completada con éxito!")

if __name__ == "__main__":
    migrar()
