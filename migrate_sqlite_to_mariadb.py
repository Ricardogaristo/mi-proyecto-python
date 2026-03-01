"""
migrate_sqlite_to_mariadb.py
============================
Migra los datos de tareas.db + formacion.db → MariaDB.

Uso:
    python migrate_sqlite_to_mariadb.py

Requisitos previos:
    1. Haber ejecutado setup_mariadb.sql
    2. Tener .env configurado
    3. pip install pymysql python-dotenv
"""

import sqlite3
import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

# ── Conexiones ─────────────────────────────────────────────────────
def mariadb():
    return pymysql.connect(
        host="localhost",
        port=3306,
        db="gestor_tareas",
        user="gestor_user",
        password="",
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
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
    """Convierte valores vacíos a None para MariaDB."""
    if val == "" or val is None:
        return None
    return val


# ── Migración principal ────────────────────────────────────────────
def migrar():
    print("╔══════════════════════════════════════════════════╗")
    print("║   Migración SQLite → MariaDB                     ║")
    print("╚══════════════════════════════════════════════════╝\n")

    mb  = mariadb()
    src = sqlite_main()

    with mb.cursor() as cur:

        # ── 1. Usuarios ────────────────────────────────────────────
        rows = src.execute("SELECT * FROM usuarios").fetchall()
        print(f"👤 Migrando {len(rows)} usuarios…")
        for r in rows:
            cur.execute("""
                INSERT IGNORE INTO usuarios (id, username, email, password, es_admin)
                VALUES (%s, %s, %s, %s, %s)
            """, (r["id"], r["username"], _safe(r["email"]),
                  r["password"], r["es_admin"] or 0))
        mb.commit()
        print(f"   ✅ {len(rows)} usuarios importados.")

        # ── 2. Tareas ──────────────────────────────────────────────
        rows = src.execute("SELECT * FROM tareas").fetchall()
        print(f"\n📋 Migrando {len(rows)} tareas…")
        for r in rows:
            # fecha puede ser string YYYY-MM-DD o vacío
            fecha = _safe(r["fecha"]) if "fecha" in r.keys() else None
            cur.execute("""
                INSERT IGNORE INTO tareas
                    (id, descripcion, categoria, fecha, completada,
                     codigo, usuario_id, prioridad, favorita, notas)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                r["id"],
                r["descripcion"],
                _safe(r["categoria"]),
                fecha,
                r["completada"] or 0,
                _safe(r["codigo"]),
                _safe(r["usuario_id"]),
                r["prioridad"] if "prioridad" in r.keys() and r["prioridad"] else 2,
                r["favorita"]  if "favorita"  in r.keys() and r["favorita"]  else 0,
                _safe(r["notas"] if "notas" in r.keys() else None),
            ))
        mb.commit()
        print(f"   ✅ {len(rows)} tareas importadas.")

        # ── 3. Subtareas ───────────────────────────────────────────
        try:
            rows = src.execute("SELECT * FROM subtareas").fetchall()
            print(f"\n🔖 Migrando {len(rows)} subtareas…")
            for r in rows:
                cur.execute("""
                    INSERT IGNORE INTO subtareas (id, tarea_id, texto, hecha)
                    VALUES (%s, %s, %s, %s)
                """, (r["id"], r["tarea_id"], r["texto"], r["hecha"] or 0))
            mb.commit()
            print(f"   ✅ {len(rows)} subtareas importadas.")
        except Exception as e:
            print(f"   ⚠  Sin subtareas o error: {e}")

    src.close()

    # ── 4. Formación ───────────────────────────────────────────────
    form_src = sqlite_form()
    if form_src:
        print("\n🎓 Migrando datos de formación…")
        with mb.cursor() as cur:

            # Alumnos
            rows = form_src.execute("SELECT * FROM alumnos").fetchall()
            print(f"   👥 {len(rows)} alumnos…")
            for r in rows:
                cur.execute("""
                    INSERT IGNORE INTO alumnos
                        (id, curso, nombre, progreso, examenes,
                         fecha_inicio, fecha_fin, supera_75,
                         telefono, tutor_id, archivado, archivado_at, created_at)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """, (
                    r["id"],
                    _safe(r["curso"]),
                    r["nombre"],
                    r["progreso"] or 0,
                    r["examenes"] or 0,
                    _safe(r["fecha_inicio"]),
                    _safe(r["fecha_fin"]),
                    r["supera_75"] or 0,
                    _safe(r["telefono"]),
                    _safe(r["tutor_id"]),
                    r["archivado"] if "archivado" in r.keys() else 0,
                    _safe(r["archivado_at"] if "archivado_at" in r.keys() else None),
                    r["created_at"] if "created_at" in r.keys() else None,
                ))

            # historial_snapshots
            try:
                rows = form_src.execute("SELECT * FROM historial_snapshots").fetchall()
                print(f"   📊 {len(rows)} snapshots de historial…")
                for r in rows:
                    cur.execute("""
                        INSERT IGNORE INTO historial_snapshots
                            (id, tutor_id, fecha, label, total,
                             superan_75, pct_exito, avg_progreso, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """, (r["id"], _safe(r["tutor_id"]), _safe(r["fecha"]),
                          _safe(r["label"]), r["total"], r["superan_75"],
                          r["pct_exito"], r["avg_progreso"],
                          r["created_at"] if "created_at" in r.keys() else None))
            except Exception as e:
                print(f"   ⚠  historial_snapshots: {e}")

            # historial_automatico
            try:
                rows = form_src.execute("SELECT * FROM historial_automatico").fetchall()
                print(f"   📅 {len(rows)} eventos automáticos…")
                for r in rows:
                    cur.execute("""
                        INSERT IGNORE INTO historial_automatico
                            (id, tutor_id, fecha, evento,
                             total_alumnos, total_cursos, created_at)
                        VALUES (%s,%s,%s,%s,%s,%s,%s)
                    """, (r["id"], _safe(r["tutor_id"]), _safe(r["fecha"]),
                          _safe(r["evento"]), r["total_alumnos"],
                          r["total_cursos"],
                          r["created_at"] if "created_at" in r.keys() else None))
            except Exception as e:
                print(f"   ⚠  historial_automatico: {e}")

            # alarmas_completadas
            try:
                rows = form_src.execute("SELECT * FROM alarmas_completadas").fetchall()
                print(f"   🔔 {len(rows)} alarmas completadas…")
                for r in rows:
                    cur.execute("""
                        INSERT IGNORE INTO alarmas_completadas
                            (id, tutor_id, clave, fecha_dia, created_at)
                        VALUES (%s,%s,%s,%s,%s)
                    """, (r["id"], r["tutor_id"], r["clave"], r["fecha_dia"],
                          r["created_at"] if "created_at" in r.keys() else None))
            except Exception as e:
                print(f"   ⚠  alarmas_completadas: {e}")

            mb.commit()
            print("   ✅ Formación migrada correctamente.")
        form_src.close()
    else:
        print("\n⚠  formacion.db no encontrada, se omite.")

    mb.close()
    print("\n✅ ¡Migración completada con éxito!")


if __name__ == "__main__":
    migrar()
