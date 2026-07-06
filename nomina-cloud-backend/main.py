import pandas as pd
import numpy as np
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
import httpx

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
    if pd.isnull(valor): return "SIN PERIODO"
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
        self.cell(0, 5, self.emp_nombre, align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font('helvetica', '', 9)
        self.cell(0, 4, f"RUT: {self.emp_nit}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.cell(0, 4, f"Tipo: {self.emp_tipo}", align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        self.ln(4)

        self.set_font('helvetica', 'B', 12)
        self.cell(0, 10, 'COMPROBANTE INDIVIDUAL DE PAGO DE NÓMINA', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font('helvetica', '', 11)
        self.cell(0, 5, f'Periodo de Pago: {self.periodo_liq}', align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(5)

# =========================================================
# INICIALIZACIÓN DE LA APLICACIÓN FASTAPI
# =========================================================

app = FastAPI(
    title="Nómina Cloud API",
    description="API para la gestión y liquidación de nóminas conectada a Supabase.",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
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

@app.get("/api/v1/mi-ip")
async def get_my_ip():
    """Endpoint temporal para conocer la IP pública del servidor."""
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.ipify.org?format=json")
        response.raise_for_status()
        return response.json()

@app.get("/api/v1/empleador/{id_contacto}/empleados")
async def obtener_empleados_por_empleador(id_contacto: str):
    """
    Endpoint (Proxy) para obtener todos los empleados de un empleador.
    Realiza orquestación consultando Módulo Contactos y Módulo Oportunidades de Wolkvox.
    """
    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    
    headers = {
        "Content-Type": "application/json"
    }

    async def _mock_fallback():
        # Fallback a un mock si el endpoint es llamado de prueba o sin conexión real
        return {
            "status": "success",
            "empleador": "MOCK EMPRESA S.A.",
            "data": [
                {
                    "ID_CONTRATO": f"{id_contacto}_102938",
                    "NOMBRE_EMPLEADO": "Juan Perez",
                    "TIPO_CONTRATO": "TIEMPO PARCIAL",
                    "CARGO_DESEMPENEADO": "EMPLEADA DOMESTICA",
                    "PERIODO_PAGO": "QUINCENAL",
                    "ES_SMLV": "NO",
                    "SALARIO_BASE": 50000,
                    "CON_BONO": "SI",
                    "VLR_BONO": 15000,
                    "TIENE_AUX": "NO",
                    "EPS": "SURA",
                    "FONDO DE PENSIONES": "PROTECCION"
                },
                {
                    "ID_CONTRATO": f"{id_contacto}_229933",
                    "NOMBRE_EMPLEADO": "Maria Gomez",
                    "TIPO_CONTRATO": "TIEMPO COMPLETO",
                    "CARGO_DESEMPENEADO": "AUXILIAR ADMINISTRATIVO",
                    "PERIODO_PAGO": "MENSUAL",
                    "ES_SMLV": "SI",
                    "SALARIO_BASE": 1750905,
                    "CON_BONO": "NO",
                    "VLR_BONO": 0,
                    "TIENE_AUX": "SI",
                    "EPS": "N/A",
                    "FONDO DE PENSIONES": "N/A"
                }
            ]
        }

    try:
        async with httpx.AsyncClient() as client:
            # Paso 1: Módulo Contactos
            payload_contacto = {
                "operation": "techcon",
                "wolkvox-token": wolkvox_token,
                "module": "contacts",
                "field": "ID Contacto",
                "value": id_contacto
            }
            resp_contactos = await client.post(url_wolkvox, json=payload_contacto, headers=headers)
            resp_contactos.raise_for_status()
            data_contactos = resp_contactos.json()
            
            print("----- JSON CRUDO CONTACTOS -----")
            print(data_contactos)
            print("--------------------------------")
            
            # Verificar si existe "data" y si tiene elementos
            if not data_contactos.get("data") or len(data_contactos["data"]) == 0:
                raise HTTPException(status_code=404, detail="El empleador no existe en el Módulo de Contactos de Wolkvox.")
                
            contacto_data = data_contactos["data"][0]
            nombre_empleador = contacto_data.get("namecontact")
            contacto_interno_id = str(contacto_data.get("id", ""))
            
            if not nombre_empleador:
                raise HTTPException(status_code=400, detail="El contacto encontrado no tiene un nombre válido ('namecontact').")

            estado_contacto = contacto_data.get("Estado Contacto")
            if estado_contacto in ["RETIRADO", "UnicaAfiliacion", "En Mora SS"]:
                raise HTTPException(status_code=403, detail='El cliente se encuentra registrado en el sistema, pero actualmente no cuenta con este servicio habilitado.')

            # Helper para normalizar texto (minúsculas, sin tildes, sin espacios extra)
            def normalizar_texto(texto):
                if texto is None or not isinstance(texto, str):
                    return ""
                texto = texto.strip().lower()
                texto = " ".join(texto.split())
                return unicodedata.normalize('NFKD', texto).encode('ASCII', 'ignore').decode('utf-8')

            # Paso 2: Módulo Oportunidades
            # Intentamos primero buscar por ID_CONTACTO (Mejora de arquitectura recomendada)
            payload_oportunidades = {
                "operation": "techcon",
                "wolkvox-token": wolkvox_token,
                "module": "opportunities",
                "field": "ID Contacto",
                "value": id_contacto
            }
            
            empleados_wolkvox = []
            try:
                resp_oportunidades = await client.post(url_wolkvox, json=payload_oportunidades, headers=headers)
                resp_oportunidades.raise_for_status()
                data_oportunidades = resp_oportunidades.json()
                
                if not data_oportunidades.get("data") or len(data_oportunidades["data"]) == 0:
                    raise ValueError("Búsqueda por ID vacía")
                    
            except Exception as e:
                print(f"Aviso: Búsqueda por ID Contacto falló. Intentando fallback por nombre exacto. Error: {e}")
                # Fallback: usar el nombre original exacto (sin normalizar) tal cual está en la base de datos de Wolkvox
                payload_oportunidades["field"] = "Contact"
                payload_oportunidades["value"] = nombre_empleador
                
                try:
                    resp_oportunidades = await client.post(url_wolkvox, json=payload_oportunidades, headers=headers)
                    resp_oportunidades.raise_for_status()
                    data_oportunidades = resp_oportunidades.json()
                except Exception as e2:
                    print(f"Aviso: Búsqueda de oportunidades falló o sin resultados para '{nombre_empleador}'. Error: {e2}")
                    data_oportunidades = {}

            print("----- JSON CRUDO OPORTUNIDADES -----")
            print(data_oportunidades)
            print("------------------------------------")
            
            if data_oportunidades.get("data") and len(data_oportunidades["data"]) > 0:
                empleados_wolkvox = data_oportunidades["data"]
            
            if not empleados_wolkvox:
                # Asignar valores por defecto para que la ejecución no se rompa
                empleados_wolkvox = [{
                    "id": contacto_interno_id,
                    "ID Empleado": contacto_interno_id,
                    "Nombre del Empleado": nombre_empleador,
                    "Condicion Laboral": "TIEMPO COMPLETO",
                    "Salario Minimo": "SI",
                    "Salario Base": 1750905,
                    "Bono NO Salarial": "NO",
                    "Vlr Bono": 0,
                    "No Incluye Auxilio de Tte": "NO",
                    "EPS": "N/A",
                    "FONDO DE PENSIONES": "N/A"
                }]
            # Helpers para la extracción anidada de campos personalizados de Wolkvox
            def extract_val(d, key, default=None):
                val = d.get(key)
                if isinstance(val, dict):
                    # Extracción profunda segura para tipo 'currency'
                    if 'convert' in val and val['convert'] is not None:
                        return val['convert']
                    return val.get("value", default)
                return val if val is not None else default

            # Cruce en memoria seguro
            nombre_contacto_norm = normalizar_texto(nombre_empleador)
            empleados_filtrados = []
            for opp in empleados_wolkvox:
                nombre_opp = str(extract_val(opp, "Contact", "")) or str(extract_val(opp, "Nombre del Empleado", ""))
                if nombre_contacto_norm in normalizar_texto(nombre_opp) or normalizar_texto(nombre_opp) in nombre_contacto_norm:
                    empleados_filtrados.append(opp)
            
            if not empleados_filtrados and empleados_wolkvox:
                empleados_filtrados = empleados_wolkvox

            empleados_limpios = []

            # Paso 3: Procesamiento de Lista
            for empleado in empleados_filtrados:
                if empleado.get("wolkvox_fase") == "Retirado":
                    continue
                    
                id_empleado_extraido = extract_val(empleado, "ID Empleado")
                
                # Asegurar de tener un ID de empleado distinto al ID del empleador
                if not id_empleado_extraido or str(id_empleado_extraido) == str(id_contacto):
                    id_empleado = str(empleado.get("id") or empleado.get("contact_id") or contacto_interno_id)
                else:
                    id_empleado = str(id_empleado_extraido)
                    
                if not id_empleado:
                    continue  # Ignorar registros sin ID Empleado válido
                
                # Llave compuesta
                llave_unica = f"{id_contacto}_{id_empleado}"
                
                # Extracción de campos
                nombre_completo = empleado.get("Nombre del Empleado", "")
                if not nombre_completo:
                    nombre_completo = extract_val(empleado, "Nombre del Empleado", "")

                tipo_contrato = extract_val(empleado, "Condicion Laboral", "TIEMPO COMPLETO")
                tipo_labor = extract_val(empleado, "Tipo de Labor", "")
                periodo_pago = extract_val(empleado, "Frecuencia de Pago", "QUINCENAL")
                es_smlv = extract_val(empleado, "Salario Minimo", "SI")
                salario_base = extract_val(empleado, "Salario Base", 1750905)
                salario_especie = extract_val(empleado, "Salario en Especie", 0)
                con_bono = extract_val(empleado, "Bono NO Salarial", "NO")
                vlr_bono = extract_val(empleado, "Vlr Bono", 0)
                
                eps = extract_val(empleado, "EPS", "")
                fondo_pensiones = extract_val(empleado, "FONDO DE PENSIONES", "")
                
                raw_no_incluye = extract_val(empleado, "No Incluye Auxilio de Tte", "")
                val_no_incluye = str(raw_no_incluye).strip().upper() if raw_no_incluye is not None else ""
                if val_no_incluye in ["", "NO", "FALSE", "0", "NULL", "NONE"]:
                    tiene_aux = "SI"
                else:
                    tiene_aux = "NO"
                
                # Parsing numérico seguro
                try:
                    salario_base = float(salario_base)
                except:
                    salario_base = 1750905
                    
                try:
                    salario_especie = float(salario_especie)
                except:
                    salario_especie = 0
                    
                try:
                    vlr_bono = float(vlr_bono)
                except:
                    vlr_bono = 0

                empleados_limpios.append({
                    "ID_CONTRATO": llave_unica,
                    "ID_EMPLEADO": empleado.get("ID Empleado"),
                    "NOMBRE_EMPLEADO": nombre_completo,
                    "TIPO_CONTRATO": str(tipo_contrato).upper(),
                    "CARGO_DESEMPENEADO": str(tipo_labor).upper() if tipo_labor else "NO ESPECIFICADO",
                    "PERIODO_PAGO": str(periodo_pago).upper() if periodo_pago else "QUINCENAL",
                    "ES_SMLV": str(es_smlv).upper(),
                    "SALARIO_BASE": salario_base,
                    "SALARIO_ESPECIE": salario_especie,
                    "CON_BONO": str(con_bono).upper(),
                    "VLR_BONO": vlr_bono,
                    "TIENE_AUX": str(tiene_aux).upper(),
                    "EPS": str(eps),
                    "FONDO DE PENSIONES": str(fondo_pensiones)
                })

            if not empleados_limpios:
                raise HTTPException(status_code=404, detail="No se encontraron empleados con IDs válidos.")

            # Paso 4: Respuesta limpia
            return {
                "status": "success",
                "empleador": nombre_empleador,
                "data": empleados_limpios
            }
            
    except httpx.HTTPStatusError as e:
        if id_contacto.upper() == 'EMP-001':
            return await _mock_fallback()
        print(f"Error crítico HTTPStatusError en CRM: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error real: {str(e)} - Detalles: {e.response.text}")
    except httpx.HTTPError as e:
        if id_contacto.upper() == 'EMP-001':
            return await _mock_fallback()
        print(f"Error crítico HTTPError en CRM: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error real: {str(e)}")
    except HTTPException:
        # En caso de errores 404 (no encontrado) o 400 simulados, retornar el mock si es EMP-001
        if id_contacto.upper() == 'EMP-001':
            return await _mock_fallback()
        raise
    except Exception as e:
        print(f"Error crítico inesperado en CRM: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error real: {str(e)}")

@app.post("/api/v1/liquidar")
def liquidar_nomina(payload: List[Dict[str, Any]] = Body(...)):
    if not payload:
        return []
        
    for item in payload:
        periodo = str(item.get("PERIODO_PAGO", "QUINCENAL")).strip().upper()
        try:
            dias = float(item.get("DIAS_LABORADOS", 0) or 0)
        except ValueError:
            dias = 0
            
        if periodo == "QUINCENAL" and dias > 15:
            raise HTTPException(status_code=400, detail="Error de validación: Un contrato quincenal no puede superar los 15 días laborados.")
        elif periodo == "MENSUAL" and dias > 30:
            raise HTTPException(status_code=400, detail="Error de validación: Un contrato mensual no puede superar los 30 días laborados.")
    
    df_final = pd.DataFrame(payload)
    
    # --- 3. PARÁMETROS 2026 ---
    SMLV_2026 = 1750905
    SMLD_2026 = SMLV_2026 / 30
    PISO_TP_BONO = SMLD_2026 * (7/6)
    AUX_TTE_MES = 249095
    LIMITE_AUX = SMLV_2026 * 2
    HR_MES = 210
    PORCENTAJE_LEY = 0.04
    
    FACTORES = {'HED': 1.25, 'HEN': 1.75, 'HEDF': 2.05, 'HENF': 2.55, 'RN': 0.35, 'RDN': 0.80, 'RNF': 1.15}
    
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
    cols_limpiar = ['SALARIO_BASE', 'VLR_BONO', 'PRESTAMOS', 'SALARIO_ESPECIE', 'PRIMA_CALC']
    for col in cols_limpiar:
        df_final[col] = df_final[col].astype(str).str.replace(r'[\$,.]', '', regex=True)
            
    cols_num = cols_limpiar + ['DIAS_LABORADOS', 'HORAS_LABORADAS', 'DIAS_VACACIONES', 'DIAS_INCAPACIDAD'] + list(FACTORES.keys())
    cols_existentes = [col for col in cols_num if col in df_final.columns]
    df_final[cols_existentes] = df_final[cols_existentes].apply(pd.to_numeric, errors='coerce').fillna(0)
    
    # --- 5. & 6. LIQUIDACIÓN VECTORIZADA DE NÓMINA ---
    # A. Booleanos, Variables Base y ESTADO
    es_smlv = df_final['ES_SMLV'].astype(str).str.strip().str.upper().isin(['VERDADERO', 'TRUE', 'SI', '1'])
    con_bono = df_final['CON_BONO'].astype(str).str.strip().str.upper().isin(['VERDADERO', 'TRUE', 'SI', '1'])
    tiene_aux = df_final['TIENE_AUX'].astype(str).str.strip().str.upper().isin(['VERDADERO', 'TRUE', 'SI', 'SÍ', '1'])
    tipo_contrato = df_final['TIPO_CONTRATO'].astype(str).str.strip().str.upper()
    estado_empleado = df_final['ESTADO_EMPLEADO'].astype(str).str.strip().str.upper()
    periodo_pago = df_final['PERIODO_PAGO'].astype(str).str.strip().str.upper()
    
    # Distribución de Días
    d_vac = df_final['DIAS_VACACIONES']
    d_inc = df_final['DIAS_INCAPACIDAD']
    d_lab_total = np.where(df_final['HORAS_LABORADAS'] > 0, df_final['HORAS_LABORADAS'] / 8, df_final['DIAS_LABORADOS'])
    
    dias_efectivos_trabajo = np.maximum(d_lab_total - d_vac - d_inc, 0)
    
    sal_base_raw = df_final['SALARIO_BASE']
    sal_especie_raw = df_final['SALARIO_ESPECIE']
    
    df_final['TOTAL_BASE_MENSUAL'] = np.where(
        tipo_contrato == "EMPLEADO INTERNO",
        sal_base_raw + sal_especie_raw,
        sal_base_raw
    )
    
    sal_base_input = df_final['TOTAL_BASE_MENSUAL']
    val_diario_propuesto = np.where(tipo_contrato == "TIEMPO PARCIAL", sal_base_input, sal_base_input / 30)
    
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
    
    df_final['VAL_DIA_ESPECIE'] = np.where(tipo_contrato == "EMPLEADO INTERNO", sal_especie_raw / 30, 0)
    df_final['VAL_DIA_EFECTIVO'] = valor_dia_total - df_final['VAL_DIA_ESPECIE']
    
    df_final['SUELDO_EFECTIVO_PAGADO'] = df_final['VAL_DIA_EFECTIVO'] * dias_efectivos_trabajo
    df_final['SALARIO_ESPECIE_MES'] = df_final['VAL_DIA_ESPECIE'] * dias_efectivos_trabajo
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
    bono_mensual_tope = np.where(tipo_contrato == "TIEMPO PARCIAL", df_final['BONO_REF'] * 30, df_final['BONO_REF'])
    cond_aux = tiene_aux & ((df_final['SAL_REF'] + bono_mensual_tope) <= LIMITE_AUX)
    df_final['VAL_AUX_TTE'] = np.where(cond_aux, (AUX_TTE_MES / 30) * dias_efectivos_trabajo, 0)
    
    ibc_tiempo_completo = np.maximum(
        df_final['SUELDO_TRABAJADO'] + df_final['SALARIO_ESPECIE_MES'] + df_final['VALOR_VACACIONES'] + df_final['VALOR_INCAPACIDAD'] + df_final['TOTAL_EXTRAS'], 
        (SMLV_2026 / 30) * d_lab_total
    )
    
    dias_proyectados = np.where(periodo_pago == 'QUINCENAL', d_lab_total * 2, d_lab_total)
    cond_parcial = [dias_proyectados <= 7, dias_proyectados <= 14, dias_proyectados <= 21, dias_proyectados > 21]
    opciones_parcial_mes = [SMLV_2026 * 0.25, SMLV_2026 * 0.50, SMLV_2026 * 0.75, SMLV_2026]
    
    ibc_parcial_proporcional = np.where(
        periodo_pago == 'QUINCENAL',
        np.select(cond_parcial, opciones_parcial_mes) / 2,
        np.select(cond_parcial, opciones_parcial_mes)
    )
    
    eps_exento = df_final.get('EPS', '').astype(str).str.strip().str.upper().str.contains('N/A', na=False)
    fondo_pensiones_exento = df_final.get('FONDO_PENSIONES', '').astype(str).str.strip().str.upper().str.contains('N/A', na=False)
    
    cond_tiempo_parcial_rigido = (tipo_contrato == "TIEMPO PARCIAL") & (~eps_exento)

    # --- EXCEPCIÓN TIEMPO PARCIAL: IBC PILA ---
    # Los empleados de Tiempo Parcial que no están exentos de EPS cotizan sobre 1 SMLV completo.
    df_final['IBC_PILA'] = np.where(
        cond_tiempo_parcial_rigido,
        SMLV_2026,
        np.where(tipo_contrato == "TIEMPO PARCIAL", ibc_parcial_proporcional + df_final['TOTAL_EXTRAS'], ibc_tiempo_completo)
    )
    
    # --- CÁLCULO DE DEDUCCIONES ---
    # Salud y Pensión (4% cada uno)
    df_final['SALUD_4'] = np.where(eps_exento, 0, df_final['IBC_PILA'] * PORCENTAJE_LEY)
    df_final['PENSION_4'] = np.where(fondo_pensiones_exento, 0, df_final['IBC_PILA'] * PORCENTAJE_LEY)
    
    # Fraccionamiento de Deducciones para Periodo Quincenal
    # Regla: Solo se fracciona para Tiempo Parcial que NO están exentos de EPS (IBC base de SMLV completo)
    es_quincenal_fraccion = (periodo_pago == 'QUINCENAL') & (tipo_contrato == 'TIEMPO PARCIAL') & (~eps_exento)
    df_final['SALUD_4'] = np.where(es_quincenal_fraccion, df_final['SALUD_4'] / 2.0, df_final['SALUD_4'])
    df_final['PENSION_4'] = np.where(es_quincenal_fraccion, df_final['PENSION_4'] / 2.0, df_final['PENSION_4'])
    
    # Redondeo PILA al múltiplo de 100 superior como paso final
    df_final['SALUD_4'] = df_final['SALUD_4'].apply(lambda x: math.ceil(x / 100.0) * 100 if pd.notnull(x) and x > 0 else 0)
    df_final['PENSION_4'] = df_final['PENSION_4'].apply(lambda x: math.ceil(x / 100.0) * 100 if pd.notnull(x) and x > 0 else 0)
    
    # F. Totales Finales (Modificado para incluir PRIMA_CALC)
    df_final['SUELDO_PAGADO'] = df_final['SUELDO_TRABAJADO'] + df_final['VALOR_VACACIONES'] + df_final['VALOR_INCAPACIDAD']
    
    df_final['TOTAL_DEVENGADO'] = (
        df_final['SUELDO_PAGADO'] +
        df_final['SALARIO_ESPECIE_MES'] +
        df_final['VALOR_BONO'] +
        df_final['TOTAL_EXTRAS'] +
        df_final['VAL_AUX_TTE'] +
        df_final['PRIMA_CALC']
    )
    
    df_final['TOTAL_DEDUCIDO'] = df_final['SALUD_4'] + df_final['PENSION_4'] + df_final['PRESTAMOS']
    df_final['NETO_PAGAR'] = df_final['TOTAL_DEVENGADO'] - df_final['TOTAL_DEDUCIDO'] - df_final['SALARIO_ESPECIE_MES']
    
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

@app.post("/api/v1/comprobante/generar")
def generar_comprobante(row: Dict[str, Any] = Body(...)):
    HR_MES = 210
    factores_dict = {'HED': 1.25, 'HEN': 1.75, 'HEDF': 2.05, 'HENF': 2.55, 'RN': 0.35, 'RDN': 0.80, 'RNF': 1.15}

    periodo_actual = formatear_periodo(row.get('PERIODO_LIQ'))
    id_empleado = str(row.get('ID_EMPLEADO', 'SIN_EMPLEADO')).strip()

    sal_ref_fila = forzar_numero(row.get('SAL_REF', 0))
    v_hora_fila = sal_ref_fila / HR_MES

    datos_emp = {
        'nombre': str(row.get('RAZON_SOCIAL', 'EMPRESA NO ENCONTRADA')),
        'nit': str(row.get('ID_APORTANTE', '000.000.000-0')),
        'tipo': str(row.get('TIPO_DOCUMENTO', 'PERSONA JURÍDICA'))
    }

    pdf = ComprobantePDF(datos_emp, periodo_actual)
    pdf.add_page()

    # --- BLOQUE INFORMACIÓN EMPLEADO ---
    pdf.set_fill_color(245, 245, 245)
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(0, 7, f"INFORMACIÓN DEL TRABAJADOR", fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font('helvetica', '', 10)
    pdf.ln(2)
    pdf.cell(95, 6, f"Nombre: {row.get('NOMBRE_EMPLEADO', '')}")
    pdf.cell(60, 6, f"Tipo Contrato: {row.get('TIPO_CONTRATO', '')}")
    pdf.cell(50, 6, f"Tipo ID: {row.get('T_ID_EMPLEADO', '')}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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
    pdf.cell(45, 8, "DEDUCIDO", border=1, align='C', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf.set_font('helvetica', '', 10)

    # --- 1. CONCEPTOS DE TIEMPO Y SALARIO ---
    d_vac = forzar_numero(row.get('DIAS_VACACIONES', 0))
    d_inc = forzar_numero(row.get('DIAS_INCAPACIDAD', 0))
    d_trab = np.maximum(total_dias - d_vac - d_inc, 0)

    label_sueldo = "Sueldo Efectivo" if forzar_numero(row.get('SAL_ESPECIE_PAGADO', 0)) > 0 else "Sueldo por Días Trabajados"

    conceptos_fijos = [
        (f"{label_sueldo} ({d_trab:.0f} días)", 'SUELDO_EFECTIVO_PAGADO'),
        (f"Salario en Especie ({d_trab:.0f} días)", 'SAL_ESPECIE_PAGADO'),
        (f"Vacaciones Disfrutadas ({d_vac:.0f} días)", 'PAGO_VACACIONES'),
        (f"Incapacidad Remunerada ({d_inc:.0f} días)", 'PAGO_INCAPACIDAD'),
        ("Bono No Salarial", 'BONO_PAGADO'),
        ("Auxilio de Transporte", 'VAL_AUX_TTE'),
        ("Prima de Servicios", 'PRIMA_CALC')
    ]

    for desc, col in conceptos_fijos:
        val = forzar_numero(row.get(col, 0))
        if val > 0:
            pdf.cell(100, 7, desc, border='LR')
            pdf.cell(45, 7, f"{val:,.0f}", border='LR', align='R')
            pdf.cell(45, 7, "0", border='LR', align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # 2. DETALLE DE EXTRAS
    for cod, factor in factores_dict.items():
        cant = forzar_numero(row.get(cod, 0))
        if cant > 0:
            monto = float(cant * v_hora_fila * factor)
            pdf.cell(100, 7, f"{NOMBRES_EXTRAS.get(cod, cod)} ({cant} Hr)", border='LR')
            pdf.cell(45, 7, f"{monto:,.0f}", border='LR', align='R')
            pdf.cell(45, 7, "0", border='LR', align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- 3. DEDUCCIONES ---
    deducciones = [
        ("Aporte Salud (4%)", 'SALUD_4'),
        ("Aporte Pensión (4%)", 'PENSION_4'),
        ("Descuento por Préstamos", 'PRESTAMOS'),
        ("Salario Especie (Recibido)", 'SAL_ESPECIE_PAGADO')
    ]

    for desc, col in deducciones:
        val = forzar_numero(row.get(col, 0))
        if val > 0:
            pdf.cell(100, 7, desc, border='LR')
            pdf.cell(45, 7, "0", border='LR', align='R')
            pdf.cell(45, 7, f"{val:,.0f}", border='LR', align='R', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # LÍNEA FINAL DE LA TABLA
    pdf.cell(190, 0, "", border='T', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # TOTALES
    pdf.set_font('helvetica', 'B', 10)
    pdf.cell(100, 8, "TOTALES", border=1, align='R', fill=True)
    pdf.cell(45, 8, f"{forzar_numero(row.get('TOTAL_DEVENGADO', 0)):,.0f}", border=1, align='R', fill=True)
    pdf.cell(45, 8, f"{forzar_numero(row.get('TOTAL_DEDUCIDO', 0)):,.0f}", border=1, align='R', fill=True, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # NETO A PAGAR
    pdf.ln(4)
    pdf.set_font('helvetica', 'B', 12)
    pdf.cell(145, 10, "NETO A PAGAR:", align='R')
    pdf.set_text_color(0, 50, 150)
    pdf.cell(45, 10, f"${forzar_numero(row.get('NETO_PAGAR', 0)):,.0f}", border=1, align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.set_text_color(0, 0, 0)

    # --- FIRMAS ---
    pdf.ln(17)
    y_firma = pdf.get_y()
    pdf.line(25, y_firma, 85, y_firma)
    pdf.line(125, y_firma, 185, y_firma)
    pdf.ln(1)
    pdf.set_font('helvetica', '', 8)
    pdf.cell(95, 3, "Firma del Trabajador", align='C')
    pdf.cell(95, 3, "Firma Autorizada", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(95, 3, "(Recibí Conforme)", align='C')
    pdf.cell(95, 3, "Empleador / Sello", align='C', new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    # --- NOTAS PIE DE PÁGINA ---
    pdf.ln(10)
    pdf.set_font('helvetica', 'I', 8)
    pdf.set_text_color(100, 100, 100)
    ibc_val = forzar_numero(row.get('IBC_PILA', 0))
    pdf.cell(0, 4, f"* Base de Cotización (IBC): ${ibc_val:,.0f}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
    pdf.cell(0, 4, f"Estado: {row.get('OBSERVACIONES','LIQUIDADO')} | Generado por Nómina Cloud API.", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    pdf_bytes = bytes(pdf.output())
    
    return Response(
        content=pdf_bytes, 
        media_type="application/pdf",
        headers={'Content-Disposition': 'attachment; filename="comprobante.pdf"'}
    )

@app.post("/api/v1/historico/guardar")
def guardar_historico(payload: Union[Dict[str, Any], List[Dict[str, Any]]] = Body(...), db: Session = Depends(get_db)):
    if not payload:
        return {"status": "success", "message": "No hay datos para guardar."}
        
    if isinstance(payload, dict):
        payload = [payload]
        
    df_entrada = pd.DataFrame(payload)
    df_entrada.columns = df_entrada.columns.str.strip().str.upper()
    
    # 1. Asegurar columnas de periodo y quincena
    if 'PERIODO_LIQ' not in df_entrada.columns or 'QUINCENA_PAGO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener las claves 'PERIODO_LIQ' y 'QUINCENA_PAGO'."}
        
    # 2. Limpieza de entrada: Solo registros únicos por contrato
    if 'ID_CONTRATO' not in df_entrada.columns:
        return {"status": "error", "message": "El payload debe contener 'ID_CONTRATO'."}
        
    df_entrada = df_entrada.drop_duplicates(subset=['ID_CONTRATO'], keep='last')
    
    # 3. Preparar la inserción / actualización en t_novedades
    upsert_query = text("""
        INSERT INTO t_novedades (
            id_contrato, periodo_liq, quincena_pago, generar_nomina, 
            dias_laborados, horas_laboradas, dias_vacaciones, dias_incapacidad,
            prestamos, prima_calc, hed, hen, hedf, henf, rn, rdn, rnf, observaciones
        ) VALUES (
            :id_contrato, :periodo_liq, :quincena_pago, :generar_nomina,
            :dias_laborados, :horas_laboradas, :dias_vacaciones, :dias_incapacidad,
            :prestamos, :prima_calc, :hed, :hen, :hedf, :henf, :rn, :rdn, :rnf, :observaciones
        )
        ON CONFLICT (id_contrato, periodo_liq, quincena_pago)
        DO UPDATE SET
            generar_nomina = EXCLUDED.generar_nomina,
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
            created_at = CURRENT_TIMESTAMP;
    """)
    
    records_saved = 0
    try:
        for _, row in df_entrada.iterrows():
            params = {
                "id_contrato": str(row.get('ID_CONTRATO')).strip(),
                "periodo_liq": str(row.get('PERIODO_LIQ')).strip(),
                "quincena_pago": str(row.get('QUINCENA_PAGO', '1')).strip(),
                "generar_nomina": True,
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
                "observaciones": str(row.get('OBSERVACIONES', '')) if pd.notnull(row.get('OBSERVACIONES')) else None
            }
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
