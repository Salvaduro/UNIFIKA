import os
import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from supabase import create_client, Client

load_dotenv(".env.local")
load_dotenv(".env")

SUPABASE_URL = os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv(
    "SUPABASE_ANON_KEY") or os.getenv("VITE_SUPABASE_ANON_KEY")

if not SUPABASE_URL or not SUPABASE_ANON_KEY:
    print("ADVERTENCIA: SUPABASE_URL o SUPABASE_ANON_KEY no definidos.")
else:
    supabase_client: Client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)

security = HTTPBearer()


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

        print("\n==== AUDITORÍA DE AUTH EN REQUISICIÓN ====")
        print(f"ID extraído del JWT (sub): {user_id}")
        print(f"Email extraído del JWT: {user_email}")

        if not user_id or not user_email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="El token no contiene el claim 'sub' o 'email'.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Paso A: Validar o Crear en m_perfiles (Lógica Auto-Sanable)
        query_perfil = text("SELECT rol, id_aportante FROM m_perfiles WHERE id = :user_id")
        perfil_result = db.execute(query_perfil, {"user_id": user_id}).mappings().first()
        
        rol_asignado = "Empleador"
        perfil_id_aportante = None
        
        if not perfil_result:
            print(f"[AUTH] ⚠️ Perfil no encontrado para {user_id}. Creando perfil por defecto (Empleador)...")
            try:
                insert_perfil = text("INSERT INTO m_perfiles (id, rol) VALUES (:user_id, 'Empleador')")
                db.execute(insert_perfil, {"user_id": user_id})
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"[AUTH ERROR] No se pudo crear el perfil en m_perfiles: {e}")
        else:
            rol_asignado = perfil_result["rol"]
            perfil_id_aportante = perfil_result.get("id_aportante")

        print(f"Resultado en m_perfiles: Rol asignado -> {rol_asignado}, id_aportante -> {perfil_id_aportante}")

        if rol_asignado == "SuperAdmin":
            return {
                "rol": "SuperAdmin",
                "id_aportante": None,
                "email": user_email,
                "razon_social": "ADMINISTRACIÓN GLOBAL"
            }

        # Paso B: Validar Cliente (por id_aportante desde el perfil, o fallback a Email)
        result = None
        if perfil_id_aportante:
            query = text("SELECT id_aportante, razon_social, estado_contacto FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
            result = db.execute(query, {"id_aportante": perfil_id_aportante}).mappings().first()
            
        if not result:
            query = text("SELECT id_aportante, razon_social, estado_contacto FROM m_aportantes WHERE email ILIKE :user_email LIMIT 1")
            result = db.execute(query, {"user_email": user_email}).mappings().first()
            
            # Si lo encontramos por email y el perfil estaba vacío, actualizamos el perfil
            if result and not perfil_id_aportante:
                try:
                    update_perfil = text("UPDATE m_perfiles SET id_aportante = :id_ap WHERE id = :user_id")
                    db.execute(update_perfil, {"id_ap": result["id_aportante"], "user_id": user_id})
                    db.commit()
                except Exception as e:
                    db.rollback()

        print(f"Resultado en m_aportantes (Cliente): {dict(result) if result else 'Ninguno'}")
        if not result:
            print(
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

            proxy_url = os.getenv("PROXY_URL")
            client_kwargs = {"proxy": proxy_url} if proxy_url else {}
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    resp_contactos = await client.post(url_wolkvox, json=payload_contacto, headers=headers)
                    if resp_contactos.status_code >= 400:
                        import logging
                        logger = logging.getLogger("uvicorn")
                        logger.error(f"[WOLKVOX/FIXIE ERROR] Status: {resp_contactos.status_code}, Body: {resp_contactos.text}")
                        raise HTTPException(status_code=403, detail=f"Error en proveedor externo: {resp_contactos.text}")
                    resp_contactos.raise_for_status()
                    data_contactos = resp_contactos.json()
            except HTTPException as http_e:
                raise http_e
            except Exception as e:
                print(f"==== ERROR WOLKVOX JIT: {str(e)} ====")
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
            if estado_contacto in ["RETIRADO", "UnicaAfiliacion", "En Mora SS"]:
                raise HTTPException(
                    status_code=403, detail="Tu cuenta se encuentra registrada, pero el servicio no está habilitado actualmente. Por favor, comunícate al Tel. 333 6025560 para brindarte atención.")

            nombre_empleador = contacto_data.get("namecontact", "SIN NOMBRE")
            tipo_doc_empleador = contacto_data.get("Tipo ID Contacto", "NIT")
            rut_empleador = contacto_data.get("ID Contacto", "000.000.000-0")
            tipo_empleador = contacto_data.get(
                "Tipo Empleador", "PERSONA JURÍDICA")
            telefono_raw = contacto_data.get("telephonecontact", {})
            telefono = telefono_raw.get("value", "") if isinstance(
                telefono_raw, dict) else str(telefono_raw) if telefono_raw else ""
            email_crm = contacto_data.get("emailcontact", user_email)

            nuevo_aportante = {
                "id_aportante": rut_empleador,
                "razon_social": nombre_empleador,
                "tipo_documento": tipo_doc_empleador,
                "tipo_empleador": tipo_empleador,
                "telefono": telefono,
                "email": str(email_crm).lower().strip() if email_crm else user_email,
                "estado_contacto": estado_contacto
            }

            try:
                supabase_client.table("m_aportantes").upsert(
                    nuevo_aportante).execute()
                    
                # Update m_perfiles so we don't have to fallback to email again
                update_perfil_jit = text("UPDATE m_perfiles SET id_aportante = :id_ap WHERE id = :user_id")
                db.execute(update_perfil_jit, {"id_ap": rut_empleador, "user_id": user_id})
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"==== ERROR HACIENDO UPSERT EN SUPABASE JIT O ACTUALIZANDO PERFIL: {str(e)} ====")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al registrar al usuario en el sistema local."
                )

            # Sincronización en cascada de los empleados inmediatamente después de crear el aportante
            try:
                from main import obtener_empleados_por_empleador
                mock_user = {
                    "rol": "Empleador",
                    "id_aportante": rut_empleador,
                    "email": str(email_crm).lower().strip() if email_crm else user_email,
                    "razon_social": nombre_empleador,
                    "estado_contacto": estado_contacto
                }
                await obtener_empleados_por_empleador(id_contacto=rut_empleador, current_user=mock_user, db=db)
                print(f"[AUTH] ✅ Sincronización en cascada de empleados finalizada para {rut_empleador}.")
            except Exception as sync_e:
                print(f"==== ERROR SYNC EMPLEADOS EN LOGIN: {str(sync_e)} ====")

            return mock_user

        print(
            "[AUTH] ✅ Aportante encontrado en Caché Local (Supabase). Evitando llamada a Wolkvox.")
        return {
            "rol": "Empleador",
            "id_aportante": result["id_aportante"],
            "email": user_email,
            "razon_social": result["razon_social"],
            "estado_contacto": result.get("estado_contacto")
        }
    except Exception as e:
        # If it's already an HTTPException, re-raise it so the detail is preserved
        if isinstance(e, HTTPException):
            raise e
        print(f"==== ERROR AUTH SDK: {str(e)} ====")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tu sesión ha expirado o es inválida. Por favor, inicia sesión nuevamente o comunícate al Tel. 333 6025560 si el problema persiste.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_user(
    user: dict = Depends(get_current_user_unblocked)
):
    if user.get("rol") == "Empleador":
        estado_actual = str(user.get("estado_contacto", "")).upper().strip()
        estados_restringidos = ["EN MORA SS", "RETIRADO", "UNICAAFILIACION"]
        if estado_actual in estados_restringidos:
            raise HTTPException(
                status_code=403, detail=f"Acceso denegado. Estado de cuenta: {user.get('estado_contacto', 'Desconocido')}. Por favor, comunícate con nuestra línea de soporte al 3336025560 para reactivar tu servicio.")
    return user
