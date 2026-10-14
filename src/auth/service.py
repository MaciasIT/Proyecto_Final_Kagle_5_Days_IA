from __future__ import annotations

import contextlib
import secrets
import sqlite3
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from .db import get_connection
from .models import (
    InvitationInfo,
    InvitationRecord,
    LoginResult,
    UserProfile,
)


@contextlib.contextmanager
def _get_db(conn: sqlite3.Connection | None = None) -> Generator[sqlite3.Connection, None, None]:
    """Proporciona una conexión activa a la base de datos gestionando su ciclo de vida.

    Si se proporciona una conexión existente, la reutiliza sin cerrarla.
    Si no se proporciona, crea una nueva mediante get_connection() y la cierra al finalizar.
    """
    if conn is not None:
        yield conn
    else:
        new_conn = get_connection()
        try:
            yield new_conn
        finally:
            new_conn.close()


def user_count(conn: sqlite3.Connection | None = None) -> int:
    """Devuelve el número total de usuarios registrados en la base de datos.

    Args:
        conn: Conexión opcional a la base de datos.

    Returns:
        Cantidad de usuarios registrados.
    """
    with _get_db(conn) as db:
        cursor = db.execute("SELECT COUNT(*) AS total FROM users")
        row = cursor.fetchone()
        return int(row["total"]) if row else 0


def is_admin(username: str, conn: sqlite3.Connection | None = None) -> bool:
    """Comprueba si un usuario existe y tiene rol de administrador.

    Args:
        username: Nombre del usuario a consultar.
        conn: Conexión opcional a la base de datos.

    Returns:
        True si el usuario existe y tiene rol 'admin', False en caso contrario.
    """
    if not username or not username.strip():
        return False

    with _get_db(conn) as db:
        cursor = db.execute(
            "SELECT role FROM users WHERE username = ?",
            (username.strip(),),
        )
        row = cursor.fetchone()
        if not row:
            return False
        return str(row["role"]).lower() == "admin"


def validate_invitation(
    code: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Verifica si un código de invitación existe, está activo y no ha expirado.

    Args:
        code: Código alfanumérico de la invitación.
        conn: Conexión opcional a la base de datos.

    Returns:
        Diccionario con code, role y created_by si es válida, o None si no es válida.
    """
    if not code or not code.strip():
        return None

    clean_code = code.strip()
    with _get_db(conn) as db:
        cursor = db.execute(
            """
            SELECT code, role, status, created_by, expires_at
            FROM invitations
            WHERE code = ?
            """,
            (clean_code,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        if row["status"] != "active":
            return None

        expires_at_str = row["expires_at"]
        if expires_at_str:
            try:
                expires_at = datetime.fromisoformat(expires_at_str)
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expires_at:
                    return None
            except ValueError:
                return None

        payload = {
            "code": row["code"],
            "role": row["role"],
            "created_by": row["created_by"],
        }
        return InvitationInfo.model_validate(payload).model_dump()


def use_invitation(
    code: str,
    used_by: str,
    conn: sqlite3.Connection | None = None,
) -> bool:
    """Marca una invitación activa como usada por un usuario registrado.

    Args:
        code: Código de la invitación a consumir.
        used_by: Nombre del usuario que la consume.
        conn: Conexión opcional a la base de datos.

    Returns:
        True si la invitación se marcó como usada exitosamente, False si no era válida.
    """
    if not code or not code.strip() or not used_by or not used_by.strip():
        return False

    clean_code = code.strip()
    clean_user = used_by.strip()

    with _get_db(conn) as db:
        invitation = validate_invitation(clean_code, conn=db)
        if not invitation:
            return False

        now_str = datetime.now(timezone.utc).isoformat()
        cursor = db.execute(
            """
            UPDATE invitations
            SET status = 'used', used_by = ?, used_at = ?
            WHERE code = ? AND status = 'active'
            """,
            (clean_user, now_str, clean_code),
        )
        db.commit()
        return cursor.rowcount > 0


def create_invitation(
    created_by: str,
    role: str = "user",
    expires_hours: int = 72,
    conn: sqlite3.Connection | None = None,
) -> str:
    """Genera una nueva invitación de un solo uso. Solo los administradores pueden crearla.

    Args:
        created_by: Nombre del usuario administrador que genera la invitación.
        role: Rol que se otorgará al usuario registrado ('user' o 'admin').
        expires_hours: Horas de validez de la invitación desde su creación.
        conn: Conexión opcional a la base de datos.

    Returns:
        Código alfanumérico seguro generado para la invitación.

    Raises:
        PermissionError: Si el usuario creador no es administrador.
        ValueError: Si los parámetros proporcionados son inválidos.
    """
    if not created_by or not created_by.strip():
        raise PermissionError("Se requiere un usuario creador válido.")

    clean_creator = created_by.strip()
    with _get_db(conn) as db:
        if not is_admin(clean_creator, conn=db):
            raise PermissionError(
                f"Solo los administradores pueden crear invitaciones. El usuario '{clean_creator}' no es administrador."
            )

        if role not in ("admin", "user"):
            raise ValueError("El rol de la invitación debe ser 'admin' o 'user'.")

        if expires_hours <= 0:
            raise ValueError("El número de horas de expiración debe ser positivo.")

        code = secrets.token_urlsafe(24)
        now = datetime.now(timezone.utc)
        created_at = now.isoformat()
        expires_at = (now + timedelta(hours=expires_hours)).isoformat()

        db.execute(
            """
            INSERT INTO invitations (code, role, status, created_by, created_at, expires_at)
            VALUES (?, ?, 'active', ?, ?, ?)
            """,
            (code, role, clean_creator, created_at, expires_at),
        )
        db.commit()
        return code


def register_user(
    username: str,
    password: str,
    invite_code: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    """Registra un nuevo usuario en la base de datos.

    - Si no existen usuarios en la BD, el primero se crea como admin automáticamente sin código.
    - Si ya existen usuarios, se requiere un invite_code válido.
    - La contraseña se hashea con bcrypt.

    Args:
        username: Nombre del nuevo usuario.
        password: Contraseña en texto claro.
        invite_code: Código de invitación (obligatorio salvo para el primer usuario).
        conn: Conexión opcional a la base de datos.

    Returns:
        Diccionario con username, role y created_at.

    Raises:
        ValueError: Si los datos son inválidos, el usuario ya existe o la invitación no es válida.
    """
    if not username or not username.strip():
        raise ValueError("El nombre de usuario no puede estar vacío.")
    if not password:
        raise ValueError("La contraseña no puede estar vacía.")

    clean_user = username.strip()

    with _get_db(conn) as db:
        # Verificar si el usuario ya existe
        cursor = db.execute("SELECT id FROM users WHERE username = ?", (clean_user,))
        if cursor.fetchone() is not None:
            raise ValueError(f"El usuario '{clean_user}' ya existe.")

        total_users = user_count(conn=db)
        if total_users == 0:
            assigned_role = "admin"
        else:
            if not invite_code or not invite_code.strip():
                raise ValueError("Se requiere un código de invitación para registrarse.")

            clean_code = invite_code.strip()
            invite = validate_invitation(clean_code, conn=db)
            if not invite:
                raise ValueError("Código de invitación inválido o expirado.")
            assigned_role = invite.get("role", "user")

        salt = bcrypt.gensalt()
        password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")
        created_at = datetime.now(timezone.utc).isoformat()

        try:
            db.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (clean_user, password_hash, assigned_role, created_at),
            )

            if total_users > 0 and invite_code:
                marked = use_invitation(invite_code, clean_user, conn=db)
                if not marked:
                    raise ValueError("No se pudo consumir el código de invitación.")

            db.commit()
        except Exception:
            db.rollback()
            raise

        result = {
            "username": clean_user,
            "role": assigned_role,
            "created_at": created_at,
        }
        return UserProfile.model_validate(result).model_dump()


def login_user(
    username: str,
    password: str,
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any] | None:
    """Verifica las credenciales de un usuario.

    Args:
        username: Nombre de usuario.
        password: Contraseña en texto plano.
        conn: Conexión opcional a la base de datos.

    Returns:
        Diccionario con username y role si las credenciales son válidas; None en caso contrario.
    """
    if not username or not username.strip() or not password:
        return None

    clean_user = username.strip()
    with _get_db(conn) as db:
        cursor = db.execute(
            "SELECT username, password_hash, role FROM users WHERE username = ?",
            (clean_user,),
        )
        row = cursor.fetchone()
        if not row:
            return None

        stored_hash = str(row["password_hash"])
        try:
            is_valid = bcrypt.checkpw(
                password.encode("utf-8"),
                stored_hash.encode("utf-8"),
            )
        except Exception:
            return None

        if not is_valid:
            return None

        result = {
            "username": row["username"],
            "role": row["role"],
        }
        return LoginResult.model_validate(result).model_dump()


def list_invitations(
    created_by: str | None = None,
    conn: sqlite3.Connection | None = None,
) -> list[dict[str, Any]]:
    """Devuelve la lista de invitaciones con su estado completo.

    Args:
        created_by: Opcional. Nombre del usuario para filtrar las invitaciones creadas por él.
        conn: Conexión opcional a la base de datos.

    Returns:
        Lista de diccionarios con el detalle de cada invitación.
    """
    with _get_db(conn) as db:
        if created_by and created_by.strip():
            cursor = db.execute(
                """
                SELECT id, code, role, status, created_by, used_by, created_at, used_at, expires_at
                FROM invitations
                WHERE created_by = ?
                ORDER BY id DESC
                """,
                (created_by.strip(),),
            )
        else:
            cursor = db.execute(
                """
                SELECT id, code, role, status, created_by, used_by, created_at, used_at, expires_at
                FROM invitations
                ORDER BY id DESC
                """
            )

        rows = cursor.fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            record = InvitationRecord.model_validate(dict(row)).model_dump()
            result.append(record)
        return result
