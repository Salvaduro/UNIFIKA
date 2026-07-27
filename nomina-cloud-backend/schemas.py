from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Union
from datetime import datetime
from models import RolUsuario

# =========================================================
# ESQUEMAS PARA M_APORTANTES (TENANT)
# =========================================================
class AportanteBase(BaseModel):
    id_aportante: str
    razon_social: str
    tipo_documento: Optional[str] = None
    tipo_empleador: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    estado_contacto: Optional[str] = None
    carpeta_cliente: Optional[str] = None

class AportanteCreate(AportanteBase):
    pass

class AportanteUpdate(BaseModel):
    """
    Esquema para actualización parcial de aportantes.
    Nota (Escudo Anti-Nulls): Al hacer un UPDATE o UPSERT, se debe utilizar model_dump(exclude_unset=True, exclude_none=True).
    """
    razon_social: Optional[str] = None
    tipo_documento: Optional[str] = None
    tipo_empleador: Optional[str] = None
    telefono: Optional[str] = None
    email: Optional[str] = None
    estado_contacto: Optional[str] = None
    carpeta_cliente: Optional[str] = None

class AportanteResponse(AportanteBase):
    created_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


# =========================================================
# ESQUEMAS PARA M_PERFILES Y USUARIO (MULTI-TENANT)
# =========================================================
class PerfilBase(BaseModel):
    rol: RolUsuario = RolUsuario.EMPLEADOR
    id_aportante: Optional[str] = Field(
        default=None,
        description="ID del aportante asociado al perfil (FK a m_aportantes.id_aportante en Multi-Tenant)"
    )

class PerfilCreate(PerfilBase):
    id: str = Field(..., description="UUID del usuario autenticado en Supabase Auth")

class PerfilUpdate(BaseModel):
    """
    Esquema para actualización de m_perfiles.
    Nota (Escudo Anti-Nulls): Al actualizar en BD usar exclude_unset=True, exclude_none=True.
    """
    rol: Optional[RolUsuario] = None
    id_aportante: Optional[str] = Field(
        default=None,
        description="ID del aportante asociado al perfil en actualización"
    )

class PerfilResponse(PerfilBase):
    id: str
    created_at: Optional[datetime] = None
    aportante: Optional[AportanteResponse] = None

    model_config = ConfigDict(from_attributes=True)


class UserDataResponse(BaseModel):
    """
    Esquema de datos para representar la sesión del usuario o empleador actual.
    Incluye id_aportante de forma explícita para el manejo Multi-Tenant.
    """
    id: Optional[str] = None
    email: Optional[str] = None
    rol: Union[RolUsuario, str] = RolUsuario.EMPLEADOR.value
    id_aportante: Optional[str] = Field(
        default=None,
        description="ID del aportante vinculado al usuario/perfil"
    )
    razon_social: Optional[str] = None
    estado_contacto: Optional[str] = None
    carpeta_cliente: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class UsuarioPerfilResponse(BaseModel):
    """
    Esquema de respuesta estándar para los endpoints de autenticación y perfil (/api/v1/perfil y /api/v1/auth/init-session).
    """
    status: str = "success"
    message: str
    user: Optional[UserDataResponse] = None
    data: Optional[UserDataResponse] = None

    model_config = ConfigDict(from_attributes=True)
