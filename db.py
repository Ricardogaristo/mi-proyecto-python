"""
db.py — Módulo de conexión compartida
Soporta PostgreSQL (Render, via DATABASE_URL) y MariaDB (local).
"""

import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "")
_USE_PG = bool(DATABASE_URL)

if _USE_PG:
    import psycopg2
    import psycopg2.extras

def get_connection():
    """Conexión principal (tareas, usuarios, subtareas)."""
    if _USE_PG:
        return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=int(os.getenv("DB_PORT", 3306)),
        db=os.getenv("DB_NAME", "gestor_tareas"),
        user=os.getenv("DB_USER", "gestor_user"),
        password=os.getenv("DB_PASSWORD", ""),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )

def get_form_conn():
    """Conexión al módulo de formación (misma BD)."""
    return get_connection()