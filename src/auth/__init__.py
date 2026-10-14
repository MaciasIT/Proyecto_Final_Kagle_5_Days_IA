from __future__ import annotations

"""Módulo de autenticación por invitación para Doc Squad v2.

Proporciona registro con asignación automática de administrador al primer usuario,
acceso protegido por hash bcrypt, gestión y validación de invitaciones de un solo uso.
"""

from .db import get_connection, get_db_path, init_db
from .service import (
    create_invitation,
    is_admin,
    list_invitations,
    login_user,
    register_user,
    use_invitation,
    user_count,
    validate_invitation,
)

__all__ = [
    "create_invitation",
    "get_connection",
    "get_db_path",
    "init_db",
    "is_admin",
    "list_invitations",
    "login_user",
    "register_user",
    "use_invitation",
    "user_count",
    "validate_invitation",
]
