import pandas as pd
import math
import datetime
import os
import unicodedata
import traceback
from fpdf import FPDF
from fpdf.enums import XPos, YPos
from fastapi.responses import Response
from fastapi import FastAPI, Depends, Body, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Dict, Any, Union
from database import get_db
from pydantic import BaseModel
import httpx
from core.security import get_current_user, get_current_user_unblocked, supabase_client
from dotenv import load_dotenv

load_dotenv(".env.local")
load_dotenv(".env")

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


def formatear_periodo(valor):
    if pd.isnull(valor):
        return "SIN PERIODO"
    if isinstance(valor, (pd.Timestamp, datetime.datetime)):
        return valor.strftime('%B %Y').upper()
    try:
        return pd.to_datetime(valor).strftime('%B %Y').upper()
    except:
        return str(valor).upper()


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
    proxy_url = os.getenv("PROXY_URL")
    client_kwargs = {"proxy": proxy_url} if proxy_url else {}
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
    proxy_url = os.getenv("PROXY_URL")
    client_kwargs = {"proxy": proxy_url} if proxy_url else {}
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp_contactos = await client.post(url_wolkvox, json=payload_contacto, headers=headers)
            if resp_contactos.status_code == 200:
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
        pass

    return {"estado_contacto": nuevo_estado}


@app.get("/api/v1/perfil")
@app.post("/api/v1/auth/init-session")
async def get_perfil_usuario(current_user: dict = Depends(get_current_user)):
    """
    Endpoint protegido para inicializar la sesión y validar el perfil (m_aportantes).
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
    Endpoint (Proxy) para obtener todos los empleados de un empleador con Caché en Supabase.
    """
    if current_user.get("rol") != "SuperAdmin":
        id_contacto = current_user["id_aportante"]
        
    # 1. Intentar cargar desde Caché Local (Supabase)
    try:
        query_empleados = text("SELECT * FROM m_empleados WHERE id_aportante = :id_aportante")
        empleados_locales = db.execute(query_empleados, {"id_aportante": id_contacto}).mappings().all()
        if empleados_locales and len(empleados_locales) > 0:
            print(f"[CACHE] ✅ {len(empleados_locales)} empleados encontrados localmente. Evitando Wolkvox.")
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
                    "RAZON_SOCIAL": current_user.get("razon_social", ""),
                    "EMAIL_APORTANTE": current_user.get("email", ""),
                })
            return {
                "status": "success",
                "empleador": current_user.get("razon_social", ""),
                "data": data_local
            }
    except Exception as e:
        print(f"[CACHE ERROR] Fallo al consultar m_empleados: {str(e)}")

    print(f"[WOLKVOX] ⚠️ Empleados no encontrados localmente para {id_contacto}. Extrayendo desde Wolkvox...")
    
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
        
    try:
        from core.wolkvox_sync import sync_empleados_from_wolkvox
        
        razon_social = current_user.get("razon_social")
        if not razon_social:
            query_admin = text("SELECT razon_social FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
            resultado_admin = db.execute(query_admin, {"id_aportante": id_contacto}).mappings().first()
            razon_social = resultado_admin["razon_social"] if resultado_admin else id_contacto

        empleados_limpios = await sync_empleados_from_wolkvox(id_contacto, razon_social, db)
        
        return {
            "status": "success",
            "empleador": razon_social,
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
    if current_user.get("rol") != "SuperAdmin":
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
    """
    if current_user.get("rol") != "SuperAdmin":
        id_contacto = current_user["id_aportante"]
        
    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    headers = {"wolkvox-token": wolkvox_token, "Content-Type": "application/json"}
    
    query_admin = text("SELECT razon_social FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
    resultado_admin = db.execute(query_admin, {"id_aportante": id_contacto}).mappings().first()
    nombre_empleador = resultado_admin["razon_social"] if resultado_admin else id_contacto

    from core.wolkvox_sync import sync_empleados_from_wolkvox
    try:
        empleados_limpios = await sync_empleados_from_wolkvox(id_contacto, nombre_empleador, db, target_empleado_id=id_empleado)
    except Exception as e:
        import traceback
        traceback.print_exc()
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=500, detail=f"Error sinc. Wolkvox: {str(e)}")

    return {
        "status": "success",
        "data": empleados_limpios[0] if empleados_limpios else None
    }

class CierreNominaRequest(BaseModel):
    periodo: str
    quincena: Union[int, str]
    id_aportante: Union[str, None] = None


@app.get("/api/v1/nomina/estado-cierre/{periodo}/{quincena}")
def obtener_estado_cierre(periodo: str, quincena: str, id_aportante: str = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    aportante_seguro = current_user.get("id_aportante")
    if not aportante_seguro or str(aportante_seguro) == 'None':
        aportante_seguro = id_aportante

    if not aportante_seguro:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de aportante válido para la consulta.")

    check = text(
        "SELECT 1 FROM t_cierres_nomina WHERE id_aportante = :id_aportante AND periodo_liq = :periodo AND quincena_pago = :quincena")
    is_cerrado = db.execute(check, {"id_aportante": str(
        aportante_seguro), "periodo": periodo, "quincena": quincena}).first() is not None
    return {"cerrado": is_cerrado}


@app.post("/api/v1/nomina/cerrar")
def cerrar_nomina(payload: CierreNominaRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    aportante_seguro = current_user.get("id_aportante")
    if not aportante_seguro or str(aportante_seguro) == 'None':
        aportante_seguro = payload.id_aportante

    if not aportante_seguro:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de aportante válido para el cierre.")

    id_aportante_str = str(aportante_seguro)
    email = current_user.get("email", "desconocido")
    if email != "desconocido":
        email = email.lower().strip()

    check = text(
        "SELECT 1 FROM t_cierres_nomina WHERE id_aportante = :id_aportante AND periodo_liq = :periodo AND quincena_pago = :quincena")
    quincena_str = str(payload.quincena).strip()

    if db.execute(check, {"id_aportante": id_aportante_str, "periodo": payload.periodo, "quincena": quincena_str}).first():
        raise HTTPException(
            status_code=400, detail="La nómina ya está cerrada.")

    try:
        insert = text("""
            INSERT INTO t_cierres_nomina (id_aportante, periodo_liq, quincena_pago, cerrado_por)
            VALUES (:id_aportante, :periodo, :quincena, :email)
        """)
        db.execute(insert, {"id_aportante": id_aportante_str,
                   "periodo": payload.periodo, "quincena": quincena_str, "email": email})
        db.commit()
        return {"status": "success", "message": "Nómina cerrada exitosamente."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/nomina/resumen/{periodo}/{quincena}")
async def obtener_resumen_nomina(periodo: str, quincena: str, id_aportante: str = None, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    aportante_seguro = current_user.get("id_aportante")
    if not aportante_seguro or str(aportante_seguro) == 'None':
        aportante_seguro = id_aportante

    if not aportante_seguro:
        raise HTTPException(
            status_code=400, detail="No se encontró un ID de aportante válido para la consulta.")

    id_aportante_str = str(aportante_seguro)

    query = text("""
        SELECT 
            e.id_contrato, e.nombre_empleado, e.cargo, e.tipo_contrato,
            n.neto_pagar, n.total_devengado, n.total_deducido
        FROM m_empleados e
        LEFT JOIN t_novedades n 
            ON e.id_contrato = n.id_contrato 
            AND n.periodo_liq = :periodo 
            AND n.quincena_pago = :quincena
        WHERE e.id_aportante = :id_aportante
          AND UPPER(e.estado_empleado) = 'ACTIVO'
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
            "neto_pagar": neto
        })

    return {
        "status": "success",
        "totales": {
            "total_empresa_devengado": total_empresa_devengado,
            "total_empresa_deducido": total_empresa_deducido,
            "total_empresa_neto": total_empresa_neto,
            "total_empleados": len(resultado),
            "empleados_pendientes": sum(1 for e in resumen_empleados if e["estado"] == "PENDIENTE")
        },
        "empleados": resumen_empleados
    }


@app.post("/api/v1/liquidar")
def liquidar_nomina(payload: List[Dict[str, Any]] = Body(...), current_user: dict = Depends(get_current_user)):
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
    query = text("""
        SELECT e.*, n.*, 
               n.salario_base as salario_base_novedad,
               n.vlr_bono as vlr_bono_novedad,
               n.sal_especie as sal_especie_novedad,
               n.prestamos as prestamos_novedad,
               a.razon_social as razon_social,
               a.tipo_documento as tipo_documento,
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
            resultado_final['ID_APORTANTE'] = row_dict.get('ID_APORTANTE', '')
            resultado_final['PERIODO_LIQ'] = row_dict.get('PERIODO_LIQ')
            resultado_final['QUINCENA_PAGO'] = row_dict.get('QUINCENA_PAGO')
            resultado_final['OBSERVACIONES'] = row_dict.get('OBSERVACIONES')

            return generar_comprobante(resultado_final)
    except Exception as e:
        pass
        # Fallback si falla liquidar_nomina, aseguramos SAL_REF para evitar error en divisor
    if not row_dict.get('SAL_REF'):
        row_dict['SAL_REF'] = 1750905 if str(row_dict.get('ES_SMLV')).upper() in [
            'SI', 'TRUE', '1'] else row_dict.get('SALARIO_BASE', 0)
    return generar_comprobante(row_dict)


@app.post("/api/v1/comprobante/generar")
def generar_comprobante(row: Dict[str, Any] = Body(...)):
    HR_MES = 210
    factores_dict = {'HED': 1.25, 'HEN': 1.75, 'HEDF': 2.05,
                     'HENF': 2.55, 'RN': 0.35, 'RDN': 0.80, 'RNF': 1.15}

    periodo_liq = formatear_periodo(row.get('PERIODO_LIQ', 'SIN PERIODO'))
    quincena_pago = str(row.get('QUINCENA_PAGO', '')).strip().upper()

    id_aportante = str(row.get('ID_APORTANTE', '')).strip()

    if quincena_pago in ['1', 'Q1']:
        texto_periodo = f"Primera Quincena de {periodo_liq}"
    elif quincena_pago in ['2', 'Q2']:
        texto_periodo = f"Segunda Quincena de {periodo_liq}"
    elif quincena_pago in ['M', 'MENSUAL']:
        texto_periodo = f"Mensualidad de {periodo_liq}"
    else:
        texto_periodo = periodo_liq

    id_empleado = str(row.get('ID_EMPLEADO', 'SIN_EMPLEADO')).strip()

    sal_ref_fila = forzar_numero(row.get('SAL_REF', 0))
    v_hora_fila = sal_ref_fila / HR_MES

    datos_emp = {
        'nombre': str(row.get('RAZON_SOCIAL', 'EMPRESA NO ENCONTRADA')),
        'nit': str(row.get('ID_APORTANTE', '000.000.000-0')),
        'tipo': str(row.get('TIPO_DOCUMENTO', 'PERSONA JURÍDICA'))
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
    pdf.cell(95, 6, f"Nombre: {row.get('NOMBRE_EMPLEADO', '')}")
    pdf.cell(60, 6, f"Tipo Contrato: {row.get('TIPO_CONTRATO', '')}")
    pdf.cell(50, 6, f"Tipo ID: {row.get('T_ID_EMPLEADO', '')}",
             new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.cell(95, 6, f"Cargo: {row.get('CARGO', 'NO ASIGNADO')}")
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
        ("Descuento por Préstamos", 'PRESTAMOS'),
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
    observaciones = row.get("OBSERVACIONES", "").strip()
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

    id_contrato = row.get('ID_CONTRATO', 'SIN_CONTRATO')
    periodo_liq_raw = row.get('PERIODO_LIQ', 'SIN_PERIODO')
    quincena_pago_raw = row.get('QUINCENA_PAGO', '')

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


@app.post("/api/v1/historico/guardar")
def guardar_historico(payload: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(...), db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    if not payload:
        return {"status": "success", "message": "No hay datos para guardar."}

    if isinstance(payload, dict):
        payload = [payload]

    df_entrada = pd.DataFrame(payload)
    df_entrada.columns = df_entrada.columns.str.strip().str.upper()

    # 1. Asegurar columnas de periodo y quincena
    if 'PERIODO_LIQ' not in df_entrada.columns or 'QUINCENA_PAGO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener las claves 'PERIODO_LIQ' y 'QUINCENA_PAGO'."}

    id_aportante = str(current_user.get("id_aportante"))
    periodo_check = str(df_entrada.iloc[0]['PERIODO_LIQ']).strip()
    quincena_check = str(df_entrada.iloc[0]['QUINCENA_PAGO']).strip()

    check_cierre_query = text("""
        SELECT 1 FROM t_cierres_nomina
        WHERE id_aportante = :id_aportante AND periodo_liq = :periodo AND quincena_pago = :quincena
    """)
    if db.execute(check_cierre_query, {"id_aportante": id_aportante, "periodo": periodo_check, "quincena": quincena_check}).first():
        raise HTTPException(
            status_code=400, detail="La nómina de este periodo se encuentra en estado CERRADO y sus datos no pueden ser alterados. Por favor, comuníquese con la línea de atención.")

    # 2. Limpieza de entrada: Solo registros únicos por contrato
    if 'ID_CONTRATO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener 'ID_CONTRATO'."}

    df_entrada = df_entrada.drop_duplicates(
        subset=['ID_CONTRATO'], keep='last')

    # 3. Preparar la inserción / actualización en cascada (Aportante -> Empleado -> Novedades)
    upsert_aportante_query = text("""
        INSERT INTO m_aportantes (id_aportante, razon_social, tipo_documento, tipo_empleador, telefono, email)
        VALUES (:id_aportante, :razon_social, :tipo_documento, :tipo_empleador, :telefono, :email)
        ON CONFLICT (id_aportante) DO UPDATE SET
            razon_social = EXCLUDED.razon_social,
            tipo_documento = EXCLUDED.tipo_documento,
            tipo_empleador = EXCLUDED.tipo_empleador,
            telefono = EXCLUDED.telefono,
            email = EXCLUDED.email;
    """)

    upsert_empleado_query = text("""
        INSERT INTO m_empleados (
            id_contrato, id_aportante, id_empleado, t_id_empleado, nombre_empleado,
            cargo, tipo_contrato, estado_empleado, periodo_pago, salario_base,
            vlr_bono, sal_especie, eps, afp, es_smlv, con_bono, tiene_aux,
            nombre_1, nombre_2, apellido_1, apellido_2, departamento, municipio, riesgo_arl, ccf, arl, link_drive
        ) VALUES (
            :id_contrato, :id_aportante, :id_empleado, :t_id_empleado, :nombre_empleado,
            :cargo, :tipo_contrato, :estado_empleado, :periodo_pago, :salario_base,
            :vlr_bono, :sal_especie, :eps, :afp, :es_smlv, :con_bono, :tiene_aux,
            :nombre_1, :nombre_2, :apellido_1, :apellido_2, :departamento, :municipio, :riesgo_arl, :ccf, :arl, :link_drive
        ) ON CONFLICT (id_contrato) DO UPDATE SET
            id_aportante = EXCLUDED.id_aportante,
            id_empleado = EXCLUDED.id_empleado,
            t_id_empleado = EXCLUDED.t_id_empleado,
            nombre_empleado = EXCLUDED.nombre_empleado,
            cargo = EXCLUDED.cargo,
            tipo_contrato = EXCLUDED.tipo_contrato,
            estado_empleado = EXCLUDED.estado_empleado,
            periodo_pago = EXCLUDED.periodo_pago,
            salario_base = EXCLUDED.salario_base,
            vlr_bono = EXCLUDED.vlr_bono,
            sal_especie = EXCLUDED.sal_especie,
            eps = EXCLUDED.eps,
            afp = EXCLUDED.afp,
            es_smlv = EXCLUDED.es_smlv,
            con_bono = EXCLUDED.con_bono,
            tiene_aux = EXCLUDED.tiene_aux,
            nombre_1 = EXCLUDED.nombre_1,
            nombre_2 = EXCLUDED.nombre_2,
            apellido_1 = EXCLUDED.apellido_1,
            apellido_2 = EXCLUDED.apellido_2,
            departamento = EXCLUDED.departamento,
            municipio = EXCLUDED.municipio,
            riesgo_arl = EXCLUDED.riesgo_arl,
            ccf = EXCLUDED.ccf,
            arl = EXCLUDED.arl,
            link_drive = EXCLUDED.link_drive;
    """)

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
            # Params para aportante
            # Si es SuperAdmin (None), toma el ID del payload. Si es Empleador, usa el de la sesión.
            id_aportante_seguro = current_user.get("id_aportante")
            if not id_aportante_seguro:
                id_aportante_seguro = str(row.get('ID_APORTANTE', '')).strip()

            if not id_aportante_seguro:
                raise HTTPException(
                    status_code=400, detail="No se encontró un ID de aportante válido para guardar el registro.")
            params_aportante = {
                "id_aportante": id_aportante_seguro,
                "razon_social": str(row.get('RAZON_SOCIAL', '')).strip(),
                "tipo_documento": str(row.get('TIPO_DOCUMENTO', '')).strip(),
                "tipo_empleador": str(row.get('TIPO_EMPLEADOR', '')).strip(),
                "telefono": str(row.get('TELEFONO_APORTANTE', '')).strip(),
                "email": str(row.get('EMAIL_APORTANTE', '')).strip()
            }

            # Params para empleado
            es_smlv_bool = str(row.get('ES_SMLV', '')).strip().upper() in [
                'SI', 'TRUE', '1']
            con_bono_bool = str(row.get('CON_BONO', '')).strip().upper() in [
                'SI', 'TRUE', '1']
            tiene_aux_bool = str(row.get('TIENE_AUX', '')).strip().upper() in [
                'SI', 'TRUE', '1']

            params_empleado = {
                "id_contrato": str(row.get('ID_CONTRATO')).strip(),
                "id_aportante": id_aportante_seguro,
                "id_empleado": str(row.get('ID_EMPLEADO', '')).strip(),
                "t_id_empleado": str(row.get('T_ID_EMPLEADO', '')).strip(),
                "nombre_empleado": str(row.get('NOMBRE_EMPLEADO', '')).strip(),
                "cargo": str(row.get('CARGO', '')).strip() or str(row.get('CARGO_DESEMPENEADO', '')).strip(),
                "tipo_contrato": str(row.get('TIPO_CONTRATO', '')).strip(),
                "estado_empleado": str(row.get('ESTADO_EMPLEADO', 'ACTIVO')).strip(),
                "periodo_pago": str(row.get('PERIODO_PAGO', '')).strip(),
                "salario_base": forzar_numero(row.get('SALARIO_BASE', 0)),
                "vlr_bono": forzar_numero(row.get('VLR_BONO', 0)),
                "sal_especie": forzar_numero(row.get('SALARIO_ESPECIE', 0)),
                "eps": str(row.get('EPS', '')).strip(),
                "afp": str(row.get('FONDO_PENSIONES', '')).strip() or str(row.get('FONDO DE PENSIONES', '')).strip(),
                "es_smlv": es_smlv_bool,
                "con_bono": con_bono_bool,
                "tiene_aux": tiene_aux_bool,
                "nombre_1": str(row.get('NOMBRE_1', '')).strip(),
                "nombre_2": str(row.get('NOMBRE_2', '')).strip(),
                "apellido_1": str(row.get('APELLIDO_1', '')).strip(),
                "apellido_2": str(row.get('APELLIDO_2', '')).strip(),
                "departamento": str(row.get('DEPARTAMENTO', '')).strip(),
                "municipio": str(row.get('MUNICIPIO', '')).strip(),
                "riesgo_arl": str(row.get('RIESGO_ARL', '')).strip(),
                "ccf": str(row.get('CCF', '')).strip(),
                "arl": str(row.get('NOMBRE_ARL', '')).strip(),
                "link_drive": str(row.get('LINK_DRIVE', '')).strip()
            }

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

            db.execute(upsert_aportante_query, params_aportante)
            db.execute(upsert_empleado_query, params_empleado)
            db.execute(upsert_query, params)
            records_saved += 1

        db.commit()
        return {
            "status": "success",
            "message": "Nómina guardada exitosamente en la base de datos.",
            "registros_procesados": records_saved
        }
    except Exception as e:
        db.rollback()
        return {"status": "error", "message": f"Error al guardar histórico: {str(e)}"}


@app.get("/api/v1/nomina/periodos-historico")
def obtener_historico(aportante_id: str = None, current_user: dict = Depends(get_current_user)):
    try:
        id_aportante_final = aportante_id or current_user.get("id_aportante")

        if not id_aportante_final or str(id_aportante_final) == 'None':
            raise ValueError(
                "No se detectó un id_aportante para consultar. Si eres SuperAdmin, debes seleccionar una empresa primero.")

        # 1. Traer los periodos que ya están cerrados (Esta tabla SÍ tiene id_aportante)
        cierres_res = supabase_client.table('t_cierres_nomina').select(
            'periodo_liq, quincena_pago').eq('id_aportante', id_aportante_final).execute()
        cierres_data = cierres_res.data if cierres_res.data else []
        cierres_set = {
            f"{c['periodo_liq']}-{c['quincena_pago']}" for c in cierres_data}

        # 2. Consultar m_empleados para obtener los contratos de esta empresa
        empleados_res = supabase_client.table('m_empleados').select(
            'id_contrato, nombre_empleado, cargo').eq('id_aportante', id_aportante_final).execute()
        empleados_data = empleados_res.data if empleados_res.data else []
        contratos = [emp['id_contrato'] for emp in empleados_data]
        empleados_dict = {emp['id_contrato']: emp for emp in empleados_data}

        # Si la empresa no tiene empleados, devolvemos lista vacía inmediatamente
        if not contratos:
            return []

        # 3. Traer la actividad de t_novedades filtrando por la lista de contratos
        novedades_res = supabase_client.table('t_novedades').select(
            'periodo_liq, quincena_pago, id_contrato').in_('id_contrato', contratos).execute()
        novedades_data = novedades_res.data if novedades_res.data else []

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

            id_c = nov.get("id_contrato")
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
            partes = item['periodo_liq'].upper().strip().split()

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
