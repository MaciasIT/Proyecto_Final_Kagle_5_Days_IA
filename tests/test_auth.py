from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from auth.db import get_connection, get_db_path, init_db
from auth.service import (
    create_invitation,
    is_admin,
    list_invitations,
    login_user,
    register_user,
    use_invitation,
    user_count,
    validate_invitation,
)


@pytest.fixture(autouse=True)
def isolated_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Aísla la base de datos de cada test en un directorio temporal."""
    test_db_file = tmp_path / "doc_squad_test.db"
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    monkeypatch.setattr("auth.db.get_db_path", lambda: str(test_db_file))
    return test_db_file


def test_init_db_creates_tables(isolated_db: Path) -> None:
    """Verifica que init_db crea correctamente las tablas users e invitations."""
    init_db()

    conn = sqlite3.connect(str(isolated_db))
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'invitations')"
    )
    tables = {row[0] for row in cursor.fetchall()}
    conn.close()

    assert "users" in tables
    assert "invitations" in tables


def test_register_first_user_is_admin() -> None:
    """El primer usuario registrado debe adquirir rol admin sin necesitar invitación."""
    assert user_count() == 0

    user = register_user("primer_admin", "clave_segura_123")

    assert user["username"] == "primer_admin"
    assert user["role"] == "admin"
    assert "created_at" in user
    assert is_admin("primer_admin") is True
    assert user_count() == 1


def test_register_second_user_requires_invite() -> None:
    """El segundo usuario no puede registrarse sin código de invitación."""
    register_user("admin_inicial", "clave123")

    with pytest.raises(ValueError, match="código de invitación"):
        register_user("segundo_usuario", "clave123", invite_code=None)

    with pytest.raises(ValueError, match="código de invitación"):
        register_user("segundo_usuario", "clave123", invite_code="")

    assert user_count() == 1


def test_register_with_valid_invite() -> None:
    """Un usuario puede registrarse exitosamente con una invitación válida activa."""
    register_user("admin_creador", "clave_admin")
    code = create_invitation(created_by="admin_creador", role="user", expires_hours=24)

    user = register_user("nuevo_usuario", "clave_usuario", invite_code=code)

    assert user["username"] == "nuevo_usuario"
    assert user["role"] == "user"
    assert is_admin("nuevo_usuario") is False
    assert user_count() == 2

    # La invitación ya no debe ser válida para ser reutilizada
    assert validate_invitation(code) is None


def test_register_with_used_invite_fails() -> None:
    """No se permite usar una invitación que ya ha sido consumida."""
    register_user("admin_creador", "clave_admin")
    code = create_invitation(created_by="admin_creador", role="user")

    # Primer consumo válido
    register_user("usuario_uno", "clave1", invite_code=code)

    # Segundo intento con el mismo código debe fallar
    with pytest.raises(ValueError, match="invitación"):
        register_user("usuario_dos", "clave2", invite_code=code)

    assert user_count() == 2


def test_register_with_invalid_invite_fails() -> None:
    """Registrarse con un código inexistente o inventado debe fallar."""
    register_user("admin_creador", "clave_admin")

    with pytest.raises(ValueError, match="invitación"):
        register_user("usuario_fantasma", "clave123", invite_code="codigo_inventado_xyz")

    assert user_count() == 1


def test_login_valid_credentials() -> None:
    """El inicio de sesión debe ser exitoso con credenciales correctas."""
    register_user("usuario_valido", "mi_password_correcto")

    auth_data = login_user("usuario_valido", "mi_password_correcto")

    assert auth_data is not None
    assert auth_data["username"] == "usuario_valido"
    assert auth_data["role"] == "admin"


def test_login_invalid_password() -> None:
    """El inicio de sesión debe devolver None si la contraseña es errónea."""
    register_user("usuario_valido", "mi_password_correcto")

    auth_data = login_user("usuario_valido", "password_equivocado")

    assert auth_data is None


def test_login_nonexistent_user() -> None:
    """El inicio de sesión debe devolver None para un usuario inexistente."""
    auth_data = login_user("no_existo", "cualquier_clave")

    assert auth_data is None


def test_create_invitation_by_admin() -> None:
    """Un administrador puede generar invitaciones con rol y caducidad especificados."""
    register_user("admin_test", "clave_admin")

    code = create_invitation(created_by="admin_test", role="user", expires_hours=48)

    assert isinstance(code, str)
    assert len(code) > 10

    info = validate_invitation(code)
    assert info is not None
    assert info["code"] == code
    assert info["role"] == "user"
    assert info["created_by"] == "admin_test"


def test_create_invitation_by_non_admin_fails() -> None:
    """Un usuario que no sea administrador no tiene permisos para crear invitaciones."""
    register_user("admin_root", "clave_root")
    code = create_invitation(created_by="admin_root", role="user")
    register_user("usuario_comun", "clave_comun", invite_code=code)

    with pytest.raises(PermissionError):
        create_invitation(created_by="usuario_comun", role="user")

    with pytest.raises(PermissionError):
        create_invitation(created_by="inexistente", role="user")


def test_list_invitations() -> None:
    """La función list_invitations debe retornar todas las invitaciones y permitir filtrar."""
    register_user("admin_principal", "clave_admin")

    code1 = create_invitation(created_by="admin_principal", role="user")
    code2 = create_invitation(created_by="admin_principal", role="admin")

    # Listar todas
    todas = list_invitations()
    assert len(todas) == 2
    codigos = {inv["code"] for inv in todas}
    assert code1 in codigos
    assert code2 in codigos

    # Consumir una
    register_user("segundo_admin", "clave_admin2", invite_code=code2)

    # Comprobar actualización de estado en la lista
    actualizadas = list_invitations()
    usada = next(inv for inv in actualizadas if inv["code"] == code2)
    assert usada["status"] == "used"
    assert usada["used_by"] == "segundo_admin"
    assert usada["used_at"] is not None

    # Filtrar por creador
    filtradas = list_invitations(created_by="admin_principal")
    assert len(filtradas) == 2

    filtradas_vacias = list_invitations(created_by="otro_admin_sin_invitaciones")
    assert len(filtradas_vacias) == 0


def test_expired_invitation_fails_validation() -> None:
    """Una invitación con fecha de expiración pasada no debe ser válida."""
    register_user("admin_tiempo", "clave_tiempo")
    code = create_invitation(created_by="admin_tiempo", role="user", expires_hours=1)

    # Forzar fecha de expiración en el pasado
    conn = get_connection()
    past_date = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    conn.execute("UPDATE invitations SET expires_at = ? WHERE code = ?", (past_date, code))
    conn.commit()
    conn.close()

    assert validate_invitation(code) is None
    with pytest.raises(ValueError, match="invitación"):
        register_user("usuario_tardio", "clave", invite_code=code)


def test_register_duplicate_username_fails() -> None:
    """No se permite registrar dos usuarios con el mismo nombre."""
    register_user("duplicado", "clave1")
    code = create_invitation(created_by="duplicado", role="user")

    with pytest.raises(ValueError, match="ya existe"):
        register_user("duplicado", "clave2", invite_code=code)
