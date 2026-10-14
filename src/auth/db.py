from __future__ import annotations

import os
import sqlite3

DEFAULT_DATA_DIR = "./data"
DB_FILENAME = "doc_squad.db"


def get_db_path() -> str:
    """Obtiene la ruta a la base de datos SQLite según DATA_DIR o ./data por defecto.

    Crea el directorio contenedor si no existe.

    Returns:
        Ruta completa al fichero de la base de datos SQLite.
    """
    raw_data_dir = os.getenv("DATA_DIR", DEFAULT_DATA_DIR)
    if raw_data_dir.endswith(".db"):
        db_path = raw_data_dir
    else:
        db_path = os.path.join(raw_data_dir, DB_FILENAME)

    dir_path = os.path.dirname(os.path.abspath(db_path))
    if dir_path:
        os.makedirs(dir_path, exist_ok=True)

    return db_path


def init_db(
    conn: sqlite3.Connection | None = None,
    db_path: str | None = None,
) -> None:
    """Crea las tablas users e invitations con CREATE TABLE IF NOT EXISTS.

    Args:
        conn: Conexión SQLite opcional. Si no se pasa, se abre una conexión nueva.
        db_path: Ruta a la base de datos si no se proporciona conexión.
    """
    should_close = False
    if conn is None:
        target_path = db_path or get_db_path()
        conn = sqlite3.connect(target_path)
        should_close = True

    try:
        with conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
                    created_at TEXT NOT NULL
                );
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT UNIQUE NOT NULL,
                    role TEXT NOT NULL DEFAULT 'user' CHECK(role IN ('admin', 'user')),
                    status TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'used', 'revoked')),
                    created_by TEXT NOT NULL,
                    used_by TEXT,
                    created_at TEXT NOT NULL,
                    used_at TEXT,
                    expires_at TEXT
                );
                """
            )
    finally:
        if should_close:
            conn.close()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """Abre y devuelve una conexión a SQLite, creando la base de datos y tablas si no existen.

    Configura row_factory en sqlite3.Row para acceder a columnas por nombre.

    Args:
        db_path: Ruta opcional al fichero SQLite. Por defecto usa get_db_path().

    Returns:
        Conexión abierta e inicializada a SQLite.
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    init_db(conn=conn)
    return conn
