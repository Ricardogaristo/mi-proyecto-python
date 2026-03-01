-- ============================================================
--  setup_mariadb.sql
--  Ejecutar UNA SOLA VEZ para crear el schema completo
--  Uso: mysql -u root -p < setup_mariadb.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS gestor_tareas
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- Crea el usuario de la app (ajusta la contraseña)
CREATE USER IF NOT EXISTS 'gestor_user'@'localhost'
  IDENTIFIED BY 'CambiaEstaPassword123!';
GRANT ALL PRIVILEGES ON gestor_tareas.* TO 'gestor_user'@'localhost';
FLUSH PRIVILEGES;

USE gestor_tareas;

-- ── Tabla usuarios ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS usuarios (
    id         INT          NOT NULL AUTO_INCREMENT,
    username   VARCHAR(100) NOT NULL,
    email      VARCHAR(255),
    password   VARCHAR(255) NOT NULL,
    es_admin   TINYINT(1)   NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    UNIQUE KEY uq_username (username),
    UNIQUE KEY uq_email    (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Admin por defecto (contraseña: 1234 — cámbiala en producción)
INSERT IGNORE INTO usuarios (username, email, password, es_admin)
VALUES ('admin', 'admin@correo.com', '1234', 1);

-- ── Tabla tareas ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tareas (
    id          INT          NOT NULL AUTO_INCREMENT,
    descripcion TEXT         NOT NULL,
    categoria   VARCHAR(150),
    fecha       DATE,
    completada  TINYINT(1)   NOT NULL DEFAULT 0,
    codigo      VARCHAR(50),
    usuario_id  INT,
    prioridad   TINYINT      NOT NULL DEFAULT 2,   -- 1=alta 2=media 3=baja
    favorita    TINYINT(1)   NOT NULL DEFAULT 0,
    notas       TEXT,
    PRIMARY KEY (id),
    CONSTRAINT fk_tarea_usuario
        FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla subtareas ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subtareas (
    id       INT  NOT NULL AUTO_INCREMENT,
    tarea_id INT  NOT NULL,
    texto    TEXT NOT NULL,
    hecha    TINYINT(1) NOT NULL DEFAULT 0,
    PRIMARY KEY (id),
    CONSTRAINT fk_subtarea_tarea
        FOREIGN KEY (tarea_id) REFERENCES tareas(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla alumnos (módulo Formación) ─────────────────────────────
CREATE TABLE IF NOT EXISTS alumnos (
    id           INT           NOT NULL AUTO_INCREMENT,
    curso        VARCHAR(200),
    nombre       VARCHAR(200)  NOT NULL,
    progreso     DECIMAL(5,2)  NOT NULL DEFAULT 0.00,
    examenes     INT           NOT NULL DEFAULT 0,
    fecha_inicio DATE,
    fecha_fin    DATE,
    supera_75    TINYINT(1)    NOT NULL DEFAULT 0,
    telefono     VARCHAR(30),
    tutor_id     INT,
    archivado    TINYINT(1)    NOT NULL DEFAULT 0,
    archivado_at DATETIME,
    created_at   DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla historial_snapshots ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS historial_snapshots (
    id           INT          NOT NULL AUTO_INCREMENT,
    tutor_id     INT,
    fecha        VARCHAR(20),
    label        VARCHAR(200),
    total        INT,
    superan_75   INT,
    pct_exito    DECIMAL(5,2),
    avg_progreso DECIMAL(5,2),
    created_at   DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla historial_automatico ────────────────────────────────────
CREATE TABLE IF NOT EXISTS historial_automatico (
    id             INT  NOT NULL AUTO_INCREMENT,
    tutor_id       INT,
    fecha          VARCHAR(20),
    evento         VARCHAR(300),
    total_alumnos  INT,
    total_cursos   INT,
    created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ── Tabla alarmas_completadas ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS alarmas_completadas (
    id         INT         NOT NULL AUTO_INCREMENT,
    tutor_id   INT         NOT NULL,
    clave      VARCHAR(200) NOT NULL,
    fecha_dia  DATE        NOT NULL,
    created_at DATETIME    NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_alarma (tutor_id, clave, fecha_dia)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SELECT 'Schema creado correctamente.' AS resultado;
