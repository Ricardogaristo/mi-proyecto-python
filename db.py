"""
db.py — Módulo de conexión compartida a MariaDB
Importar con: from db import get_connection, get_form_conn
"""

import os
import pymysql
import pymysql.cursors
from dotenv import load_dotenv

load_dotenv()

_DB_CONFIG = {
    "host":     os.getenv("DB_HOST",     "localhost"),
    "port":     int(os.getenv("DB_PORT", 3306)),
    "db":       os.getenv("DB_NAME",     "gestor_tareas"),
    "user":     os.getenv("DB_USER",     "gestor_user"),
    "password": os.getenv("DB_PASSWORD", ""),
    "charset":  "utf8mb4",
    "cursorclass": pymysql.cursors.DictCursor,
    "autocommit": False,
}

def get_connection():
    """Conexión principal (tareas, usuarios, subtareas)."""
    return pymysql.connect(**_DB_CONFIG)

# Alias para formacion.py — usan la misma base de datos
def get_form_conn():
    """Conexión al módulo de formación (misma BD)."""
    return pymysql.connect(**_DB_CONFIG)
