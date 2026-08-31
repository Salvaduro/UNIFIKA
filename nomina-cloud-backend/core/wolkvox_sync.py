import os
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException
import logging

logger = logging.getLogger("uvicorn")


def map_aportante_from_wolkvox(contacto_data: dict, fallback_id: str, fallback_email: str) -> dict:
    if not isinstance(contacto_data, dict):
        contacto_data = {}
    nombre_empleador = str(contacto_data.get("namecontact", "") or "SIN NOMBRE").strip()
    tipo_doc_empleador = str(contacto_data.get("Tipo ID Contacto", "") or "NIT").strip()
    rut_empleador = str(contacto_data.get("ID Contacto", "") or fallback_id or "").strip()
    tipo_empleador = str(contacto_data.get("Tipo Empleador", "") or "PERSONA JURÍDICA").strip()
    telefono_raw = contacto_data.get("telephonecontact", {})
    telefono = str(telefono_raw.get("value", "") or "").strip() if isinstance(telefono_raw, dict) else str(telefono_raw or "").strip() if telefono_raw else ""
    email_crm = contacto_data.get("emailcontact", fallback_email)

    nuevo_aportante = {
        "id_aportante": rut_empleador,
        "razon_social": nombre_empleador,
        "tipo_documento": tipo_doc_empleador,
        "tipo_empleador": tipo_empleador,
        "telefono": telefono,
        "email": str(email_crm or fallback_email or "").lower().strip(),
        "estado_contacto": contacto_data.get("Estado Contacto"),
        "carpeta_cliente": contacto_data.get("Carpeta Cliente", None)
    }
    
    return {k: v for k, v in nuevo_aportante.items() if v is not None and v != ""}


async def sync_aportante_from_wolkvox(id_aportante: str, db: Session) -> dict:
    """
    Función para extraer y actualizar el empleador (Contacto) desde Wolkvox de forma manual.
    """
    id_aportante = str(id_aportante)
    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    if not wolkvox_token:
        logger.error("[ERROR-SYNC-APORTANTE] WOLKVOX_TOKEN no configurado.")
        return None

    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    headers = {"wolkvox-token": wolkvox_token, "Content-Type": "application/json"}
    
    payload_contacto = {
        "operation": "techcon",
        "wolkvox-token": wolkvox_token,
        "module": "contacts",
        "field": "ID Contacto",
        "value": id_aportante
    }

    fixie_url = os.getenv("FIXIE_URL")
    client_kwargs = {"proxy": fixie_url} if fixie_url else {}
    
    try:
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.post(url_wolkvox, json=payload_contacto, headers=headers, timeout=15)
            
            logger.info(f"[DEBUG-CONTACTOS] Buscando empleador con ID: {id_aportante}")
            logger.info(f"[DEBUG-CONTACTOS] HTTP Status: {resp.status_code}")
            logger.info(f"[DEBUG-CONTACTOS] Body: {resp.text}")
            
            if resp.status_code == 200:
                data_contactos = resp.json()
                if isinstance(data_contactos, dict) and data_contactos.get("data") and len(data_contactos.get("data", [])) > 0:
                    contacto_data = data_contactos.get("data", [])[0]
                    
                    # Extraer email existente para fallback si no hay en crm
                    query_admin = text("SELECT email FROM m_aportantes WHERE id_aportante = :id_aportante LIMIT 1")
                    resultado_admin = db.execute(query_admin, {"id_aportante": id_aportante}).mappings().first()
                    fallback_email = resultado_admin.get("email", "") if resultado_admin else ""
                    
                    nuevo_aportante = map_aportante_from_wolkvox(contacto_data, id_aportante, fallback_email)
                    
                    # UPDATE/UPSERT explícito
                    from core.security import supabase_client
                    supabase_client.table("m_aportantes").upsert(nuevo_aportante).execute()
                    
                    return nuevo_aportante
    except Exception as e:
        logger.error(f"[ERROR-SYNC-APORTANTE] Fallo al extraer o actualizar el aportante {id_aportante}: {str(e)}")
        
    return None


def extract_val(d: dict, key: str, default=None):
    """
    Extracción segura de valores en diccionarios anidados de Wolkvox.
    """
    if not isinstance(d, dict):
        return default
    val = d.get(key)
    if isinstance(val, dict):
        if "convert" in val and val.get("convert") is not None:
            return val.get("convert", default)
        return val.get("value", default)
    return val if val is not None else default


def parse_monetary(valor, default=0) -> float:
    """
    Extracción de Diccionarios Anidados (Monedas):
    Campos monetarios como 'Salario Base', 'Salario en Especie' y 'Amount' 
    vienen de Wolkvox como diccionarios (ej: {"value": "1750905", "symbol": "COP"}).
    Verifica if isinstance(valor, dict): y extrae .get("value", 0) antes de convertir a float().
    """
    while isinstance(valor, dict):
        valor = valor.get("convert") if valor.get("convert") is not None else valor.get("value", default)
    try:
        if valor is None:
            return float(default)
        val_str = str(valor).strip().replace(",", "")
        if val_str.lower() in ["", "none", "null", "n/a", "na"]:
            return float(default)
        return float(val_str)
    except (ValueError, TypeError):
        return float(default)


async def sync_empleados_from_wolkvox(id_aportante: str, razon_social: str, db: Session, target_empleado_id: str = None):
    """
    Función reutilizable para extraer empleados desde Wolkvox y hacer el upsert profundo de 28 columnas a m_empleados.
    Si target_empleado_id está presente, se filtra y procesa únicamente ese empleado.

    Regla de Negocio (Soft-Delete de Wolkvox):
    - NUNCA aplicar Hard-Delete a un empleado que ya no viene en Wolkvox (estado "lost").
    - Se aplica Soft-Delete cambiando estado_empleado = 'RETIRADO' (de lo contrario se asigna 'ACTIVO').
    """
    id_aportante = str(id_aportante)
    if target_empleado_id is not None:
        target_empleado_id = str(target_empleado_id)
        
    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    headers = {"wolkvox-token": wolkvox_token, "Content-Type": "application/json"}
    
    if not razon_social or str(razon_social).strip() == "" or str(razon_social).strip().lower() == "none":
        logger.error(f"[ERROR-SYNC-EMPLEADOS] Razón Social viene vacía o nula para el aportante {id_aportante}. Intentando fallback a ID.")
        razon_social_busqueda = id_aportante
    else:
        razon_social_busqueda = str(razon_social).strip()

    payload_detalle = {
        "operation": "techcon",
        "wolkvox-token": wolkvox_token,
        "module": "opportunities",
        "field": "Contact",
        "value": razon_social_busqueda
    }
    
    fixie_url = os.getenv("FIXIE_URL")
    client_kwargs = {"proxy": fixie_url} if fixie_url else {}
    
    async with httpx.AsyncClient(**client_kwargs) as client:
        resp_det = await client.post(url_wolkvox, json=payload_detalle, headers=headers)
        
        logger.info(f"[DEBUG-OPORTUNIDADES] Buscando con ID: {id_aportante} / Nombre: {razon_social_busqueda}")
        logger.info(f"[DEBUG-OPORTUNIDADES] HTTP Status: {resp_det.status_code}")
        logger.info(f"[DEBUG-OPORTUNIDADES] Body: {resp_det.text}")

        if resp_det.status_code >= 400:
            logger.error(f"[WOLKVOX/FIXIE ERROR] Status: {resp_det.status_code}, Body: {resp_det.text}")
            raise HTTPException(status_code=403, detail=f"Error en proveedor externo: {resp_det.text}")
        resp_det.raise_for_status()
        data_det = resp_det.json()
        
        if not isinstance(data_det, dict) or not data_det.get("data") or len(data_det.get("data", [])) == 0:
            if target_empleado_id:
                raise HTTPException(status_code=404, detail="Empleado no encontrado en Wolkvox.")
            return []

        empleados_limpios = []
        for emp_wv in data_det.get("data", []):
            if not isinstance(emp_wv, dict):
                continue

            raw_id_for_log = str(
                emp_wv.get("ID Empleado", "") or emp_wv.get("id", "") or emp_wv.get("contact_id", "") or "DESCONOCIDO"
            ).strip()
            try:
                if target_empleado_id:
                    if str(emp_wv.get("ID Empleado", "") or "").strip() != str(target_empleado_id).strip():
                        continue
                        
                # El filtrado de Retirado se manejará a través del mapeo de estado

                id_opp = str(emp_wv.get("id", "") or "").strip()
                raw_id_empleado = emp_wv.get("ID Empleado")
                id_empleado_str = str(raw_id_empleado).strip() if raw_id_empleado is not None and str(raw_id_empleado).strip() != "" else id_opp
                
                if not id_empleado_str or str(id_empleado_str) == str(id_aportante):
                    contact_id = emp_wv.get("contact_id")
                    id_empleado_str = str(contact_id).strip() if contact_id is not None and str(contact_id).strip() != "" else id_opp
                
                if not id_empleado_str:
                    continue
                    
                llave_unica = f"{id_aportante}_{id_empleado_str}"

                nombre_completo = str(
                    emp_wv.get("Nombre del Empleado", "") or extract_val(emp_wv, "Nombre del Empleado", "") or ""
                ).strip()

                nombre_1 = str(emp_wv.get("NOMBRE_1", "") or "").strip().upper()
                nombre_2 = str(emp_wv.get("NOMBRE_2", "") or "").strip().upper()
                apellido_1 = str(emp_wv.get("APELLIDO_1", "") or "").strip().upper()
                apellido_2 = str(emp_wv.get("APELLIDO_2", "") or "").strip().upper()
                departamento = str(emp_wv.get("Departamento", "") or "").strip().upper()
                municipio = str(emp_wv.get("Municipio", "") or "").strip().upper()
                riesgo_arl = str(emp_wv.get("Tipo de Riesgo ARL", "") or "").strip().upper()
                ccf = str(emp_wv.get("CAJA COMPENSACION", "") or "").strip().upper()
                nombre_arl = str(emp_wv.get("ARL", "") or "").strip().upper()
                
                tipo_id_empleado = str(extract_val(emp_wv, "Tipo ID Empleado", "") or "").strip().upper()
                tipo_contrato = str(extract_val(emp_wv, "Condicion Laboral", "TIEMPO COMPLETO") or "TIEMPO COMPLETO").strip().upper()
                tipo_labor = str(extract_val(emp_wv, "Tipo de Labor", "") or "").strip().upper()
                periodo_pago = str(extract_val(emp_wv, "Frecuencia de Pago", "QUINCENAL") or "QUINCENAL").strip().upper()
                es_smlv = str(extract_val(emp_wv, "Salario Minimo", "SI") or "SI").strip().upper()
                
                raw_salario_base = extract_val(emp_wv, "Salario Base", None)
                if raw_salario_base is None:
                    raw_salario_base = extract_val(emp_wv, "Amount", 1750905)
                salario_base = parse_monetary(raw_salario_base, default=1750905)
                
                raw_salario_especie = extract_val(emp_wv, "Salario en Especie", 0)
                salario_especie = parse_monetary(raw_salario_especie, default=0)
                
                con_bono = str(extract_val(emp_wv, "Bono NO Salarial", "NO") or "NO").strip().upper()
                raw_vlr_bono = extract_val(emp_wv, "Vlr Bono", 0)
                vlr_bono = parse_monetary(raw_vlr_bono, default=0)
                if con_bono == "NO":
                    vlr_bono = 0
                
                raw_link = emp_wv.get("Link Nomina Empleado")
                link_drive = str(raw_link or "").strip() if raw_link is not None else ""
                if link_drive.lower() in ["none", "null", "n/a", "na"]:
                    link_drive = ""
                    
                eps = str(extract_val(emp_wv, "EPS", "") or "").strip().upper()
                fondo_pensiones = str(extract_val(emp_wv, "FONDO DE PENSIONES", "") or "").strip().upper()

                raw_no_incluye = extract_val(emp_wv, "No Incluye Auxilio de Tte", True)
                val_no_incluye = str(raw_no_incluye).strip().upper()
                # Si el JSON dice FALSE/NO, invertimos y el resultado es SI (True)
                if val_no_incluye in ["FALSE", "0", "NO"]:
                    tiene_aux = "SI"
                else:
                    tiene_aux = "NO"

                insert_query = text("""
                    INSERT INTO m_empleados (
                        id_contrato, id_aportante, id_empleado, t_id_empleado, nombre_empleado, 
                        cargo, tipo_contrato, estado_empleado, periodo_pago, salario_base, vlr_bono, sal_especie, 
                        eps, afp, es_smlv, con_bono, tiene_aux, nombre_1, nombre_2, apellido_1, apellido_2,
                        departamento, municipio, riesgo_arl, ccf, arl, link_drive
                    ) VALUES (
                        :id_contrato, :id_aportante, :id_empleado, :t_id_empleado, :nombre_empleado,
                        :cargo, :tipo_contrato, :estado_empleado, :periodo_pago, :salario_base, :vlr_bono, :sal_especie,
                        :eps, :afp, :es_smlv, :con_bono, :tiene_aux, :nombre_1, :nombre_2, :apellido_1, :apellido_2,
                        :departamento, :municipio, :riesgo_arl, :ccf, :arl, :link_drive
                    ) ON CONFLICT (id_contrato) DO UPDATE SET 
                        nombre_empleado = COALESCE(EXCLUDED.nombre_empleado, m_empleados.nombre_empleado),
                        salario_base = COALESCE(EXCLUDED.salario_base, m_empleados.salario_base),
                        eps = COALESCE(EXCLUDED.eps, m_empleados.eps),
                        afp = COALESCE(EXCLUDED.afp, m_empleados.afp),
                        tiene_aux = COALESCE(EXCLUDED.tiene_aux, m_empleados.tiene_aux),
                        link_drive = COALESCE(EXCLUDED.link_drive, m_empleados.link_drive),
                        nombre_1 = COALESCE(EXCLUDED.nombre_1, m_empleados.nombre_1),
                        nombre_2 = COALESCE(EXCLUDED.nombre_2, m_empleados.nombre_2),
                        apellido_1 = COALESCE(EXCLUDED.apellido_1, m_empleados.apellido_1),
                        apellido_2 = COALESCE(EXCLUDED.apellido_2, m_empleados.apellido_2),
                        departamento = COALESCE(EXCLUDED.departamento, m_empleados.departamento),
                        municipio = COALESCE(EXCLUDED.municipio, m_empleados.municipio),
                        riesgo_arl = COALESCE(EXCLUDED.riesgo_arl, m_empleados.riesgo_arl),
                        ccf = COALESCE(EXCLUDED.ccf, m_empleados.ccf),
                        arl = COALESCE(EXCLUDED.arl, m_empleados.arl),
                        estado_empleado = COALESCE(EXCLUDED.estado_empleado, m_empleados.estado_empleado)
                """)
                fase_status = str(emp_wv.get("wolkvox_fase_status", "") or "").strip().lower()
                if fase_status == "lost":
                    estado_empleado_map = "RETIRADO"
                else:
                    estado_empleado_map = "ACTIVO"

                db.execute(insert_query, {
                    "id_contrato": llave_unica,
                    "id_aportante": id_aportante,
                    "id_empleado": id_empleado_str,
                    "t_id_empleado": tipo_id_empleado,
                    "nombre_empleado": nombre_completo,
                    "cargo": tipo_labor if tipo_labor else "NO ESPECIFICADO",
                    "tipo_contrato": tipo_contrato,
                    "estado_empleado": estado_empleado_map,
                    "periodo_pago": periodo_pago if periodo_pago else "QUINCENAL",
                    "salario_base": salario_base,
                    "vlr_bono": vlr_bono,
                    "sal_especie": salario_especie,
                    "eps": eps,
                    "afp": fondo_pensiones,
                    "es_smlv": True if es_smlv == "SI" else False,
                    "con_bono": True if con_bono == "SI" else False,
                    "tiene_aux": True if tiene_aux == "SI" else False,
                    "nombre_1": nombre_1,
                    "nombre_2": nombre_2,
                    "apellido_1": apellido_1,
                    "apellido_2": apellido_2,
                    "departamento": departamento,
                    "municipio": municipio,
                    "riesgo_arl": riesgo_arl,
                    "ccf": ccf,
                    "arl": nombre_arl,
                    "link_drive": link_drive
                })
                db.commit()
                
                empleados_limpios.append({
                    "ID_CONTRATO": llave_unica,
                    "ID_APORTANTE": id_aportante,
                    "ID_EMPLEADO": id_empleado_str,
                    "T_ID_EMPLEADO": tipo_id_empleado,
                    "NOMBRE_EMPLEADO": nombre_completo,
                    "CARGO_DESEMPENEADO": tipo_labor if tipo_labor else "NO ESPECIFICADO",
                    "TIPO_CONTRATO": tipo_contrato,
                    "ESTADO_EMPLEADO": estado_empleado_map,
                    "PERIODO_PAGO": periodo_pago if periodo_pago else "QUINCENAL",
                    "SALARIO_BASE": salario_base,
                    "VLR_BONO": vlr_bono,
                    "SALARIO_ESPECIE": salario_especie,
                    "EPS": eps,
                    "FONDO DE PENSIONES": fondo_pensiones,
                    "ES_SMLV": "SI" if es_smlv == "SI" else "NO",
                    "CON_BONO": "SI" if con_bono == "SI" else "NO",
                    "TIENE_AUX": "SI" if tiene_aux == "SI" else "NO",
                    "LINK_DRIVE": link_drive,
                    "RAZON_SOCIAL": razon_social
                })
            except Exception as e:
                db.rollback()
                logger.error(f"[ERROR-SYNC-EMPLEADOS] Fallo procesando empleado ID {raw_id_for_log}: {str(e)}")
                continue
                
        if target_empleado_id and not empleados_limpios:
            raise HTTPException(status_code=404, detail="El empleado no se encontró en las oportunidades del contacto.")
            
        return empleados_limpios

