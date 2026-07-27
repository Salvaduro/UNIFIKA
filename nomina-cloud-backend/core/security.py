import os
import logging
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from supabase import create_client, Client
from models import RolUsuario

logger = logging.getLogger("uvicorn")

load_dotenv(".env.local")
load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    logger.error("ADVERTENCIA: SUPABASE_URL o SUPABASE_ANON_KEY no definidos.")
else:
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

security = HTTPBearer()


class UserContext(dict):
    """
    Diccionario de sesión de usuario con soporte de acceso por atributo y detección de rol VIP.
    Compatibilidad total con el Búnker de Datos RBAC (Camino A) y ORM Multi-Tenant.
    """
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            return None

    def __setattr__(self, key, value):
        self[key] = value

    @property
    def es_vip(self) -> bool:
        """Indica si es STAFF UNIFIKA ('ADMINISTRADOR' o 'SUPERADMIN')."""
        rol_upper = str(self.get("rol", "")).upper().strip()
        return rol_upper in [RolUsuario.ADMINISTRADOR.value, RolUsuario.SUPERADMIN.value]


def filter_by_tenant(query, model, current_user: dict):
    """
    Inyecta el filtro Multi-Tenant (Búnker de Datos RBAC - Camino A) en consultas ORM.
    - 'ADMINISTRADOR' y 'SUPERADMIN': Ejecutan consultas SIN el filtro de id_aportante (Puerta VIP - Soporte).
    - 'EMPLEADOR': Inyecta obligatoriamente filtro por id_aportante en m_empleados, t_novedades y t_cierres_nomina.
    """
    rol = str(current_user.get("rol", "")).upper().strip()
    if rol in [RolUsuario.ADMINISTRADOR.value, RolUsuario.SUPERADMIN.value]:
        # Puerta VIP (Staff UNIFIKA)
        return query

    id_aportante = str(current_user.get("id_aportante", ""))

    if hasattr(model, "id_aportante"):
        return query.filter(model.id_aportante == id_aportante)
    elif hasattr(model, "id_contrato"):
        from models import Empleado
        if hasattr(model, "empleado"):
            return query.join(model.empleado).filter(Empleado.id_aportante == id_aportante)
        else:
            subquery = query.session.query(Empleado.id_contrato).filter(Empleado.id_aportante == id_aportante)
            return query.filter(model.id_contrato.in_(subquery))
    return query


async def get_current_user_unblocked(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
):
    """
    Dependencia de FastAPI para validar el token JWT enviado por Supabase Auth en el header Authorization (Bearer).
    Decodifica el token usando SUPABASE_JWT_SECRET y devuelve el id_aportante extraído de la BD.
    """
    token = credentials.credentials
    if not SUPABASE_URL or not SUPABASE_ANON_KEY:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error de configuración: SUPABASE_URL o SUPABASE_ANON_KEY no definidos."
        )

    try:
        # El SDK de Supabase valida el token automáticamente con el servidor
        user_response = supabase_client.auth.get_user(token)
        user_id = user_response.user.id
        user_email = user_response.user.email
        if user_email:
            user_email = user_email.lower().strip()

        logger.info("\n==== AUDITORÍA DE AUTH EN REQUISICIÓN ====")
        logger.info(f"ID extraído del JWT (sub): {user_id}")
        logger.info(f"Email extraído del JWT: {user_email}")

        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token no contiene el claim 'sub' o 'email'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Paso A: Validar o Crear en m_perfiles (Lógica Auto-Sanable)
        query_perfil = text("SELECT rol, id_aportante FROM m_perfiles WHERE id = :user_id")
        perfil_result = db.execute(query_perfil, {"user_id": user_id}).mappings().first()
        
        rol_asignado = RolUsuario.EMPLEADOR.value
        perfil_id_aportante = None
        
        # Extracción del rol desde m_perfiles o user_metadata del token JWT
        extracted_rol = None
        if perfil_result and perfil_result.get("rol"):
            extracted_rol = perfil_result["rol"]
        elif user_response.user.user_metadata and user_response.user.user_metadata.get("rol"):
            extracted_rol = user_response.user.user_metadata.get("rol")
        
        # Normalización inmediata a mayúsculas y eliminación de espacios
        raw_rol = str(extracted_rol).upper().strip() if extracted_rol else RolUsuario.EMPLEADOR.value
        
        if not perfil_result:
            logger.info(f"[AUTH] ⚠️ Perfil no encontrado para {user_id}. Creando perfil por defecto ({raw_rol})...")
            try:
                insert_perfil = text("INSERT INTO m_perfiles (id, rol) VALUES (:user_id, :rol)")
                db.execute(insert_perfil, {"user_id": user_id, "rol": raw_rol})
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"[AUTH ERROR] No se pudo crear el perfil en m_perfiles: {e}")
        else:
            perfil_id_aportante = perfil_result.get("id_aportante")

        if raw_rol in [RolUsuario.SUPERADMIN.value, RolUsuario.ADMINISTRADOR.value, RolUsuario.EMPLEADOR.value]:
            rol_asignado = raw_rol
        else:
            rol_asignado = RolUsuario.EMPLEADOR.value

        logger.info(f"Resultado en m_perfiles: Rol asignado -> {rol_asignado}, id_aportante -> {perfil_id_aportante}")

        if rol_asignado in [RolUsuario.SUPERADMIN.value, RolUsuario.ADMINISTRADOR.value]:
            logger.info(f"[AUTH] ⭐ Usuario STAFF identificado ({rol_asignado}). Saltando validación local y en Wolkvox.")
            return UserContext({
                "id": user_id,
                "rol": rol_asignado,
                "id_aportante": perfil_id_aportante,
                "email": user_email,
                "razon_social": "ADMINISTRACIÓN GLOBAL" if rol_asignado == RolUsuario.SUPERADMIN.value else "STAFF ADMINISTRATIVO",
                "carpeta_cliente": None
            })

        # Paso B: Validar Cliente (por id_aportante desde el perfil, o fallback a Email)
        result = None
        if perfil_id_aportante:
            query = text("SELECT id_aportante, razon_social, estado_contacto, carpeta_cliente FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
            result = db.execute(query, {"id_aportante": perfil_id_aportante}).mappings().first()
            
        if not result:
            query = text("SELECT id_aportante, razon_social, estado_contacto, carpeta_cliente FROM m_aportantes WHERE email ILIKE :user_email LIMIT 1")
            result = db.execute(query, {"user_email": user_email}).mappings().first()
            
            # Si lo encontramos por email y el perfil estaba vacío, actualizamos el perfil
            if result and not perfil_id_aportante:
                try:
                    update_perfil = text("UPDATE m_perfiles SET id_aportante = :id_ap WHERE id = :user_id")
                    db.execute(update_perfil, {"id_ap": result["id_aportante"], "user_id": user_id})
                    db.commit()
                except Exception as e:
                    db.rollback()
                    logger.warning(f"[AUTH WARNING] No se pudo actualizar m_perfiles: {e}")

        logger.info(f"Resultado en m_aportantes (Cliente): {dict(result) if result else 'Ninguno'}")
        if not result:
            logger.info(
                "[AUTH] ⚠️ Aportante no encontrado localmente. Consultando API de Wolkvox (JiT)...")
            # Paso C: Aprovisionamiento JIT desde Wolkvox
            wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
            if not wolkvox_token:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No encontramos tu correo en nuestro sistema. Por favor, comunícate al Tel. 333 6025560 para brindarte atención."
                )

            url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
            headers = {"Content-Type": "application/json"}
            payload_contacto = {
                "operation": "techcon",
                "wolkvox-token": wolkvox_token,
                "module": "contacts",
                "field": "emailcontact",
                "value": user_email
            }

            fixie_url = os.getenv("FIXIE_URL")
            client_kwargs = {"proxy": fixie_url} if fixie_url else {}
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    response = await client.post(url_wolkvox, json=payload_contacto, headers=headers, timeout=15)
                    response.raise_for_status()
                    data_contactos = response.json()
                    
                    if not data_contactos.get("data") or len(data_contactos["data"]) == 0:
                        # Doble Búsqueda (Case-Insensitive Fallback)
                        payload_contacto["value"] = user_email.upper()
                        response_upper = await client.post(url_wolkvox, json=payload_contacto, headers=headers, timeout=15)
                        response_upper.raise_for_status()
                        data_contactos = response_upper.json()
            except Exception as e:
                logger.error(f"==== ERROR WOLKVOX JIT: {str(e)} ====")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No encontramos tu correo en nuestro sistema. Por favor, comunícate al Tel. 333 6025560 para brindarte atención."
                )

            if not data_contactos.get("data") or len(data_contactos["data"]) == 0:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No encontramos tu correo en nuestro sistema. Por favor, comunícate al Tel. 333 6025560 para brindarte atención."
                )

            contacto_data = data_contactos["data"][0]
            estado_contacto = contacto_data.get("Estado Contacto")
            if str(estado_contacto or "").upper().strip() in ["RETIRADO", "UNICAAFILIACION", "EN MORA SS"]:
                raise HTTPException(
                    status_code=403, detail="Su cuenta presenta una novedad. Por favor comuníquese con la línea de soporte 333 6025560.")
            from core.wolkvox_sync import map_aportante_from_wolkvox
            rut_empleador = contacto_data.get("ID Contacto", "000.000.000-0")
            nuevo_aportante = map_aportante_from_wolkvox(contacto_data, rut_empleador, user_email)

            try:
                supabase_client.table("m_aportantes").upsert(
                    nuevo_aportante).execute()
                    
                # Update m_perfiles so we don't have to fallback to email again
                update_perfil_jit = text("UPDATE m_perfiles SET id_aportante = :id_ap WHERE id = :user_id")
                db.execute(update_perfil_jit, {"id_ap": rut_empleador, "user_id": user_id})
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"==== ERROR HACIENDO UPSERT EN SUPABASE JIT O ACTUALIZANDO PERFIL: {str(e)} ====")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al registrar al usuario en el sistema local."
                )

            # Sincronización en cascada de los empleados inmediatamente después de crear el aportante
            try:
                from main import obtener_empleados_por_empleador
                mock_user = UserContext({
                    "id": user_id,
                    "rol": RolUsuario.EMPLEADOR.value,
                    "id_aportante": rut_empleador,
                    "email": str(email_crm).lower().strip() if email_crm else user_email,
                    "razon_social": nombre_empleador,
                    "estado_contacto": estado_contacto,
                    "carpeta_cliente": contacto_data.get("Carpeta Cliente", None)
                })
                await obtener_empleados_por_empleador(id_contacto=rut_empleador, current_user=mock_user, db=db)
                logger.info(f"[AUTH] ✅ Sincronización en cascada de empleados finalizada para {rut_empleador}.")
            except Exception as sync_e:
                logger.error(f"==== ERROR SYNC EMPLEADOS EN LOGIN: {str(sync_e)} ====")

            return mock_user

        logger.info(
            "[AUTH] ✅ Aportante encontrado en Caché Local (Supabase). Evitando llamada a Wolkvox.")
        return UserContext({
            "id": user_id,
            "rol": RolUsuario.EMPLEADOR.value,
            "id_aportante": result["id_aportante"],
            "email": user_email,
            "razon_social": result["razon_social"],
            "estado_contacto": result.get("estado_contacto"),
            "carpeta_cliente": result.get("carpeta_cliente")
        })
    except Exception as e:
        # If it's already an HTTPException, re-raise it so the detail is preserved
        if isinstance(e, HTTPException):
            raise e
        logger.error(f"==== ERROR AUTH SDK: {str(e)} ====")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión ha expirado o es inválida. Por favor, inicia sesión nuevamente o comunícate al Tel. 333 6025560 si el problema persiste.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user: dict = Depends(get_current_user_unblocked)
):
    user_ctx = UserContext(user) if not isinstance(user, UserContext) else user
    rol_upper = str(user_ctx.get("rol", "")).upper().strip()
    user_ctx["rol"] = rol_upper
    if rol_upper == RolUsuario.EMPLEADOR.value:
        estado_actual = str(user_ctx.get("estado_contacto", "")).upper().strip()
        estados_restringidos = ["EN MORA SS", "RETIRADO", "UNICAAFILIACION"]
        if estado_actual in estados_restringidos:
            raise HTTPException(
                status_code=403, detail=f"Acceso denegado. Estado de cuenta: {user_ctx.get('estado_contacto', 'Desconocido')}. Por favor, comunícate con nuestra línea de soporte al 3336025560 para reactivar tu servicio.")
    return user_ctx
