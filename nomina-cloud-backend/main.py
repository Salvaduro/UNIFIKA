import pandas as pd
import math
import datetime

import calendar
import holidays
import uuid
import os
import logging
import json
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fastapi.responses import Response
from fastapi import FastAPI, Depends, Body, HTTPException, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Union, Optional, Tuple
from database import get_db, SessionLocal
from pydantic import BaseModel
import httpx
from core.security import get_current_user, get_current_user_unblocked, supabase_client, filter_by_tenant, UserContext
import models
import schemas
import resend
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

resend.api_key = os.environ.get("RESEND_API_KEY")

logger = logging.getLogger("uvicorn")

# NO BORRAR: Requerido por el motor matemático
import numpy as np
import pandas as pd

# =========================================================
# CONSTANTES Y FUNCIONES DE UTILIDAD (HELPERS)
# =========================================================

NOMBRES_EXTRAS = {
    'HED': 'HR. EXTRA DIURNA (1.25)',
    'HEN': 'HR. EXTRA NOCTURNA (1.75)',
    'HEDF': 'HR. EXTRA DOM/FEST DIURNA (2.05)',
    'HENF': 'HR. EXTRA DOM/FEST NOCTURNA (2.55)',
    'RN': 'RECARGO NOCTURNO (0.35)',
    'RDN': 'RECARGO DOM/FEST DIURNO (0.80)',
    'RNF': 'RECARGO FESTIVO NOCTURNO (1.15)'
}


def forzar_numero(valor):
    try:
        return float(valor) if pd.notnull(valor) else 0.0
    except:
        return 0.0


co_holidays = holidays.CO()

def is_business_day(d: datetime.date) -> bool:
    return d.weekday() < 5 and d not in co_holidays

def add_business_days(start_date: datetime.date, days: int) -> datetime.date:
    current = start_date
    step = 1 if days > 0 else -1
    remaining = abs(days)
    
    while remaining > 0:
        current += datetime.timedelta(days=step)
        if is_business_day(current):
            remaining -= 1
    return current

def obtener_ultimo_dia_mes(year: int, month: int) -> datetime.date:
    last_day = calendar.monthrange(year, month)[1]
    return datetime.date(year, month, last_day)

def obtener_nombre_mes(mes_num: int) -> str:
    meses = ["", "ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE", "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
    return meses[mes_num]

def calcular_fechas_ciclo(fecha_base: datetime.date) -> Optional[Tuple[str, str, str]]:
    year = fecha_base.year
    month = fecha_base.month
    
    corte_15_actual = datetime.date(year, month, 15)
    corte_fin_actual = obtener_ultimo_dia_mes(year, month)
    
    if month == 1:
        prev_year = year - 1
        prev_month = 12
    else:
        prev_year = year
        prev_month = month - 1
        
    corte_15_anterior = datetime.date(prev_year, prev_month, 15)
    corte_fin_anterior = obtener_ultimo_dia_mes(prev_year, prev_month)
    
    if fecha_base == add_business_days(corte_15_actual, -2):
        return ('PRELIQUIDAR', f"{obtener_nombre_mes(month)} {year}", '1')
        
    if fecha_base == add_business_days(corte_fin_actual, -2):
        return ('PRELIQUIDAR', f"{obtener_nombre_mes(month)} {year}", '2')
        
    if fecha_base == add_business_days(corte_15_actual, 3):
        return ('CERRAR', f"{obtener_nombre_mes(month)} {year}", '1')
        
    if fecha_base == add_business_days(corte_fin_anterior, 3):
        return ('CERRAR', f"{obtener_nombre_mes(prev_month)} {prev_year}", '2')
        
    return None

def formatear_periodo(valor):
    if pd.isnull(valor):
        return "SIN PERIODO"
    if isinstance(valor, (pd.Timestamp, datetime.datetime)):
        return valor.strftime('%B %Y').upper()
    try:
        return pd.to_datetime(valor).strftime('%B %Y').upper()
    except:
        return str(valor).upper()


def registrar_auditoria(db: Session, current_user: dict, tipo_accion: str, entidad_afectada: str = None, detalles: dict = None):
    if isinstance(current_user, dict):
        email = str(current_user.get("email", "desconocido")).strip()
        rol = str(current_user.get("rol", "")).upper().strip()
        id_aportante = str(current_user.get("id_aportante", "")).strip()
    else:
        email = str(getattr(current_user, "email", "desconocido")).strip()
        rol = str(getattr(current_user, "rol", "")).upper().strip()
        id_aportante = str(getattr(current_user, "id_aportante", "")).strip()

    detalles_json = json.dumps(detalles or {}, ensure_ascii=False)

    query = text("""
        INSERT INTO t_auditoria_logs (
            usuario_email, rol_usuario, id_aportante, tipo_accion, entidad_afectada, detalles
        ) VALUES (
            :email, :rol, :id_aportante, :tipo_accion, :entidad_afectada, CAST(:detalles AS jsonb)
        )
    """)
    db.execute(query, {
        "email": email,
        "rol": rol,
        "id_aportante": id_aportante,
        "tipo_accion": str(tipo_accion).strip(),
        "entidad_afectada": str(entidad_afectada).strip() if entidad_afectada else None,
        "detalles": detalles_json
    })


class ComprobantePDF(FPDF):
    def __init__(self, datos_empleador, periodo_liq):
        super().__init__()
        self.emp_nombre = datos_empleador.get('nombre', '')
        self.emp_nit = datos_empleador.get('nit', '')
        self.emp_tipo = datos_empleador.get('tipo', '')
        self.periodo_liq = periodo_liq

    def header(self):
        logo_path = 'LOGO_UFK.jpg'
        if os.path.exists(logo_path):
            with self.local_context(fill_opacity=0.2):
                self.image(logo_path, x=10, y=10, w=190)

        self.set_font('helvetica', 'B', 11)
        self.cell(0, 5, self.emp_nombre, align='R',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font('helvetica', '', 9)
        self.cell(0, 4, f"RUT: {self.emp_nit}", align='R',
                  new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 4, f"Tipo: {self.emp_tipo}",
                  align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(4)

        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'COMPROBANTE INDIVIDUAL DE PAGO DE NÓMINA',
                  align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font('helvetica', '', 11)
        self.cell(0, 5, f'Periodo de Pago: {self.periodo_liq}',
                  align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(5)

# =========================================================
# INICIALIZACIÓN DE LA APLICACIÓN FASTAPI
# =========================================================


app = FastAPI(
    title="Nómina Cloud API",
    description="API para la gestión y liquidación de nóminas conectada a Supabase.",
    version="1.0.0"
)

raw_origins = os.getenv("FRONTEND_URL", "http://localhost:5173")
allow_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
allow_origins.extend(["https://app.unifika.co", "http://localhost:5173"])
allow_origins = list(set(allow_origins))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root(db: Session = Depends(get_db)):
    try:
        # Ejecutamos una consulta simple para verificar la conexión
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {
                "status": "success",
                "message": "¡La API de Nómina Cloud está viva y conectada a Supabase correctamente!"
            }
        else:
            return {
                "status": "warning",
                "message": "La API está corriendo, pero hubo un comportamiento inesperado en la conexión."
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error de conexión a la base de datos: {str(e)}"
        }


@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    """Endpoint de Health Check para el balanceador de carga de Render."""
    try:
        # Ping ligero a la base de datos
        result = db.execute(text("SELECT 1")).scalar()
        if result == 1:
            return {"status": "ok", "database": "connected"}
        else:
            raise HTTPException(status_code=503, detail="Unexpected DB response")
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"DB Connection failed: {str(e)}")


@app.get("/api/v1/mi-ip")
async def get_my_ip():
    """Endpoint temporal para conocer la IP pública del servidor."""
    fixie_url = os.getenv("FIXIE_URL")
    client_kwargs = {"proxy": fixie_url} if fixie_url else {}
    async with httpx.AsyncClient(**client_kwargs) as client:
        response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return response.json()


@app.get("/api/v1/auth/sync-status")
async def sync_auth_status(current_user: dict = Depends(get_current_user_unblocked), db: Session = Depends(get_db)):
    """Endpoint para sincronizar el estado_contacto con Wolkvox (silencioso)."""
    user_email = current_user.get("email")
    if user_email:
        user_email = user_email.lower().strip()
    if not user_email:
        raise HTTPException(
            status_code=400, detail="No email provided in token.")

    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    if not wolkvox_token:
        # Fallback si no hay token de Wolkvox
        return {"estado_contacto": current_user.get("estado_contacto")}

    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    headers = {"Content-Type": "application/json"}
    payload_contacto = {
        "operation": "techcon",
        "wolkvox-token": wolkvox_token,
        "module": "contacts",
        "field": "emailcontact",
        "value": user_email
    }

    nuevo_estado = current_user.get("estado_contacto")
    fixie_url = os.getenv("FIXIE_URL")
    client_kwargs = {"proxy": fixie_url} if fixie_url else {}
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp_contactos = await client.post(url_wolkvox, json=payload_contacto, headers=headers)
            if resp_contactos.status_code >= 400:
                import logging
                logger = logging.getLogger("uvicorn")
                logger.error(f"[WOLKVOX/FIXIE ERROR in sync_auth_status] Status: {resp_contactos.status_code}, Body: {resp_contactos.text}")
            elif resp_contactos.status_code == 200:
                data_contactos = resp_contactos.json()
                if data_contactos.get("data") and len(data_contactos["data"]) > 0:
                    contacto_data = data_contactos["data"][0]
                    nuevo_estado = contacto_data.get("Estado Contacto")

                    # Update local database
                    update_query = text(
                        "UPDATE m_aportantes SET estado_contacto = :estado WHERE email ILIKE :email")
                    db.execute(update_query, {
                               "estado": nuevo_estado, "email": user_email})
                    db.commit()
    except Exception as e:
        import logging
        logger = logging.getLogger("uvicorn")
        logger.error(f"[WOLKVOX/FIXIE EXCEPTION in sync_auth_status] {str(e)}")
        pass

    return {"estado_contacto": nuevo_estado}


@app.get("/api/v1/perfil", response_model=schemas.UsuarioPerfilResponse)
async def get_perfil_usuario(current_user: dict = Depends(get_current_user)):
    return {
        "status": "success",
        "message": "Token válido y autenticación exitosa.",
        "user": current_user
    }

@app.post("/api/v1/auth/init-session", response_model=schemas.UsuarioPerfilResponse)
async def init_session_endpoint(current_user: dict = Depends(get_current_user_unblocked)):
    """
    Endpoint protegido para inicializar la sesión y validar el perfil (m_aportantes).
    Usa get_current_user_unblocked para no arrojar 403 prematuramente por estados restringidos.
    """
    return {
        "status": "success",
        "message": "Token válido y autenticación exitosa.",
        "data": current_user
    }


@app.get("/api/v1/historico/ultimo-dias/{id_contrato}")
def obtener_ultimo_dias_laborados(id_contrato: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    query = text("""
        SELECT dias_laborados 
        FROM t_novedades 
        WHERE id_contrato = :id_contrato 
        ORDER BY created_at DESC 
        LIMIT 1
    """)
    resultado = db.execute(
        query, {"id_contrato": id_contrato}).mappings().first()

    if resultado:
        return {"status": "success", "dias_laborados": resultado["dias_laborados"]}
    return {"status": "not_found", "dias_laborados": 0}


@app.get("/api/v1/empleador/{id_contacto}/empleados")
async def obtener_empleados_por_empleador(id_contacto: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint (Proxy) para obtener todos los empleados de un empleador con Caché en Supabase y JiT Fallback en cascada.

    Reglas de Negocio - Sincronización de Empleados y Soft-Delete (Wolkvox):
    - Manejo de Rotación (Wolkvox): NUNCA aplicar Hard-Delete a un empleado que ya no viene en Wolkvox (estado "lost").
    - Se aplica Soft-Delete cambiando estado_empleado = 'RETIRADO'.
    - Un empleado en estado RETIRADO o En Mora SS no puede operar en el sistema.
    """
    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() not in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
        id_contacto = current_user["id_aportante"]
    
    id_contacto = str(id_contacto)
    
    # Paso A: Consulta m_aportantes local
    query_admin = text("SELECT id_aportante, razon_social, email, estado_contacto, carpeta_cliente FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
    try:
        resultado_admin = db.execute(query_admin, {"id_aportante": id_contacto}).mappings().first()
    except Exception as e:
        db.rollback()
        logger.warning(f"Error consulta admin en m_aportantes: {e}")
        resultado_admin = None

    # Paso B: JiT Fallback a Wolkvox (Contactos) si el aportante no existe
    if not resultado_admin:
        import os, httpx
        logger.info(f"[WOLKVOX] ⚠️ Aportante {id_contacto} no encontrado localmente. Extrayendo desde Wolkvox (JiT)...")
        wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
        if wolkvox_token:
            url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
            headers = {"Content-Type": "application/json"}
            payload_contacto = {
                "operation": "techcon",
                "wolkvox-token": wolkvox_token,
                "module": "contacts",
                "field": "ID Contacto",
                "value": id_contacto
            }
            fixie_url = os.getenv("FIXIE_URL")
            client_kwargs = {"proxy": fixie_url} if fixie_url else {}
            try:
                async with httpx.AsyncClient(**client_kwargs) as client:
                    response = await client.post(url_wolkvox, json=payload_contacto, headers=headers, timeout=15)
                    if response.status_code == 200:
                        data_contactos = response.json()
                        if data_contactos.get("data") and len(data_contactos["data"]) > 0:
                            contacto_data = data_contactos["data"][0]
                            from core.security import supabase_client
                            
                            from core.wolkvox_sync import map_aportante_from_wolkvox
                            nuevo_aportante = map_aportante_from_wolkvox(contacto_data, id_contacto, id_contacto)
                            
                            try:
                                supabase_client.table("m_aportantes").upsert(nuevo_aportante).execute()
                                resultado_admin = nuevo_aportante
                                
                                # Sincronización en cascada (Oportunidades) - Eslabón restaurado
                                from core.wolkvox_sync import sync_empleados_from_wolkvox
                                await sync_empleados_from_wolkvox(id_contacto, resultado_admin.get("razon_social", id_contacto), db)
                            except Exception as e_upsert:
                                logger.error(f"==== ERROR UPSERT JIT Aportante: {str(e_upsert)} ====")
            except Exception as e_net:
                logger.error(f"==== ERROR WOLKVOX JIT NETWORK: {str(e_net)} ====")

    if not resultado_admin:
        raise HTTPException(status_code=404, detail=f"Aportante con ID {id_contacto} no encontrado en el sistema ni en el CRM.")

    razon_social = resultado_admin.get("razon_social", id_contacto)
    email_aportante = resultado_admin.get("email", "")

    # 1. Intentar cargar desde Caché Local (Supabase)
    try:
        query_empleados = text("SELECT * FROM m_empleados WHERE id_aportante = :id_aportante AND estado_empleado != 'RETIRADO'")
        empleados_locales = db.execute(query_empleados, {"id_aportante": id_contacto}).mappings().all()
        if empleados_locales and len(empleados_locales) > 0:
            logger.info(f"[CACHE] ✅ {len(empleados_locales)} empleados encontrados localmente. Evitando Wolkvox.")
            data_local = []
            for emp in empleados_locales:
                data_local.append({
                    "ID_CONTRATO": emp["id_contrato"],
                    "ID_APORTANTE": emp["id_aportante"],
                    "ID_EMPLEADO": emp["id_empleado"],
                    "T_ID_EMPLEADO": emp["t_id_empleado"],
                    "NOMBRE_EMPLEADO": emp["nombre_empleado"],
                    "CARGO_DESEMPENEADO": emp["cargo"],
                    "TIPO_CONTRATO": emp["tipo_contrato"],
                    "ESTADO_EMPLEADO": emp["estado_empleado"],
                    "PERIODO_PAGO": emp["periodo_pago"],
                    "SALARIO_BASE": float(emp["salario_base"]) if emp["salario_base"] else 0,
                    "VLR_BONO": float(emp["vlr_bono"]) if emp["vlr_bono"] else 0,
                    "SALARIO_ESPECIE": float(emp["sal_especie"]) if emp["sal_especie"] else 0,
                    "EPS": emp["eps"],
                    "FONDO DE PENSIONES": emp["afp"],
                    "ES_SMLV": "SI" if emp["es_smlv"] else "NO",
                    "CON_BONO": "SI" if emp["con_bono"] else "NO",
                    "TIENE_AUX": "SI" if emp["tiene_aux"] else "NO",
                    "LINK_DRIVE": emp.get("link_drive", ""),
                    "RAZON_SOCIAL": razon_social,
                    "EMAIL_APORTANTE": email_aportante,
                })
            return {
                "status": "success",
                "empleador": razon_social,
                "carpeta_cliente": resultado_admin.get("carpeta_cliente") if resultado_admin else None,
                "data": data_local
            }
    except Exception as e:
        db.rollback()
        logger.error(f"[CACHE ERROR] Fallo al consultar m_empleados: {str(e)}")

    logger.info(f"[WOLKVOX] ⚠️ Empleados no encontrados localmente para {id_contacto}. Extrayendo desde Wolkvox...")
    
    async def _mock_fallback():
        return {
            "status": "success",
            "empleador": "MOCK EMPRESA S.A.",
            "data": [{
                "ID_CONTRATO": f"{id_contacto}_102938",
                "NOMBRE_EMPLEADO": "Juan Perez (Mock)",
                "SALARIO_BASE": 50000
            }]
        }
        
    # Paso C: Extracción en cascada a Wolkvox (Oportunidades)
    try:
        from core.wolkvox_sync import sync_empleados_from_wolkvox
        
        empleados_limpios = await sync_empleados_from_wolkvox(id_contacto, razon_social, db)
        
        return {
            "status": "success",
            "empleador": razon_social,
            "carpeta_cliente": resultado_admin.get("carpeta_cliente") if resultado_admin else None,
            "data": empleados_limpios
        }
    except Exception as e:
        if id_contacto.upper() == "EMP-001":
            return await _mock_fallback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error al sincronizar empleados desde Wolkvox: {str(e)}")


@app.get("/api/v1/empleador/{id_contacto}/empleado/{id_empleado}")
async def obtener_detalle_empleado(id_contacto: str, id_empleado: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Endpoint para traer el detalle de un empleado específico desde la caché local (Supabase).
    """
    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() not in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
        id_contacto = current_user["id_aportante"]
        
    query_emp = text("SELECT * FROM m_empleados WHERE id_aportante = :id_aportante AND id_contrato = :id_contrato")
    result = db.execute(query_emp, {"id_aportante": id_contacto, "id_contrato": id_empleado}).mappings().first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Empleado no encontrado en la base de datos local.")
        
    data_local = {
        "ID_CONTRATO": result["id_contrato"],
        "ID_APORTANTE": result["id_aportante"],
        "ID_EMPLEADO": result["id_empleado"],
        "T_ID_EMPLEADO": result["t_id_empleado"],
        "NOMBRE_EMPLEADO": result["nombre_empleado"],
        "CARGO_DESEMPENEADO": result["cargo"],
        "TIPO_CONTRATO": result["tipo_contrato"],
        "ESTADO_EMPLEADO": result["estado_empleado"],
        "PERIODO_PAGO": result["periodo_pago"],
        "SALARIO_BASE": float(result["salario_base"]) if result["salario_base"] else 0,
        "VLR_BONO": float(result["vlr_bono"]) if result["vlr_bono"] else 0,
        "SALARIO_ESPECIE": float(result["sal_especie"]) if result["sal_especie"] else 0,
        "EPS": result["eps"],
        "FONDO DE PENSIONES": result["afp"],
        "ES_SMLV": "SI" if result["es_smlv"] else "NO",
        "CON_BONO": "SI" if result["con_bono"] else "NO",
        "TIENE_AUX": "SI" if result["tiene_aux"] else "NO",
        "LINK_DRIVE": result.get("link_drive", ""),
        "RAZON_SOCIAL": current_user.get("razon_social", ""),
        "EMAIL_APORTANTE": current_user.get("email", ""),
    }
    
    return {
        "status": "success",
        "data": data_local
    }


@app.post("/api/v1/empleador/{id_contacto}/empleado/{id_empleado}/sync")
async def sincronizar_detalle_empleado(id_contacto: str, id_empleado: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Endpoint para sincronizar el detalle de un empleado específico desde Wolkvox.

    Reglas de Negocio - Sincronización de Empleados y Soft-Delete (Wolkvox):
    - Manejo de Rotación (Wolkvox): NUNCA aplicar Hard-Delete a un empleado que ya no viene en Wolkvox (estado "lost").
    - Se aplica Soft-Delete cambiando estado_empleado = 'RETIRADO'.
    - Un empleado en estado RETIRADO o En Mora SS no puede operar en el sistema.
    """
    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() not in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
        id_contacto = current_user["id_aportante"]
        
    id_contacto = str(id_contacto)
    id_empleado = str(id_empleado)
    cedula_real = id_empleado.split('_')[-1] if '_' in id_empleado else id_empleado
    
    query_admin = text("SELECT razon_social FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
    try:
        resultado_admin = db.execute(query_admin, {"id_aportante": id_contacto}).mappings().first()
        nombre_empleador = resultado_admin["razon_social"] if resultado_admin else id_contacto
    except Exception as e:
        db.rollback()
        logger.warning(f"Error consultando razon_social m_aportantes: {e}")
        nombre_empleador = id_contacto
    from core.wolkvox_sync import sync_aportante_from_wolkvox, sync_empleados_from_wolkvox
    
    # Paso A, B y C: Forzar la sincronización del aportante (Contacto) para capturar legacy data (carpeta_cliente)
    await sync_aportante_from_wolkvox(id_contacto, db)
    
    # Paso 3: Mantener cascada (Actualización Completa y Filtro Local Seguro)
    try:
        # 1. Sincronizamos TODOS los empleados sin el target_empleado_id para evitar que Wolkvox rompa el filtro
        empleados_limpios = await sync_empleados_from_wolkvox(id_contacto, nombre_empleador, db)
        
        # 2. Filtramos localmente el empleado específico buscando coincidencia exacta con ID_CONTRATO
        empleado_target = next((emp for emp in (empleados_limpios or []) if emp.get("ID_CONTRATO") == id_empleado), None)
        
    except Exception as e:
        logger.error(f"Error sync detalle empleado {id_empleado}: {e}", exc_info=True)
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error sinc. Wolkvox: {str(e)}")

    if not empleado_target:
        raise HTTPException(status_code=404, detail="El empleado no fue encontrado en el CRM tras la sincronización.")

    return {
        "status": "success",
        "data": empleado_target
    }


@app.post("/api/v1/empleador/{id_contacto}/sync-masivo")
async def sincronizar_masivo_empleador(id_contacto: str, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Endpoint de Sincronización Masiva:
    Evade la caché local de Supabase (m_empleados) y fuerza la consulta y sincronización de:
    1) El aportante (sync_aportante_from_wolkvox) para actualizar estado (mora, retiro, etc.).
    2) La plantilla completa de empleados (sync_empleados_from_wolkvox) sin target_empleado_id.
    """
    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() not in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
        id_contacto = str(current_user.get("id_aportante"))

    id_contacto = str(id_contacto).strip()

    from core.wolkvox_sync import sync_aportante_from_wolkvox, sync_empleados_from_wolkvox

    try:
        aportante_info = await sync_aportante_from_wolkvox(id_contacto, db)
    except Exception as e:
        logger.warning(f"Advertencia al sincronizar aportante {id_contacto}: {e}")
        aportante_info = None

    if aportante_info and aportante_info.get("razon_social"):
        razon_social = aportante_info.get("razon_social")
    else:
        q_admin = text("SELECT razon_social FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
        row = db.execute(q_admin, {"id_aportante": id_contacto}).mappings().first()
        razon_social = row["razon_social"] if row and row["razon_social"] else id_contacto

    try:
        empleados_limpios = await sync_empleados_from_wolkvox(id_contacto, razon_social, db)
    except Exception as e:
        logger.error(f"Error en sync-masivo para empleador {id_contacto}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en sincronización masiva desde Wolkvox: {str(e)}")

    return {
        "status": "success",
        "data": empleados_limpios
    }


class EnviarDesprendiblesRequest(BaseModel):
    periodo: str
    quincena: str
    contratos: List[str]

class CierreNominaRequest(BaseModel):
    periodo: str
    quincena: Union[int, str]
    id_contrato: str


@app.get("/api/v1/nomina/estado-cierre/{periodo}/{quincena}")
def obtener_estado_cierre(periodo: str, quincena: str, id_contrato: str = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Regla de Negocio - Candado de Nómina (Inmutabilidad y Cierre Granular):
    - Una nómina con estado 'CERRADA' en t_cierres_nomina es sagrada e inmutable.
    - El candado se aplica por EMPLEADO (id_contrato), NUNCA por empresa.
    """
    if not id_contrato:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de contrato válido para la consulta.")

    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() == models.RolUsuario.EMPLEADOR.value:
        check_emp = text("SELECT 1 FROM m_empleados WHERE id_contrato = :id_contrato AND id_aportante = :id_aportante")
        if not db.execute(check_emp, {"id_contrato": str(id_contrato), "id_aportante": str(current_user["id_aportante"])}).first():
            raise HTTPException(status_code=403, detail="Acceso denegado: el contrato consultado no pertenece a su empresa (Multi-Tenant).")

    check = text(
        "SELECT 1 FROM t_cierres_nomina WHERE id_contrato = :id_contrato AND periodo_liq = :periodo AND quincena_pago = :quincena")
    is_cerrado = db.execute(check, {"id_contrato": str(id_contrato), "periodo": periodo, "quincena": quincena}).first() is not None
    return {"cerrado": is_cerrado}


@app.post("/api/v1/nomina/cerrar")
def cerrar_nomina(payload: CierreNominaRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Regla de Negocio - Candado de Nómina (Cierre inmutable por empleado):
    - Inserta el registro de cierre para id_contrato, periodo_liq y quincena_pago en t_cierres_nomina.
    - Cualquier intento posterior de sobreescritura será rechazado.
    """
    if not payload.id_contrato:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de contrato válido para el cierre.")

    id_contrato_str = str(payload.id_contrato).strip()
    if not getattr(current_user, "es_vip", False) and str(current_user.get("rol", "")).upper() == models.RolUsuario.EMPLEADOR.value:
        check_emp = text("SELECT 1 FROM m_empleados WHERE id_contrato = :id_contrato AND id_aportante = :id_aportante")
        if not db.execute(check_emp, {"id_contrato": id_contrato_str, "id_aportante": str(current_user["id_aportante"])}).first():
            raise HTTPException(status_code=403, detail="Acceso denegado: el contrato que intenta cerrar no pertenece a su empresa (Multi-Tenant).")

    email = current_user.get("email", "desconocido")
    if email != "desconocido":
        email = email.lower().strip()

    check = text(
        "SELECT 1 FROM t_cierres_nomina WHERE id_contrato = :id_contrato AND periodo_liq = :periodo AND quincena_pago = :quincena")
    quincena_str = str(payload.quincena).strip()

    if db.execute(check, {"id_contrato": id_contrato_str, "periodo": payload.periodo, "quincena": quincena_str}).first():
        raise HTTPException(
            status_code=400, detail="La nómina ya está cerrada.")

    try:
        insert = text("""
            INSERT INTO t_cierres_nomina (id_contrato, periodo_liq, quincena_pago, cerrado_por)
            VALUES (:id_contrato, :periodo, :quincena, :email)
        """)
        db.execute(insert, {"id_contrato": id_contrato_str,
                   "periodo": payload.periodo, "quincena": quincena_str, "email": email})
        registrar_auditoria(
            db=db,
            current_user=current_user,
            tipo_accion="CIERRE_NOMINA",
            entidad_afectada=id_contrato_str,
            detalles={
                "id_contrato": id_contrato_str,
                "periodo": payload.periodo,
                "quincena": quincena_str
            }
        )
        db.commit()
        return {"status": "success", "message": "Nómina cerrada exitosamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en transacción: {str(e)}")


@app.delete("/api/v1/nomina/reabrir")
def reabrir_nomina(payload: CierreNominaRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Endpoint de Reapertura (Override):
    Permite a un usuario con rol SUPERADMIN o ADMINISTRADOR anular el candado de inmutabilidad
    y reabrir una nómina cerrada eliminando el registro en t_cierres_nomina.
    """
    rol = str(current_user.get("rol", "")).upper().strip()
    if rol not in ["SUPERADMIN", "ADMINISTRADOR"]:
        raise HTTPException(status_code=403, detail="Acceso denegado: solo SUPERADMIN o ADMINISTRADOR pueden reabrir nóminas cerradas.")

    email = str(current_user.get("email", "desconocido")).lower().strip()
    id_contrato_str = str(payload.id_contrato).strip()
    periodo_str = str(payload.periodo).strip()
    quincena_str = str(payload.quincena).strip()

    try:
        del_query = text("""
            DELETE FROM t_cierres_nomina
            WHERE id_contrato = :id_contrato AND periodo_liq = :periodo AND quincena_pago = :quincena
        """)
        db.execute(del_query, {
            "id_contrato": id_contrato_str,
            "periodo": periodo_str,
            "quincena": quincena_str
        })
        registrar_auditoria(
            db=db,
            current_user=current_user,
            tipo_accion="OVERRIDE_REAPERTURA",
            entidad_afectada=id_contrato_str,
            detalles={
                "id_contrato": id_contrato_str,
                "periodo": periodo_str,
                "quincena": quincena_str
            }
        )
        db.commit()
        return {"status": "success", "message": "Nómina reabierta exitosamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en transacción: {str(e)}")


@app.get("/api/v1/nomina/resumen/{periodo}/{quincena}")
async def obtener_resumen_nomina(periodo: str, quincena: str, id_aportante: str = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if getattr(current_user, "es_vip", False) or str(current_user.get("rol", "")).upper() in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
        aportante_seguro = id_aportante or current_user.get("id_aportante")
    else:
        aportante_seguro = current_user.get("id_aportante")

    if not aportante_seguro:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de aportante válido para la consulta.")

    id_aportante_str = str(aportante_seguro)

    query = text("""
        SELECT 
            e.id_contrato, e.nombre_empleado, e.cargo, e.tipo_contrato,
            n.neto_pagar, n.total_devengado, n.total_deducido,
            CASE WHEN c.id_cierre IS NOT NULL THEN TRUE ELSE FALSE END AS esta_cerrado
        FROM m_empleados e
        LEFT JOIN t_novedades n 
            ON e.id_contrato = n.id_contrato 
            AND n.periodo_liq = :periodo 
            AND n.quincena_pago = :quincena
        LEFT JOIN t_cierres_nomina c 
            ON e.id_contrato = c.id_contrato 
            AND c.periodo_liq = :periodo 
            AND c.quincena_pago = :quincena
        WHERE e.id_aportante = :id_aportante
          AND TRIM(e.estado_empleado) NOT IN ('RETIRADO', 'En Mora SS', 'UnicaAfiliacion')
    """)
    resultado = db.execute(query, {"periodo": periodo, "quincena": quincena,
                           "id_aportante": id_aportante_str}).mappings().all()

    if not resultado:
        raise HTTPException(
            status_code=404, detail="No se encontraron empleados activos.")

    resumen_empleados = []
    total_empresa_devengado = 0.0
    total_empresa_deducido = 0.0
    total_empresa_neto = 0.0

    for row in resultado:
        if row["neto_pagar"] is not None:
            estado = "LIQUIDADO"
            neto = float(row["neto_pagar"] or 0)
            devengado = float(row["total_devengado"] or 0)
            deducido = float(row["total_deducido"] or 0)

            total_empresa_devengado += devengado
            total_empresa_deducido += deducido
            total_empresa_neto += neto
        else:
            estado = "PENDIENTE"
            neto = 0.0

        resumen_empleados.append({
            "id_contrato": row["id_contrato"],
            "nombre": row["nombre_empleado"] or "Sin Nombre",
            "cargo": row["cargo"] or "",
            "tipo_contrato": row["tipo_contrato"] or "",
            "estado": estado,
            "neto_pagar": neto,
            "esta_cerrado": bool(row["esta_cerrado"])
        })

    total_cerrados = sum(1 for e in resumen_empleados if e["esta_cerrado"])
    total_empleados = len(resultado)
    todos_cerrados = (total_cerrados > 0 and total_cerrados == total_empleados) or (total_cerrados > 0)

    return {
        "status": "success",
        "totales": {
            "total_empresa_devengado": total_empresa_devengado,
            "total_empresa_deducido": total_empresa_deducido,
            "total_empresa_neto": total_empresa_neto,
            "total_empleados": total_empleados,
            "empleados_pendientes": sum(1 for e in resumen_empleados if e["estado"] == "PENDIENTE"),
            "total_cerrados": total_cerrados,
            "todos_cerrados": todos_cerrados
        },
        "empleados": resumen_empleados
    }


@app.post("/api/v1/liquidar")
def liquidar_nomina(payload: List[Dict[str, Any]] = Body(...), current_user: dict = Depends(get_current_user)):
    """
    Reglas de Negocio - Liquidación de Nómina y Cálculo UGPP (Tiempo Parcial / Salud):
    - Las horas extras NO suman al IBC.
    - Excepción única: para empleados de Tiempo Parcial que pagan EPS/salud, el IBC se fuerza obligatoriamente a 1 SMLV.
    """
    if not payload:
        return []

    for item in payload:
        periodo = str(item.get("PERIODO_PAGO", "QUINCENAL")).strip().upper()
        try:
            dias = float(item.get("DIAS_LABORADOS", 0) or 0)
        except ValueError:
            dias = 0

        if periodo == "QUINCENAL" and dias > 15:
            raise HTTPException(
                status_code=400, detail="Error de validación: Un contrato quincenal no puede superar los 15 días laborados.")
        elif periodo == "MENSUAL" and dias > 30:
            raise HTTPException(
                status_code=400, detail="Error de validación: Un contrato mensual no puede superar los 30 días laborados.")

    df_final = pd.DataFrame(payload)

    # --- 3. PARÁMETROS 2026 ---
    SMLV_2026 = 1750905
    SMLD_2026 = SMLV_2026 / 30
    PISO_TP_BONO = SMLD_2026 * (7/6)
    AUX_TTE_MES = 249095
    LIMITE_AUX = SMLV_2026 * 2
    HR_MES = 210
    PORCENTAJE_LEY = 0.04

    FACTORES = {'HED': 1.25, 'HEN': 1.75, 'HEDF': 2.05,
                'HENF': 2.55, 'RN': 0.35, 'RDN': 0.80, 'RNF': 1.15}

    df_final.columns = df_final.columns.str.strip().str.upper()

    # --- ASEGURAR COLUMNAS REQUERIDAS ---
    columnas_defaults = {
        'ES_SMLV': '',
        'CON_BONO': '',
        'TIENE_AUX': '',
        'TIPO_CONTRATO': 'TIEMPO COMPLETO',
        'ESTADO_EMPLEADO': 'ACTIVO',
        'PERIODO_PAGO': 'QUINCENAL',
        'DIAS_VACACIONES': 0,
        'DIAS_INCAPACIDAD': 0,
        'SALARIO_BASE': 0,
        'SALARIO_ESPECIE': 0,
        'VLR_BONO': 0,
        'EPS': '',
        'FONDO_PENSIONES': '',
        'DIAS_LABORADOS': 0,
        'HORAS_LABORADAS': 0,
        'PRESTAMOS': 0,
        'PRIMA_CALC': 0
    }
    for col, val in columnas_defaults.items():
        if col not in df_final.columns:
            df_final[col] = val

    # --- 4. NORMALIZACIÓN NUMÉRICA ---
    cols_limpiar = ['SALARIO_BASE', 'VLR_BONO',
                    'PRESTAMOS', 'SALARIO_ESPECIE', 'PRIMA_CALC']
    for col in cols_limpiar:
        def limpiar_valor(x):
            if pd.isnull(x):
                return 0.0
            if isinstance(x, (int, float)):
                return float(x)
            s = str(x).strip().replace('$', '')
            # Si el valor original desde Supabase trae .0 o .00 (ej. 80000.00), lo tratamos como float directo
            if '.' in s and s.rsplit('.', 1)[1].isdigit() and len(s.rsplit('.', 1)[1]) <= 2 and ',' not in s:
                try:
                    return float(s)
                except:
                    pass
            # Limpieza para inputs de frontend como "80.000" (miles)
            s = s.replace('.', '').replace(',', '')
            try:
                return float(s)
            except:
                return 0.0

        df_final[col] = df_final[col].apply(limpiar_valor)

    cols_num = cols_limpiar + ['DIAS_LABORADOS', 'HORAS_LABORADAS',
                               'DIAS_VACACIONES', 'DIAS_INCAPACIDAD'] + list(FACTORES.keys())
    cols_existentes = [col for col in cols_num if col in df_final.columns]
    df_final[cols_existentes] = df_final[cols_existentes].apply(
        pd.to_numeric, errors='coerce').fillna(0)

    # --- 5. & 6. LIQUIDACIÓN VECTORIZADA DE NÓMINA ---
    # A. Booleanos, Variables Base y ESTADO
    es_smlv = df_final['ES_SMLV'].astype(str).str.strip(
    ).str.upper().isin(['VERDADERO', 'TRUE', 'SI', '1'])
    con_bono = df_final['CON_BONO'].astype(str).str.strip(
    ).str.upper().isin(['VERDADERO', 'TRUE', 'SI', '1'])
    tiene_aux = df_final['TIENE_AUX'].astype(str).str.strip(
    ).str.upper().isin(['VERDADERO', 'TRUE', 'SI', 'SÍ', '1'])
    tipo_contrato = df_final['TIPO_CONTRATO'].astype(
        str).str.strip().str.upper()
    estado_empleado = df_final['ESTADO_EMPLEADO'].astype(
        str).str.strip().str.upper()
    periodo_pago = df_final['PERIODO_PAGO'].astype(str).str.strip().str.upper()

    # Distribución de Días
    d_vac = df_final['DIAS_VACACIONES']
    d_inc = df_final['DIAS_INCAPACIDAD']
    d_lab_total = np.where(df_final['HORAS_LABORADAS'] > 0,
                           df_final['HORAS_LABORADAS'] / 8, df_final['DIAS_LABORADOS'])

    dias_efectivos_trabajo = np.maximum(d_lab_total - d_vac - d_inc, 0)

    sal_base_raw = df_final['SALARIO_BASE']
    sal_especie_raw = df_final['SALARIO_ESPECIE']

    df_final['TOTAL_BASE_MENSUAL'] = np.where(
        tipo_contrato == "EMPLEADO INTERNO",
        sal_base_raw + sal_especie_raw,
        sal_base_raw
    )

    sal_base_input = df_final['TOTAL_BASE_MENSUAL']
    val_diario_propuesto = np.where(
        tipo_contrato == "TIEMPO PARCIAL", sal_base_input, sal_base_input / 30)

    val_diario_validado = np.where(
        (tipo_contrato == "TIEMPO PARCIAL") & (con_bono),
        np.maximum(val_diario_propuesto, PISO_TP_BONO),
        val_diario_propuesto
    )

    sal_base_mensual_equiv = val_diario_validado * 30

    # B. Estructura Salarial
    df_final['SAL_REF'] = np.where(es_smlv, SMLV_2026, sal_base_mensual_equiv)
    df_final['BONO_REF'] = np.where(con_bono, df_final['VLR_BONO'], 0)

    # C. Devengados
    valor_dia_total = df_final['SAL_REF'] / 30

    df_final['VAL_DIA_ESPECIE'] = np.where(
        tipo_contrato == "EMPLEADO INTERNO", sal_especie_raw / 30, 0)
    df_final['VAL_DIA_EFECTIVO'] = valor_dia_total - \
        df_final['VAL_DIA_ESPECIE']

    df_final['SUELDO_EFECTIVO_PAGADO'] = df_final['VAL_DIA_EFECTIVO'] * \
        dias_efectivos_trabajo
    df_final['SALARIO_ESPECIE_MES'] = df_final['VAL_DIA_ESPECIE'] * \
        dias_efectivos_trabajo
    df_final['SUELDO_TRABAJADO'] = df_final['SUELDO_EFECTIVO_PAGADO']

    # 2. Pago Vacaciones e Incapacidades
    df_final['VALOR_VACACIONES'] = valor_dia_total * d_vac
    pago_inc_diario = np.maximum(valor_dia_total * 0.6667, SMLD_2026)
    df_final['VALOR_INCAPACIDAD'] = pago_inc_diario * d_inc

    # 4. Bonos y Extras
    df_final['VALOR_BONO'] = np.where(
        tipo_contrato == "TIEMPO PARCIAL",
        df_final['BONO_REF'] * d_lab_total,
        (df_final['BONO_REF'] / 30) * d_lab_total
    )

    valor_hora = df_final['SAL_REF'] / HR_MES
    df_final['TOTAL_EXTRAS'] = 0
    for cod, factor in FACTORES.items():
        vlr_col = f'VLR_{cod}'
        if cod in df_final.columns:
            df_final[vlr_col] = df_final[cod] * valor_hora * factor
            df_final['TOTAL_EXTRAS'] += df_final[vlr_col]
        else:
            df_final[vlr_col] = 0

    # 5. Auxilio de Transporte
    bono_mensual_tope = np.where(
        tipo_contrato == "TIEMPO PARCIAL", df_final['BONO_REF'] * 30, df_final['BONO_REF'])
    cond_aux = tiene_aux & (
        (df_final['SAL_REF'] + bono_mensual_tope) <= LIMITE_AUX)
    df_final['VAL_AUX_TTE'] = np.where(
        cond_aux, (AUX_TTE_MES / 30) * dias_efectivos_trabajo, 0)

    ibc_tiempo_completo = np.maximum(
        df_final['SUELDO_TRABAJADO'] + df_final['SALARIO_ESPECIE_MES'] +
        df_final['VALOR_VACACIONES'] +
        df_final['VALOR_INCAPACIDAD'] + df_final['TOTAL_EXTRAS'],
        (SMLV_2026 / 30) * d_lab_total
    )

    dias_proyectados = np.where(
        periodo_pago == 'QUINCENAL', d_lab_total * 2, d_lab_total)
    cond_parcial = [dias_proyectados <= 7, dias_proyectados <=
                    14, dias_proyectados <= 21, dias_proyectados > 21]
    opciones_parcial_mes = [SMLV_2026 * 0.25,
                            SMLV_2026 * 0.50, SMLV_2026 * 0.75, SMLV_2026]

    ibc_parcial_proporcional = np.where(
        periodo_pago == 'QUINCENAL',
        np.select(cond_parcial, opciones_parcial_mes) / 2,
        np.select(cond_parcial, opciones_parcial_mes)
    )

    eps_exento = df_final.get('EPS', '').astype(
        str).str.strip().str.upper().str.contains('N/A', na=False)
    fondo_pensiones_exento = df_final.get('FONDO_PENSIONES', '').astype(
        str).str.strip().str.upper().str.contains('N/A', na=False)

    cond_tiempo_parcial_rigido = (
        tipo_contrato == "TIEMPO PARCIAL") & (~eps_exento)

    # --- EXCEPCIÓN TIEMPO PARCIAL: IBC PILA ---
    # Los empleados de Tiempo Parcial que no están exentos de EPS cotizan sobre 1 SMLV completo.
    df_final['IBC_PILA'] = np.where(
        cond_tiempo_parcial_rigido,
        SMLV_2026,
        np.where(tipo_contrato == "TIEMPO PARCIAL",
                 ibc_parcial_proporcional, ibc_tiempo_completo)
    )

    # --- CÁLCULO DE DEDUCCIONES ---
    # Salud y Pensión (4% cada uno)
    df_final['SALUD_4'] = np.where(
        eps_exento, 0, df_final['IBC_PILA'] * PORCENTAJE_LEY)
    df_final['PENSION_4'] = np.where(
        fondo_pensiones_exento, 0, df_final['IBC_PILA'] * PORCENTAJE_LEY)

    # Fraccionamiento de Deducciones para Periodo Quincenal
    # Regla: Solo se fracciona para Tiempo Parcial que NO están exentos de EPS (IBC base de SMLV completo)
    es_quincenal_fraccion = (periodo_pago == 'QUINCENAL') & (
        tipo_contrato == 'TIEMPO PARCIAL') & (~eps_exento)
    df_final['SALUD_4'] = np.where(
        es_quincenal_fraccion, df_final['SALUD_4'] / 2.0, df_final['SALUD_4'])
    df_final['PENSION_4'] = np.where(
        es_quincenal_fraccion, df_final['PENSION_4'] / 2.0, df_final['PENSION_4'])

    # Redondeo PILA al múltiplo de 100 superior como paso final
    df_final['SALUD_4'] = df_final['SALUD_4'].apply(
        lambda x: math.ceil(x / 100.0) * 100 if pd.notnull(x) and x > 0 else 0)
    df_final['PENSION_4'] = df_final['PENSION_4'].apply(
        lambda x: math.ceil(x / 100.0) * 100 if pd.notnull(x) and x > 0 else 0)

    # F. Totales Finales (Modificado para incluir PRIMA_CALC)
    df_final['SUELDO_PAGADO'] = df_final['SUELDO_TRABAJADO'] + \
        df_final['VALOR_VACACIONES'] + df_final['VALOR_INCAPACIDAD']

    df_final['TOTAL_DEVENGADO'] = (
        df_final['SUELDO_PAGADO'] +
        df_final['SALARIO_ESPECIE_MES'] +
        df_final['VALOR_BONO'] +
        df_final['TOTAL_EXTRAS'] +
        df_final['VAL_AUX_TTE'] +
        df_final['PRIMA_CALC']
    )

    df_final['TOTAL_DEDUCIDO'] = df_final['SALUD_4'] + \
        df_final['PENSION_4'] + df_final['PRESTAMOS']
    df_final['NETO_PAGAR'] = df_final['TOTAL_DEVENGADO'] - \
        df_final['TOTAL_DEDUCIDO'] - df_final['SALARIO_ESPECIE_MES']

    # --- 7. VALIDACIÓN DE ESTADO DEL EMPLEADO ---
    es_retirado = estado_empleado == 'RETIRADO'

    cols_a_ceros = [
        'SUELDO_PAGADO', 'SUELDO_EFECTIVO_PAGADO', 'SALARIO_ESPECIE_MES',
        'VALOR_BONO', 'TOTAL_EXTRAS', 'VAL_AUX_TTE', 'PRESTAMOS', 'PRIMA_CALC',
        'IBC_PILA', 'SALUD_4', 'PENSION_4', 'TOTAL_DEVENGADO', 'TOTAL_DEDUCIDO', 'NETO_PAGAR',
        'VALOR_VACACIONES', 'VALOR_INCAPACIDAD', 'VLR_HED', 'VLR_HEN', 'VLR_HEDF',
        'VLR_HENF', 'VLR_RN', 'VLR_RDN', 'VLR_RNF'
    ]
    for col in cols_a_ceros:
        df_final[col] = np.where(es_retirado, 0, df_final[col])

    cols_monetarias = [
        'TOTAL_BASE_MENSUAL', 'SAL_REF', 'BONO_REF', 'VAL_DIA_ESPECIE', 'VAL_DIA_EFECTIVO',
        'SUELDO_EFECTIVO_PAGADO', 'SALARIO_ESPECIE_MES', 'SUELDO_TRABAJADO',
        'VALOR_VACACIONES', 'VALOR_INCAPACIDAD', 'VALOR_BONO', 'TOTAL_EXTRAS',
        'VAL_AUX_TTE', 'IBC_PILA', 'SALUD_4', 'PENSION_4', 'SUELDO_PAGADO',
        'TOTAL_DEVENGADO', 'TOTAL_DEDUCIDO', 'NETO_PAGAR', 'PRESTAMOS', 'PRIMA_CALC',
        'VLR_HED', 'VLR_HEN', 'VLR_HEDF', 'VLR_HENF', 'VLR_RN', 'VLR_RDN', 'VLR_RNF'
    ]
    for col in cols_monetarias:
        if col in df_final.columns:
            df_final[col] = df_final[col].round(0).fillna(0).astype(int)

    # Reemplazar NaN e infinitos por None para evitar problemas de serialización JSON en FastAPI
    df_final = df_final.replace([np.nan, np.inf, -np.inf], None)

    return df_final.to_dict(orient="records")


@app.get("/api/v1/nomina/desprendible-pdf/{id_contrato}/{periodo_liq}/{quincena_pago}")
def descargar_desprendible_pdf(id_contrato: str, periodo_liq: str, quincena_pago: str, db: Session = Depends(get_db)):
    """
    Regla de Infraestructura - Discos Efímeros en Render (ReportLab / PDF en Memoria):
    - PROHIBIDO guardar archivos físicos de PDF en disco. Todo PDF debe generarse en memoria (BytesIO / bytes) y devolverse en Response.
    """
    query = text("""
        SELECT e.*, n.*, 
               n.salario_base as salario_base_novedad,
               n.vlr_bono as vlr_bono_novedad,
               n.sal_especie as sal_especie_novedad,
               n.prestamos as prestamos_novedad,
               a.razon_social as razon_social,
               a.tipo_documento as tipo_documento,
               a.tipo_empleador as tipo_empleador,
               a.id_aportante as id_aportante
        FROM m_empleados e
        JOIN t_novedades n ON e.id_contrato = n.id_contrato
        LEFT JOIN m_aportantes a ON e.id_aportante = a.id_aportante
        WHERE e.id_contrato = :id_contrato
          AND n.periodo_liq = :periodo
          AND n.quincena_pago = :quincena
    """)
    row = db.execute(query, {"id_contrato": id_contrato,
                     "periodo": periodo_liq, "quincena": quincena_pago}).mappings().first()

    if not row:
        raise HTTPException(
            status_code=404, detail="Liquidación no encontrada para este contrato y periodo.")

    row_dict = {k.upper(): v for k, v in dict(row).items()}

    # Priorizar variables variables congeladas en la novedad sobre las del CRM (m_empleados)
    if 'SALARIO_BASE_NOVEDAD' in row_dict and row_dict['SALARIO_BASE_NOVEDAD'] is not None:
        salario_base_raw = row_dict.get('SALARIO_BASE_NOVEDAD', 0)
        try:
            row_dict['SALARIO_BASE'] = float(
                salario_base_raw) if salario_base_raw is not None else 0.0
        except ValueError:
            row_dict['SALARIO_BASE'] = 0.0

    if 'VLR_BONO_NOVEDAD' in row_dict and row_dict['VLR_BONO_NOVEDAD'] is not None:
        bono_raw = row_dict.get('VLR_BONO_NOVEDAD', 0)
        try:
            row_dict['VLR_BONO'] = float(
                bono_raw) if bono_raw is not None else 0.0
        except ValueError:
            row_dict['VLR_BONO'] = 0.0

    if 'SAL_ESPECIE_NOVEDAD' in row_dict and row_dict['SAL_ESPECIE_NOVEDAD'] is not None:
        especie_raw = row_dict.get('SAL_ESPECIE_NOVEDAD', 0)
        try:
            row_dict['SALARIO_ESPECIE'] = float(
                especie_raw) if especie_raw is not None else 0.0
        except ValueError:
            row_dict['SALARIO_ESPECIE'] = 0.0

    if 'PRESTAMOS_NOVEDAD' in row_dict and row_dict['PRESTAMOS_NOVEDAD'] is not None:
        prestamo_raw = row_dict.get('PRESTAMOS_NOVEDAD', 0)
        try:
            row_dict['PRESTAMOS'] = float(
                prestamo_raw) if prestamo_raw is not None else 0.0
        except ValueError:
            row_dict['PRESTAMOS'] = 0.0

    try:
        # Re-liquidamos en vuelo para recuperar los campos detallados que no se guardan explícitamente en BD
        resultado_liquidado = liquidar_nomina([row_dict], {})
        if resultado_liquidado:
            resultado_final = resultado_liquidado[0]
            # Mezclar metadatos necesarios
            resultado_final['RAZON_SOCIAL'] = row_dict.get(
                'RAZON_SOCIAL', 'SIN EMPRESA')
            resultado_final['TIPO_DOCUMENTO'] = row_dict.get(
                'TIPO_DOCUMENTO', 'NIT')
            resultado_final['TIPO_EMPLEADOR'] = row_dict.get('TIPO_EMPLEADOR', '')
            resultado_final['ID_APORTANTE'] = row_dict.get('ID_APORTANTE', '')
            resultado_final['PERIODO_LIQ'] = row_dict.get('PERIODO_LIQ')
            resultado_final['QUINCENA_PAGO'] = row_dict.get('QUINCENA_PAGO')
            resultado_final['OBSERVACIONES'] = row_dict.get('OBSERVACIONES')
            resultado_final['CARGO'] = row_dict.get('CARGO', 'NO ASIGNADO')
            resultado_final['TIPO_CONTRATO'] = row_dict.get('TIPO_CONTRATO', '')
            resultado_final['T_ID_EMPLEADO'] = row_dict.get('T_ID_EMPLEADO', '')
            resultado_final['ID_EMPLEADO'] = row_dict.get('ID_EMPLEADO', '')
            resultado_final['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
            return generar_comprobante(resultado_final)
    except Exception:
        pass
        # Fallback si falla liquidar_nomina, aseguramos SAL_REF para evitar error en divisor
    if not row_dict.get('SAL_REF'):
        row_dict['SAL_REF'] = 1750905 if str(row_dict.get('ES_SMLV')).upper() in [
            'SI', 'TRUE', '1'] else row_dict.get('SALARIO_BASE', 0)
    row_dict['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
    return generar_comprobante(row_dict)


@app.post("/api/v1/comprobante/generar")
def generar_comprobante(row: Dict[str, Any] = Body(...)):
    """
    Regla de Infraestructura - Discos Efímeros en Render (Comprobante PDF en Memoria):
    - Genera el comprobante de nómina en memoria sin escribir en disco físico.
    """
    
    # Inyectar tipo_empleador si no viene en el payload (caso frontend directo)
    if not row.get("tipo_empleador") and not row.get("TIPO_EMPLEADOR"):
        id_aportante = row.get("ID_APORTANTE") or row.get("id_aportante")
        if id_aportante:
            db_session = SessionLocal()
            try:
                aportante = db_session.query(models.Aportante).filter(models.Aportante.id_aportante == id_aportante).first()
                row["tipo_empleador"] = aportante.tipo_empleador if aportante else ""
            except Exception as e:
                pass
            finally:
                db_session.close()

    HR_MES = 210
    factores_dict = {'HED': 1.25, 'HEN': 1.75, 'HEDF': 2.05,
                     'HENF': 2.55, 'RN': 0.35, 'RDN': 0.80, 'RNF': 1.15}

    periodo_liq = formatear_periodo(row.get('PERIODO_LIQ') or 'SIN PERIODO')
    quincena_pago = str(row.get('QUINCENA_PAGO') or "").strip().upper()

    if quincena_pago in ['1', 'Q1']:
        texto_periodo = f"Primera Quincena de {periodo_liq}"
    elif quincena_pago in ['2', 'Q2']:
        texto_periodo = f"Segunda Quincena de {periodo_liq}"
    elif quincena_pago in ['M', 'MENSUAL']:
        texto_periodo = f"Mensualidad de {periodo_liq}"
    else:
        texto_periodo = periodo_liq

    id_empleado = str(row.get('ID_EMPLEADO') or 'SIN_EMPLEADO').strip()

    sal_ref_fila = forzar_numero(row.get('SAL_REF', 0))
    v_hora_fila = sal_ref_fila / HR_MES

    tipo_emp = str(row.get("tipo_empleador") or row.get("TIPO_EMPLEADOR") or "").strip().lower()
    texto_tipo_persona = "PERSONA NATURAL" if tipo_emp == "hogar" else "PERSONA JURÍDICA"

    datos_emp = {
        'nombre': str(row.get('RAZON_SOCIAL') or 'EMPRESA NO ENCONTRADA'),
        'nit': str(row.get('ID_APORTANTE') or '000.000.000-0'),
        'tipo': texto_tipo_persona
    }

    pdf = ComprobantePDF(datos_emp, texto_periodo)
    pdf.add_page()

    # --- BLOQUE INFORMACIÓN EMPLEADO ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 7, f"INFORMACIÓN DEL TRABAJADOR",
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font('helvetica', '', 10)
    pdf.ln(2)
    pdf.cell(95, 6, f"Nombre: {row.get('NOMBRE_EMPLEADO') or ''}")
    pdf.cell(60, 6, f"Tipo Contrato: {row.get('TIPO_CONTRATO') or ''}")
    pdf.cell(50, 6, f"Tipo ID: {row.get('T_ID_EMPLEADO') or ''}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    cargo_val = str(row.get('CARGO') or row.get('CARGO_DESEMPENEADO') or 'NO ASIGNADO').strip()
    pdf.cell(95, 6, f"Cargo: {cargo_val}")
    total_dias = forzar_numero(row.get('DIAS_LABORADOS', 0))
    pdf.cell(60, 6, f"Días/Horas Liq: {total_dias:.1f}")
    pdf.cell(50, 6, f"ID: {id_empleado}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(5)

    # --- TABLA DE PAGOS ---
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(100, 8, "DETALLE DE CONCEPTO", border=1, align='C', fill=True)
    pdf.cell(45, 8, "DEVENGADO", border=1, align='C', fill=True)
    pdf.cell(45, 8, "DEDUCIDO", border=1, align='C',
             fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font('helvetica', '', 10)

    # --- 1. CONCEPTOS DE TIEMPO Y SALARIO ---
    d_vac = forzar_numero(row.get('DIAS_VACACIONES', 0))
    d_inc = forzar_numero(row.get('DIAS_INCAPACIDAD', 0))
    d_trab = np.maximum(total_dias - d_vac - d_inc, 0)

    label_sueldo = "Sueldo Efectivo" if forzar_numero(
        row.get('SAL_ESPECIE_PAGADO', 0)) > 0 else "Sueldo por Días Trabajados"

    val_vacaciones = float(row.get('VALOR_VACACIONES', 0) or 0)
    dias_vac = float(row.get('DIAS_VACACIONES', 0) or 0)
    val_incapacidad = float(row.get('VALOR_INCAPACIDAD', 0) or 0)
    dias_inc = float(row.get('DIAS_INCAPACIDAD', 0) or 0)

    conceptos_fijos = [
        (f"{label_sueldo} ({d_trab:.0f} días)", 'SUELDO_EFECTIVO_PAGADO'),
        (f"Salario en Especie ({d_trab:.0f} días)", 'SALARIO_ESPECIE_MES')
    ]

    if val_vacaciones > 0:
        conceptos_fijos.append(
            (f"Vacaciones ({dias_vac:.0f} días)", 'VALOR_VACACIONES'))

    if val_incapacidad > 0:
        conceptos_fijos.append(
            (f"Incapacidades ({dias_inc:.0f} días)", 'VALOR_INCAPACIDAD'))

    conceptos_fijos.extend([
        ("Bono No Salarial", 'VALOR_BONO'),
        ("Auxilio de Transporte", 'VAL_AUX_TTE'),
        ("Prima de Servicios", 'PRIMA_CALC')
    ])

    for desc, col in conceptos_fijos:
        val = forzar_numero(row.get(col, 0))
        if val > 0:
            pdf.cell(100, 7, desc, border='LR')
            pdf.cell(45, 7, f"{val:,.0f}", border='LR', align='R')
            pdf.cell(45, 7, "0", border='LR', align='R',
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 2. DETALLE DE EXTRAS
    for cod, factor in factores_dict.items():
        cant = forzar_numero(row.get(cod, 0))
        if cant > 0:
            monto = float(cant * v_hora_fila * factor)
            pdf.cell(
                100, 7, f"{NOMBRES_EXTRAS.get(cod, cod)} ({cant} Hr)", border='LR')
            pdf.cell(45, 7, f"{monto:,.0f}", border='LR', align='R')
            pdf.cell(45, 7, "0", border='LR', align='R',
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- 3. DEDUCCIONES ---
    deducciones = [
        ("Aporte Salud (4%)", 'SALUD_4'),
        ("Aporte Pensión (4%)", 'PENSION_4'),
        ("Descuento para el Período", 'PRESTAMOS'),
        ("Salario Especie (Recibido)", 'SALARIO_ESPECIE_MES')
    ]

    for desc, col in deducciones:
        val = forzar_numero(row.get(col, 0))
        if val > 0:
            pdf.cell(100, 7, desc, border='LR')
            pdf.cell(45, 7, "0", border='LR', align='R')
            pdf.cell(45, 7, f"{val:,.0f}", border='LR',
                     align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # LÍNEA FINAL DE LA TABLA
    pdf.cell(190, 0, "", border='T', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # TOTALES
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(100, 8, "TOTALES", border=1, align='R', fill=True)
    pdf.cell(45, 8, f"{forzar_numero(row.get('TOTAL_DEVENGADO', 0)):,.0f}",
             border=1, align='R', fill=True)
    pdf.cell(45, 8, f"{forzar_numero(row.get('TOTAL_DEDUCIDO', 0)):,.0f}",
             border=1, align='R', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # NETO A PAGAR
    pdf.ln(4)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(145, 10, "NETO A PAGAR:", align='R')
    pdf.set_text_color(0, 50, 150)
    pdf.cell(45, 10, f"${forzar_numero(row.get('NETO_PAGAR', 0)):,.0f}",
             border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # --- OBSERVACIONES ---
    observaciones = (row.get("OBSERVACIONES") or "").strip()
    if observaciones:
        pdf.ln(5)
        pdf.set_font('helvetica', 'B', 9)
        pdf.cell(0, 5, "Observaciones:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font('helvetica', '', 9)
        pdf.multi_cell(0, 5, observaciones)

    # --- FIRMAS ---
    pdf.ln(17)
    y_firma = pdf.get_y()
    pdf.line(25, y_firma, 85, y_firma)
    pdf.line(125, y_firma, 185, y_firma)
    pdf.ln(1)
    pdf.set_font('helvetica', '', 8)
    pdf.cell(95, 3, "Firma del Trabajador", align='C')
    pdf.cell(95, 3, "Firma Autorizada", align='C',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(95, 3, "(Recibí Conforme)", align='C')
    pdf.cell(95, 3, "Empleador / Sello", align='C',
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- NOTAS PIE DE PÁGINA ---
    pdf.ln(10)
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    ibc_val = forzar_numero(row.get('IBC_PILA', 0))

    pdf.cell(0, 4, f"* Base de Cotización (IBC): ${ibc_val:,.0f}",
             align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.ln(3)
    pdf.cell(0, 4, "Generado por UNIFIKA Nómina Cloud.",
             align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_text_color(0, 0, 255)
    pdf.cell(0, 4, "https://unifika.co", align='C',
             link="https://unifika.co", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    pdf_bytes = bytes(pdf.output())

    id_contrato = str(row.get('ID_CONTRATO') or 'SIN_CONTRATO')
    periodo_liq_raw = str(row.get('PERIODO_LIQ') or 'SIN_PERIODO')
    quincena_pago_raw = str(row.get('QUINCENA_PAGO') or '')

    periodo_seguro = str(periodo_liq_raw).replace(" ", "_").upper()
    quincena_segura = str(quincena_pago_raw).replace(" ", "_").upper()

    if quincena_segura:
        nombre_archivo = f"Desprendible_{id_contrato}_{periodo_seguro}_{quincena_segura}.pdf"
    else:
        nombre_archivo = f"Desprendible_{id_contrato}_{periodo_seguro}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={'Content-Disposition': f'attachment; filename={nombre_archivo}'}
    )


@app.post("/api/v1/nomina/enviar-desprendibles")
def enviar_desprendibles(payload: EnviarDesprendiblesRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Envía los desprendibles en memoria vía Resend.
    """
    email_dest = str(current_user.get("email", "")).strip()
    if not email_dest or email_dest.lower() == "desconocido":
        raise HTTPException(status_code=400, detail="El usuario actual no tiene un correo válido.")

    if not resend.api_key:
        raise HTTPException(status_code=500, detail="La API Key de Resend no está configurada.")

    mail_from = os.environ.get("MAIL_FROM", "nomina@unifika.co")
    
    try:
        for id_contrato in payload.contratos:
            query = text("""
                SELECT e.*, n.*, 
                       n.salario_base as salario_base_novedad,
                       n.vlr_bono as vlr_bono_novedad,
                       n.sal_especie as sal_especie_novedad,
                       n.prestamos as prestamos_novedad,
                       a.razon_social as razon_social,
                       a.tipo_documento as tipo_documento,
                       a.tipo_empleador as tipo_empleador,
                       a.id_aportante as id_aportante
                FROM m_empleados e
                JOIN t_novedades n ON e.id_contrato = n.id_contrato
                LEFT JOIN m_aportantes a ON e.id_aportante = a.id_aportante
                WHERE e.id_contrato = :id_contrato
                  AND n.periodo_liq = :periodo
                  AND n.quincena_pago = :quincena
            """)
            row = db.execute(query, {"id_contrato": id_contrato, "periodo": payload.periodo, "quincena": payload.quincena}).mappings().first()
                             
            if not row:
                continue
                
            row_dict_raw = {k.upper(): v for k, v in dict(row).items()}
            
            def safe_num(val):
                return float(val) if val is not None else 0.0

            row_dict = {
                'RAZON_SOCIAL': row_dict_raw.get('RAZON_SOCIAL', 'SIN EMPRESA') or 'SIN EMPRESA',
                'TIPO_DOCUMENTO': row_dict_raw.get('TIPO_DOCUMENTO', 'NIT') or 'NIT',
                'ID_APORTANTE': row_dict_raw.get('ID_APORTANTE', ''),
                'NOMBRE_EMPLEADO': row_dict_raw.get('NOMBRE_EMPLEADO', 'Empleado') or 'Empleado',
                'ID_EMPLEADO': row_dict_raw.get('ID_EMPLEADO', ''),
                'T_ID_EMPLEADO': row_dict_raw.get('T_ID_EMPLEADO', ''),
                'CARGO': row_dict_raw.get('CARGO', 'NO ASIGNADO') or 'NO ASIGNADO',
                'TIPO_CONTRATO': row_dict_raw.get('TIPO_CONTRATO', ''),
                'ESTADO_EMPLEADO': row_dict_raw.get('ESTADO_EMPLEADO', 'ACTIVO'),
                'PERIODO_PAGO': row_dict_raw.get('PERIODO_PAGO', 'QUINCENAL'),
                'PERIODO_LIQ': row_dict_raw.get('PERIODO_LIQ', ''),
                'QUINCENA_PAGO': row_dict_raw.get('QUINCENA_PAGO', ''),
                'OBSERVACIONES': row_dict_raw.get('OBSERVACIONES', ''),
                'EPS': row_dict_raw.get('EPS', ''),
                'FONDO_PENSIONES': row_dict_raw.get('AFP', row_dict_raw.get('FONDO_PENSIONES', '')),
                'ES_SMLV': row_dict_raw.get('ES_SMLV', ''),
                'CON_BONO': row_dict_raw.get('CON_BONO', ''),
                'TIENE_AUX': row_dict_raw.get('TIENE_AUX', ''),
                
                'SALARIO_BASE': safe_num(row_dict_raw.get('SALARIO_BASE_NOVEDAD', row_dict_raw.get('SALARIO_BASE'))),
                'VALOR_BONO': safe_num(row_dict_raw.get('VLR_BONO_NOVEDAD', row_dict_raw.get('VLR_BONO'))),
                'VLR_BONO': safe_num(row_dict_raw.get('VLR_BONO_NOVEDAD', row_dict_raw.get('VLR_BONO'))),
                'SALARIO_ESPECIE': safe_num(row_dict_raw.get('SAL_ESPECIE_NOVEDAD', row_dict_raw.get('SAL_ESPECIE'))),
                'SAL_ESPECIE': safe_num(row_dict_raw.get('SAL_ESPECIE_NOVEDAD', row_dict_raw.get('SAL_ESPECIE'))),
                
                'DIAS_LABORADOS': safe_num(row_dict_raw.get('DIAS_LABORADOS')),
                'HORAS_LABORADAS': safe_num(row_dict_raw.get('HORAS_LABORADAS')),
                'DIAS_VACACIONES': safe_num(row_dict_raw.get('DIAS_VACACIONES')),
                'DIAS_INCAPACIDAD': safe_num(row_dict_raw.get('DIAS_INCAPACIDAD')),
                'PRESTAMOS': safe_num(row_dict_raw.get('PRESTAMOS_NOVEDAD', row_dict_raw.get('PRESTAMOS'))),
                'PRIMA_CALC': safe_num(row_dict_raw.get('PRIMA_CALC')),
                
                'HED': safe_num(row_dict_raw.get('HED')),
                'HEN': safe_num(row_dict_raw.get('HEN')),
                'HEDF': safe_num(row_dict_raw.get('HEDF')),
                'HENF': safe_num(row_dict_raw.get('HENF')),
                'RN': safe_num(row_dict_raw.get('RN')),
                'RDN': safe_num(row_dict_raw.get('RDN')),
                'RNF': safe_num(row_dict_raw.get('RNF')),
                
                'IBC_PILA': safe_num(row_dict_raw.get('IBC_PILA')),
                'SALUD_4': safe_num(row_dict_raw.get('SALUD_4')),
                'PENSION_4': safe_num(row_dict_raw.get('PENSION_4')),
                'TOTAL_DEVENGADO': safe_num(row_dict_raw.get('TOTAL_DEVENGADO')),
                'TOTAL_DEDUCIDO': safe_num(row_dict_raw.get('TOTAL_DEDUCIDO')),
                'NETO_PAGAR': safe_num(row_dict_raw.get('NETO_PAGAR'))
            }
            
            row_dict['SAL_REF'] = 1750905 if str(row_dict.get('ES_SMLV')).upper() in ['SI', 'TRUE', '1'] else row_dict.get('SALARIO_BASE', 0)
            
            # Re-liquidamos en vuelo para recuperar variables temporales (ej. TOTAL_EXTRAS)
            try:
                res_liq = liquidar_nomina([row_dict], {})
                if res_liq:
                    res_final = res_liq[0]
                    for k in ['RAZON_SOCIAL', 'TIPO_DOCUMENTO', 'TIPO_EMPLEADOR', 'ID_APORTANTE', 'NOMBRE_EMPLEADO', 'ID_EMPLEADO', 'T_ID_EMPLEADO', 'CARGO', 'TIPO_CONTRATO', 'PERIODO_LIQ', 'QUINCENA_PAGO', 'OBSERVACIONES']:
                        res_final[k] = row_dict.get(k, '')
                    row_dict = res_final
            except Exception as eliq:
                pass

            row_dict['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
            response_pdf = generar_comprobante(row_dict)
            pdf_bytes = response_pdf.body
            
            headers = response_pdf.headers
            content_disposition = headers.get("content-disposition", "")
            nombre_archivo = "Desprendible.pdf"
            if "filename=" in content_disposition:
                nombre_archivo = content_disposition.split("filename=")[-1].strip().strip('"')
            
            nombre_empleado = row_dict.get('NOMBRE_EMPLEADO', 'Empleado')
            periodo_texto = payload.periodo
            
            resend.Emails.send({
                "from": mail_from,
                "to": email_dest,
                "subject": f"Desprendible de Nómina - {nombre_empleado} - {periodo_texto}",
                "html": f"<p>Adjunto encontrarás el desprendible de pago de {nombre_empleado} para el periodo {periodo_texto}.</p>",
                "attachments": [
                    {
                        "filename": nombre_archivo,
                        "content": list(pdf_bytes)
                    }
                ]
            })
            
        return {"status": "success", "message": "Desprendibles enviados correctamente"}
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error al enviar desprendibles: {e}")
        raise HTTPException(status_code=500, detail=f"Error al enviar desprendibles. Por favor, intente de nuevo. Detalle: {str(e)}")

@app.post("/api/v1/historico/guardar")
def guardar_historico(payload: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(...), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    """
    Regla de Negocio - Candado de Nómina (Inmutabilidad de Nómina y Cierre Granular):
    - Una nómina con estado 'CERRADA' en t_cierres_nomina es sagrada e inmutable.
    - Antes de guardar histórico, verifica que el contrato no esté en estado CERRADA. Si lo está, rechaza con HTTP 403.
    """
    if not payload:
        return {"status": "success", "message": "No hay datos para guardar."}

    if isinstance(payload, dict):
        payload = [payload]

    df_entrada = pd.DataFrame(payload)
    df_entrada.columns = df_entrada.columns.str.strip().str.upper()

    # 1. Asegurar columnas de periodo y quincena
    if 'PERIODO_LIQ' not in df_entrada.columns or 'QUINCENA_PAGO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener las claves 'PERIODO_LIQ' y 'QUINCENA_PAGO'."}

    periodo_check = str(df_entrada.iloc[0]['PERIODO_LIQ']).strip()
    quincena_check = str(df_entrada.iloc[0]['QUINCENA_PAGO']).strip()

    contratos_afectados = df_entrada['ID_CONTRATO'].dropna().unique().tolist()
    if contratos_afectados:
        contratos_sql = ', '.join([f"'{str(c)}'" for c in contratos_afectados])
        check_cierre_query = text(f"""
            SELECT 1 FROM t_cierres_nomina
            WHERE id_contrato IN ({contratos_sql}) AND periodo_liq = :periodo AND quincena_pago = :quincena
        """)
        if db.execute(check_cierre_query, {"periodo": periodo_check, "quincena": quincena_check}).first():
            raise HTTPException(
                status_code=403, detail="Operación denegada. La nómina para este periodo ya se encuentra CERRADA y NO se puede modificar.")

    # 2. Limpieza de entrada: Solo registros únicos por contrato
    if 'ID_CONTRATO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener 'ID_CONTRATO'."}

    df_entrada = df_entrada.drop_duplicates(
        subset=['ID_CONTRATO'], keep='last')

    # 3. Preparar la inserción de Novedades (Histórico)
    # Se eliminaron los UPSERT colaterales a m_aportantes y m_empleados para evitar sobreescrituras con NULL

    upsert_query = text("""
        INSERT INTO t_novedades (
            id_contrato, periodo_liq, quincena_pago, generar_nomina, salario_base,
            dias_laborados, horas_laboradas, dias_vacaciones, dias_incapacidad,
            prestamos, prima_calc, hed, hen, hedf, henf, rn, rdn, rnf, observaciones,
            ibc_pila, salud_4, pension_4, total_devengado, total_deducido, neto_pagar,
            vlr_bono, sal_especie
        ) VALUES (
            :id_contrato, :periodo_liq, :quincena_pago, :generar_nomina, :salario_base,
            :dias_laborados, :horas_laboradas, :dias_vacaciones, :dias_incapacidad,
            :prestamos, :prima_calc, :hed, :hen, :hedf, :henf, :rn, :rdn, :rnf, :observaciones,
            :ibc_pila, :salud_4, :pension_4, :total_devengado, :total_deducido, :neto_pagar,
            :vlr_bono, :sal_especie
        )
        ON CONFLICT (id_contrato, periodo_liq, quincena_pago)
        DO UPDATE SET
            generar_nomina = EXCLUDED.generar_nomina,
            salario_base = EXCLUDED.salario_base,
            dias_laborados = EXCLUDED.dias_laborados,
            horas_laboradas = EXCLUDED.horas_laboradas,
            dias_vacaciones = EXCLUDED.dias_vacaciones,
            dias_incapacidad = EXCLUDED.dias_incapacidad,
            prestamos = EXCLUDED.prestamos,
            prima_calc = EXCLUDED.prima_calc,
            hed = EXCLUDED.hed,
            hen = EXCLUDED.hen,
            hedf = EXCLUDED.hedf,
            henf = EXCLUDED.henf,
            rn = EXCLUDED.rn,
            rdn = EXCLUDED.rdn,
            rnf = EXCLUDED.rnf,
            observaciones = EXCLUDED.observaciones,
            ibc_pila = EXCLUDED.ibc_pila,
            salud_4 = EXCLUDED.salud_4,
            pension_4 = EXCLUDED.pension_4,
            total_devengado = EXCLUDED.total_devengado,
            total_deducido = EXCLUDED.total_deducido,
            neto_pagar = EXCLUDED.neto_pagar,
            vlr_bono = EXCLUDED.vlr_bono,
            sal_especie = EXCLUDED.sal_especie,
            created_at = CURRENT_TIMESTAMP AT TIME ZONE 'America/Bogota';
    """)

    records_saved = 0
    try:
        for _, row in df_entrada.iterrows():
            # Params para novedad
            params = {
                "id_contrato": str(row.get('ID_CONTRATO')).strip(),
                "periodo_liq": str(row.get('PERIODO_LIQ')).strip(),
                "quincena_pago": str(row.get('QUINCENA_PAGO', '1')).strip(),
                "generar_nomina": True,
                "salario_base": forzar_numero(row.get('SALARIO_BASE', 0)),
                "dias_laborados": forzar_numero(row.get('DIAS_LABORADOS', 0)),
                "horas_laboradas": forzar_numero(row.get('HORAS_LABORADAS', 0)),
                "dias_vacaciones": forzar_numero(row.get('DIAS_VACACIONES', 0)),
                "dias_incapacidad": forzar_numero(row.get('DIAS_INCAPACIDAD', 0)),
                "prestamos": forzar_numero(row.get('PRESTAMOS', 0)),
                "prima_calc": forzar_numero(row.get('PRIMA_CALC', 0)),
                "hed": forzar_numero(row.get('HED', 0)),
                "hen": forzar_numero(row.get('HEN', 0)),
                "hedf": forzar_numero(row.get('HEDF', 0)),
                "henf": forzar_numero(row.get('HENF', 0)),
                "rn": forzar_numero(row.get('RN', 0)),
                "rdn": forzar_numero(row.get('RDN', 0)),
                "rnf": forzar_numero(row.get('RNF', 0)),
                "observaciones": str(row.get('OBSERVACIONES', '')) if pd.notnull(row.get('OBSERVACIONES')) else None,
                "ibc_pila": forzar_numero(row.get('IBC_PILA', 0)),
                "salud_4": forzar_numero(row.get('SALUD_4', 0)),
                "pension_4": forzar_numero(row.get('PENSION_4', 0)),
                "total_devengado": forzar_numero(row.get('TOTAL_DEVENGADO', 0)),
                "total_deducido": forzar_numero(row.get('TOTAL_DEDUCIDO', 0)),
                "neto_pagar": forzar_numero(row.get('NETO_PAGAR', 0)),
                "vlr_bono": forzar_numero(row.get('VLR_BONO', 0)),
                "sal_especie": forzar_numero(row.get('SALARIO_ESPECIE', 0))
            }

            db.execute(upsert_query, params)
            records_saved += 1

        registrar_auditoria(
            db=db,
            current_user=current_user,
            tipo_accion="GUARDADO_HISTORICO",
            entidad_afectada="t_novedades",
            detalles={
                "periodo_liq": periodo_check,
                "quincena_pago": quincena_check,
                "registros_procesados": records_saved,
                "contratos_afectados": [str(c) for c in contratos_afectados]
            }
        )
        db.commit()
        return {
            "status": "success",
            "message": "Nómina guardada exitosamente en la base de datos.",
            "registros_procesados": records_saved
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error en transacción: {str(e)}")


@app.get("/api/v1/nomina/periodos-historico")
def obtener_historico(aportante_id: str = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    try:
        if getattr(current_user, "es_vip", False) or str(current_user.get("rol", "")).upper() in [models.RolUsuario.SUPERADMIN.value, models.RolUsuario.ADMINISTRADOR.value]:
            id_aportante_final = aportante_id or current_user.get("id_aportante")
        else:
            id_aportante_final = current_user.get("id_aportante")

        if not id_aportante_final or str(id_aportante_final) == 'None':
            raise ValueError(
                "No se detectó un id_aportante para consultar. Si eres STAFF UNIFIKA (SuperAdmin o Administrador), debes seleccionar una empresa primero.")

        # 1. Consultar m_empleados para obtener los contratos de esta empresa usando SQLAlchemy
        query_empleados = text("""
            SELECT id_contrato, nombre_empleado, cargo
            FROM m_empleados
            WHERE id_aportante = :id_aportante
        """)
        empleados_data = db.execute(query_empleados, {"id_aportante": str(id_aportante_final)}).mappings().all()
        contratos = [str(emp['id_contrato']) for emp in empleados_data if emp.get('id_contrato')]
        empleados_dict = {str(emp['id_contrato']): dict(emp) for emp in empleados_data if emp.get('id_contrato')}

        # Si la empresa no tiene empleados, devolvemos lista vacía inmediatamente
        if not contratos:
            return []

        # 2. Traer los periodos que ya están cerrados usando id_contrato
        contratos_limpios = [str(c).replace("'", "''") for c in contratos]
        contratos_sql = ', '.join([f"'{c}'" for c in contratos_limpios])
        query_cierres = text(f"""
            SELECT periodo_liq, quincena_pago, id_contrato
            FROM t_cierres_nomina
            WHERE id_contrato IN ({contratos_sql})
        """)
        cierres_data = db.execute(query_cierres).mappings().all()
        cierres_set = {
            f"{c['periodo_liq']}-{c['quincena_pago']}" for c in cierres_data}

        # 3. Traer la actividad de t_novedades filtrando por la lista de contratos
        query_novedades = text(f"""
            SELECT periodo_liq, quincena_pago, id_contrato
            FROM t_novedades
            WHERE id_contrato IN ({contratos_sql})
        """)
        novedades_data = db.execute(query_novedades).mappings().all()

        # 4. Agrupar periodos únicos y asignar estado
        periodos_unicos = {}
        for nov in novedades_data:
            key = f"{nov['periodo_liq']}-{nov['quincena_pago']}"
            if key not in periodos_unicos:
                estado_actual = "CERRADO" if key in cierres_set else "ABIERTO"
                periodos_unicos[key] = {
                    "periodo_liq": nov['periodo_liq'],
                    "quincena_pago": nov['quincena_pago'],
                    "estado": estado_actual,
                    "empleados": []
                }

            id_c = str(nov.get("id_contrato", ""))
            emp_info = empleados_dict.get(id_c, {})
            periodos_unicos[key]["empleados"].append({
                "id_contrato": id_c,
                "nombre_empleado": emp_info.get("nombre_empleado", "EMPLEADO DESCONOCIDO"),
                "cargo": emp_info.get("cargo", "N/A")
            })

        # Diccionario helper para ordenar meses cronológicamente
        MESES_MAP = {
            "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
            "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
            "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12
        }

        def obtener_llave_ordenamiento(item):
            # item['periodo_liq'] suele ser "MES AÑO" (ej: "JUNIO 2026")
            partes = str(item['periodo_liq']).upper().strip().split()

            # Extraer año (si viene en el string, si no, asume 0)
            anio = int(partes[1]) if len(
                partes) > 1 and partes[1].isdigit() else 0

            # Extraer mes
            nombre_mes = partes[0] if partes else ""
            mes_num = MESES_MAP.get(nombre_mes, 0)

            # Extraer quincena como entero (ej: "1" o "2")
            try:
                quincena = int(item.get('quincena_pago', 1))
            except (ValueError, TypeError):
                quincena = 1

            # Retorna una tupla: (Año, Mes, Quincena) para comparar numéricamente
            return (anio, mes_num, quincena)

        # Convertir el diccionario de periodos únicos a lista
        lista_resultado = list(periodos_unicos.values())

        # Ordenar la lista: de la más reciente a la más vieja (reverse=True)
        lista_resultado.sort(key=obtener_llave_ordenamiento, reverse=True)

        return lista_resultado

    except Exception as e:
        error_msg = f"Error Interno de Python: {str(e)}"
        raise HTTPException(status_code=500, detail=error_msg)


# =========================================================
# ENDPOINT DE TELEMETRÍA Y LOGS DE AUDITORÍA (STAFF)
# =========================================================

@app.get("/api/v1/auditoria/logs")
async def obtener_logs_auditoria(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint de lectura para visualizar los logs del sistema (t_auditoria_logs).
    Exclusivo para rol SUPERADMIN.
    """
    rol = str(current_user.get("rol", "") if isinstance(current_user, dict) else getattr(current_user, "rol", "")).upper().strip()
    if rol != models.RolUsuario.SUPERADMIN.value:
        raise HTTPException(
            status_code=403,
            detail="Acceso Denegado. Solo el rol SUPERADMIN puede consultar los logs de auditoría."
        )

    try:
        query = text("""
            SELECT id_log, fecha_evento, usuario_email, rol_usuario, id_aportante,
                   tipo_accion, entidad_afectada, detalles
            FROM t_auditoria_logs
            ORDER BY fecha_evento DESC
            LIMIT 200
        """)
        rows = db.execute(query).mappings().all()

        logs = []
        for row in rows:
            r = dict(row)
            detalles_val = r.get("detalles")
            if isinstance(detalles_val, str):
                try:
                    detalles_val = json.loads(detalles_val)
                except Exception:
                    pass
            r["detalles"] = detalles_val
            if isinstance(r.get("fecha_evento"), (datetime.datetime, datetime.date)):
                r["fecha_evento"] = r["fecha_evento"].isoformat()
            logs.append(r)

        return {
            "status": "success",
            "total": len(logs),
            "data": logs
        }
    except Exception as e:
        logger.error(f"Error consultando logs de auditoría: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error interno al consultar logs de auditoría: {str(e)}")



def procesar_ciclo_background(dry_run: bool, target_aportante: str, target_date_str: str = None):
    db = SessionLocal()
    try:
        if target_date_str:
            fecha_base = datetime.datetime.strptime(target_date_str, "%Y-%m-%d").date()
        else:
            fecha_base = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-5))).date()
            
        resultado = calcular_fechas_ciclo(fecha_base)
        if not resultado:
            logger.info(f"Cron procesar_ciclo_background: No hay acciones de ciclo programadas para hoy ({fecha_base}).")
            return
            
        accion, periodo_liq, quincena_pago = resultado
        acciones_simuladas = []
        
        try:
            if accion == 'PRELIQUIDAR':
                query_activos = db.query(models.Empleado).filter(
                    models.Empleado.estado_empleado.notin_(['RETIRADO', 'En Mora SS', 'UnicaAfiliacion'])
                )
                if target_aportante:
                    query_activos = query_activos.filter(models.Empleado.id_aportante == target_aportante)
                activos = query_activos.all()
                
                if not activos:
                    logger.info("Cron procesar_ciclo_background: No hay empleados activos para pre-liquidar.")
                    return
                    
                nuevas_novedades = []
                mail_from = os.environ.get("MAIL_FROM", "nomina@unifika.co")
                
                for emp in activos:
                    try:
                        # Prevención de Duplicados
                        existente = db.query(models.Novedad).filter_by(
                            id_contrato=emp.id_contrato,
                            periodo_liq=periodo_liq,
                            quincena_pago=quincena_pago
                        ).first()
                        if existente:
                            continue

                        with db.begin_nested():
                            ultima_nov = db.query(models.Novedad).filter(
                                models.Novedad.id_contrato == emp.id_contrato
                            ).order_by(models.Novedad.created_at.desc()).first()
                            
                            # Fuente de la verdad (m_empleados) y regla inmutable de especie
                            tipo_contrato_str = str(emp.tipo_contrato).strip().upper()
                            if "EMPLEADO INTERNO" in tipo_contrato_str:
                                sal_especie_aplicar = emp.sal_especie
                            else:
                                sal_especie_aplicar = 0
                            
                            if ultima_nov:
                                nueva_nov = models.Novedad(
                                    id_novedad=str(uuid.uuid4()),
                                    id_contrato=emp.id_contrato,
                                    periodo_liq=periodo_liq,
                                    quincena_pago=quincena_pago,
                                    generar_nomina=True,
                                    hed=0, hen=0, hedf=0, henf=0, rn=0, rdn=0, rnf=0,
                                    dias_vacaciones=0, dias_incapacidad=0, prestamos=0,
                                    dias_laborados=ultima_nov.dias_laborados,
                                    horas_laboradas=ultima_nov.horas_laboradas,
                                    prima_calc=ultima_nov.prima_calc,
                                    salario_base=emp.salario_base,
                                    vlr_bono=emp.vlr_bono,
                                    sal_especie=sal_especie_aplicar,
                                    observaciones="Pre-liquidación automática"
                                )
                            else:
                                nueva_nov = models.Novedad(
                                    id_novedad=str(uuid.uuid4()),
                                    id_contrato=emp.id_contrato,
                                    periodo_liq=periodo_liq,
                                    quincena_pago=quincena_pago,
                                    generar_nomina=True,
                                    hed=0, hen=0, hedf=0, henf=0, rn=0, rdn=0, rnf=0,
                                    dias_vacaciones=0, dias_incapacidad=0, prestamos=0,
                                    dias_laborados=0,
                                    horas_laboradas=0,
                                    prima_calc=0,
                                    salario_base=emp.salario_base,
                                    vlr_bono=emp.vlr_bono,
                                    sal_especie=sal_especie_aplicar,
                                    observaciones="Pre-liquidación automática inicial"
                                )
                            
                            # Calcular totales financieros en vuelo
                            row_dict_calc = {
                                "ES_SMLV": emp.es_smlv,
                                "CON_BONO": emp.con_bono,
                                "TIENE_AUX": emp.tiene_aux,
                                "TIPO_CONTRATO": emp.tipo_contrato,
                                "ESTADO_EMPLEADO": emp.estado_empleado,
                                "PERIODO_PAGO": emp.periodo_pago,
                                "SALARIO_BASE": emp.salario_base,
                                "VLR_BONO": emp.vlr_bono,
                                "SALARIO_ESPECIE": sal_especie_aplicar,
                                "EPS": emp.eps,
                                "FONDO_PENSIONES": emp.afp,
                                "DIAS_LABORADOS": nueva_nov.dias_laborados or 0,
                                "HORAS_LABORADAS": nueva_nov.horas_laboradas or 0,
                                "DIAS_VACACIONES": 0,
                                "DIAS_INCAPACIDAD": 0,
                                "PRESTAMOS": 0,
                                "PRIMA_CALC": nueva_nov.prima_calc or 0,
                                "HED": 0, "HEN": 0, "HEDF": 0, "HENF": 0, "RN": 0, "RDN": 0, "RNF": 0
                            }
                            
                            res_liq = liquidar_nomina([row_dict_calc], {})
                            if res_liq:
                                res_final = res_liq[0]
                                nueva_nov.ibc_pila = res_final.get("IBC_PILA", 0)
                                nueva_nov.salud_4 = res_final.get("SALUD_4", 0)
                                nueva_nov.pension_4 = res_final.get("PENSION_4", 0)
                                nueva_nov.total_devengado = res_final.get("TOTAL_DEVENGADO", 0)
                                nueva_nov.total_deducido = res_final.get("TOTAL_DEDUCIDO", 0)
                                nueva_nov.neto_pagar = res_final.get("NETO_PAGAR", 0)
                                
                            if not dry_run:
                                db.add(nueva_nov)
                                db.flush()
                                
                            if not dry_run and resend.api_key and emp.aportante and emp.aportante.email:
                                email_aportante = str(emp.aportante.email)
                                attachments = []
                                query_pdf = text("""
                                    SELECT e.*, n.*, 
                                           n.salario_base as salario_base_novedad,
                                           n.vlr_bono as vlr_bono_novedad,
                                           n.sal_especie as sal_especie_novedad,
                                           n.prestamos as prestamos_novedad,
                                           a.razon_social as razon_social,
                                           a.tipo_documento as tipo_documento,
                                           a.tipo_empleador as tipo_empleador,
                                           a.id_aportante as id_aportante
                                    FROM m_empleados e
                                    JOIN t_novedades n ON e.id_contrato = n.id_contrato
                                    LEFT JOIN m_aportantes a ON e.id_aportante = a.id_aportante
                                    WHERE e.id_contrato = :id_contrato
                                      AND n.periodo_liq = :periodo
                                      AND n.quincena_pago = :quincena
                                """)
                                row_pdf = db.execute(query_pdf, {"id_contrato": emp.id_contrato, "periodo": periodo_liq, "quincena": quincena_pago}).mappings().first()
                                
                                if row_pdf:
                                    row_dict = {k.upper(): v for k, v in dict(row_pdf).items()}
                                    if 'SALARIO_BASE_NOVEDAD' in row_dict and row_dict['SALARIO_BASE_NOVEDAD'] is not None:
                                        row_dict['SALARIO_BASE'] = row_dict['SALARIO_BASE_NOVEDAD']
                                    if 'VLR_BONO_NOVEDAD' in row_dict and row_dict['VLR_BONO_NOVEDAD'] is not None:
                                        row_dict['VALOR_BONO'] = row_dict['VLR_BONO_NOVEDAD']
                                    if 'SAL_ESPECIE_NOVEDAD' in row_dict and row_dict['SAL_ESPECIE_NOVEDAD'] is not None:
                                        row_dict['SALARIO_ESPECIE_MES'] = row_dict['SAL_ESPECIE_NOVEDAD']
                                    if 'PRESTAMOS_NOVEDAD' in row_dict and row_dict['PRESTAMOS_NOVEDAD'] is not None:
                                        row_dict['PRESTAMOS'] = row_dict['PRESTAMOS_NOVEDAD']

                                    if not row_dict.get('SAL_REF'):
                                        row_dict['SAL_REF'] = 1750905 if str(row_dict.get('ES_SMLV')).upper() in ['SI', 'TRUE', '1'] else row_dict.get('SALARIO_BASE', 0)

                                    try:
                                        res_liq_pdf = liquidar_nomina([row_dict], {})
                                        if res_liq_pdf:
                                            res_final_pdf = res_liq_pdf[0]
                                            res_final_pdf['RAZON_SOCIAL'] = row_dict.get('RAZON_SOCIAL', 'SIN EMPRESA')
                                            res_final_pdf['TIPO_DOCUMENTO'] = row_dict.get('TIPO_DOCUMENTO', 'NIT')
                                            res_final_pdf['TIPO_EMPLEADOR'] = row_dict.get('TIPO_EMPLEADOR', '')
                                            res_final_pdf['ID_APORTANTE'] = row_dict.get('ID_APORTANTE', '')
                                            res_final_pdf['PERIODO_LIQ'] = row_dict.get('PERIODO_LIQ')
                                            res_final_pdf['QUINCENA_PAGO'] = row_dict.get('QUINCENA_PAGO')
                                            res_final_pdf['OBSERVACIONES'] = row_dict.get('OBSERVACIONES')
                                            res_final_pdf['CARGO'] = row_dict.get('CARGO', 'NO ASIGNADO')
                                            res_final_pdf['TIPO_CONTRATO'] = row_dict.get('TIPO_CONTRATO', '')
                                            res_final_pdf['T_ID_EMPLEADO'] = row_dict.get('T_ID_EMPLEADO', '')
                                            res_final_pdf['ID_EMPLEADO'] = row_dict.get('ID_EMPLEADO', '')
                                            row_dict = res_final_pdf
                                    except Exception as eliq:
                                        pass

                                    row_dict['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
                                    response_pdf = generar_comprobante(row_dict)
                                    pdf_bytes = response_pdf.body
                                    attachments.append({
                                        "filename": f"Pre_liquidacion_{emp.id_contrato}.pdf",
                                        "content": list(pdf_bytes)
                                    })
                                
                                html_content = f"""
                                <div style="font-family: Arial, sans-serif; color: #333; line-height: 1.5;">
                                    <p>Adjunto encontrará el borrador de su pre-liquidación para la quincena {quincena_pago} del periodo {periodo_liq}.</p>
                                    <p><strong>Por motivos de seguridad y auditoría, para aprobar esta nómina o realizar ajustes, por favor inicie sesión en la plataforma haciendo clic en los botones.</strong></p>
                                    <div style="margin-top: 25px;">
                                        <a href="https://app.unifika.co/" style="background-color: #10b981; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-right: 15px; font-weight: bold; display: inline-block;">Aprobada</a>
                                        <a href="https://app.unifika.co/" style="background-color: #3b82f6; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; font-weight: bold; display: inline-block;">Deseo ajustar información</a>
                                    </div>
                                </div>
                                """
                                resend.Emails.send({
                                    "from": mail_from,
                                    "to": email_aportante,
                                    "subject": f"Pre-liquidación de Nómina Lista - {periodo_liq}",
                                    "html": html_content,
                                    "attachments": attachments
                                })
                        
                        # Si llegamos aquí sin excepciones, agregamos a la lista general
                        nuevas_novedades.append(nueva_nov)
                        if dry_run:
                            acciones_simuladas.append({
                                "accion": "CREAR_NOVEDAD",
                                "id_contrato": emp.id_contrato,
                                "periodo": periodo_liq,
                                "quincena": quincena_pago
                            })
                            if emp.aportante and emp.aportante.email:
                                acciones_simuladas.append({
                                    "accion": "ENVIAR_CORREO",
                                    "destinatario": emp.aportante.email
                                })

                    except Exception as e:
                        logger.error(f"Fallo individual en pre-liquidación para contrato {emp.id_contrato}: {e}")
                        continue
                
                if not dry_run and nuevas_novedades:
                    auditoria = models.AuditoriaLog(
                        usuario_email="SISTEMA_CRON",
                        rol_usuario="SISTEMA",
                        tipo_accion="PRELIQUIDACION_MASIVA",
                        detalles={"periodo": periodo_liq, "quincena": quincena_pago, "empleados_afectados": len(nuevas_novedades)}
                    )
                    db.add(auditoria)
                    db.commit()
                
                if dry_run:
                    logger.info(f"Cron procesar_ciclo_background SIMULACIÓN: Pre-liquidación generada para {len(nuevas_novedades)} contratos. Simuladas: {len(acciones_simuladas)}")
                else:
                    logger.info(f"Cron procesar_ciclo_background: Pre-liquidación generada para {len(nuevas_novedades)} contratos.")
                
            elif accion == 'CERRAR':
                query_sql = """
                    SELECT n.id_contrato 
                    FROM t_novedades n
                    LEFT JOIN t_cierres_nomina c ON n.id_contrato = c.id_contrato 
                                                AND n.periodo_liq = c.periodo_liq 
                                                AND n.quincena_pago = c.quincena_pago
                """
                params = {"periodo": periodo_liq, "quincena": quincena_pago}
                
                if target_aportante:
                    query_sql += """
                    INNER JOIN m_empleados e ON n.id_contrato = e.id_contrato
                    WHERE n.periodo_liq = :periodo
                      AND n.quincena_pago = :quincena
                      AND c.id_cierre IS NULL
                      AND e.id_aportante = :target_aportante
                    """
                    params["target_aportante"] = target_aportante
                else:
                    query_sql += """
                    WHERE n.periodo_liq = :periodo
                      AND n.quincena_pago = :quincena
                      AND c.id_cierre IS NULL
                    """
                    
                query_pendientes = text(query_sql)
                pendientes = db.execute(query_pendientes, params).fetchall()
                
                cierres = []
                for row in pendientes:
                    cierres.append(models.CierreNomina(
                        id_cierre=str(uuid.uuid4()),
                        id_contrato=row[0],
                        periodo_liq=periodo_liq,
                        quincena_pago=quincena_pago,
                        cerrado_por="SISTEMA_CRON"
                    ))
                    if dry_run:
                        acciones_simuladas.append({
                            "accion": "CERRAR_NOMINA",
                            "id_contrato": row[0],
                            "periodo": periodo_liq,
                            "quincena": quincena_pago
                        })
                    
                if cierres:
                    if not dry_run:
                        db.bulk_save_objects(cierres)
                        auditoria = models.AuditoriaLog(
                            usuario_email="SISTEMA_CRON",
                            rol_usuario="SISTEMA",
                            tipo_accion="CIERRE_AUTOMATICO",
                            detalles={"periodo": periodo_liq, "quincena": quincena_pago, "cierres_realizados": len(cierres)}
                        )
                        db.add(auditoria)
                        db.commit()
                
                if dry_run:
                    logger.info(f"Cron procesar_ciclo_background SIMULACIÓN: Cierre automático aplicado a {len(cierres)} contratos. Simuladas: {len(acciones_simuladas)}")
                else:
                    logger.info(f"Cron procesar_ciclo_background: Cierre automático aplicado a {len(cierres)} contratos.")
                
        except Exception as e:
            db.rollback()
            logger.error(f"Error en procesar_ciclo_background ({accion}): {e}")
    finally:
        db.close()


@app.post("/api/v1/cron/procesar-ciclo")
def procesar_ciclo(request: Request, background_tasks: BackgroundTasks, dry_run: bool = False, target_aportante: str = None):
    cron_secret_header = request.headers.get("X-Cron-Secret")
    cron_secret_env = os.environ.get("CRON_SECRET")
    
    if not cron_secret_env or cron_secret_header != cron_secret_env:
        raise HTTPException(status_code=403, detail="Forbidden. Invalid CRON_SECRET.")

    target_date_str = request.query_params.get("date")

    background_tasks.add_task(procesar_ciclo_background, dry_run, target_aportante, target_date_str)
    return {"status": "processing", "message": "Proceso iniciado en segundo plano."}
