from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, ConfigDict, Field


class UserProfile(BaseModel):
    """Modelo Pydantic para los datos públicos o de registro de un usuario."""

    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nombre de usuario único.")
    role: Literal["admin", "user"] = Field(..., description="Rol del usuario en el sistema.")
    created_at: str = Field(..., description="Marca temporal de creación en formato ISO 8601.")


class LoginResult(BaseModel):
    """Modelo Pydantic para el resultado de autenticación exitosa."""

    model_config = ConfigDict(from_attributes=True)

    username: str = Field(..., description="Nombre del usuario autenticado.")
    role: Literal["admin", "user"] = Field(..., description="Rol del usuario autenticado.")


class InvitationInfo(BaseModel):
    """Modelo Pydantic para los datos devueltos al validar una invitación."""

    model_config = ConfigDict(from_attributes=True)

    code: str = Field(..., description="Código único de la invitación.")
    role: Literal["admin", "user"] = Field(..., description="Rol que otorgará al registrarse.")
    created_by: str = Field(..., description="Nombre del administrador creador.")


class InvitationRecord(BaseModel):
    """Modelo Pydantic completo para el registro de una invitación almacenada."""

    model_config = ConfigDict(from_attributes=True)

    id: int = Field(..., description="Identificador único numérico.")
    code: str = Field(..., description="Código de invitación de un solo uso.")
    role: Literal["admin", "user"] = Field(..., description="Rol asociado a la invitación.")
    status: Literal["active", "used", "revoked"] = Field(..., description="Estado de la invitación.")
    created_by: str = Field(..., description="Usuario que generó la invitación.")
    used_by: str | None = Field(default=None, description="Usuario que consumió la invitación.")
    created_at: str = Field(..., description="Fecha de creación ISO 8601.")
    used_at: str | None = Field(default=None, description="Fecha de uso ISO 8601.")
    expires_at: str | None = Field(default=None, description="Fecha de expiración ISO 8601.")
