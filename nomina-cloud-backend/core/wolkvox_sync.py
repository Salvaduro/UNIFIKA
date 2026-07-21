import os
import httpx
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

async def sync_empleados_from_wolkvox(id_aportante: str, razon_social: str, db: Session, target_empleado_id: str = None):
    """
    Función reutilizable para extraer empleados desde Wolkvox y hacer el upsert profundo de 28 columnas a m_empleados.
    Si target_empleado_id está presente, se filtra y procesa únicamente ese empleado.
    """
    id_aportante = str(id_aportante)
    if target_empleado_id is not None:
        target_empleado_id = str(target_empleado_id)
        
    wolkvox_token = os.getenv("WOLKVOX_TOKEN", "")
    url_wolkvox = "https://crm.wolkvox.com/server/API/v2/custom/query.php"
    headers = {"wolkvox-token": wolkvox_token, "Content-Type": "application/json"}
    
    payload_detalle = {
        "operation": "techcon",
        "wolkvox-token": wolkvox_token,
        "module": "opportunities",
        "field": "Contact",
        "value": razon_social
    }
    
    fixie_url = os.getenv("FIXIE_URL")
    client_kwargs = {"proxy": fixie_url} if fixie_url else {}
    
    async with httpx.AsyncClient(**client_kwargs) as client:
        resp_det = await client.post(url_wolkvox, json=payload_detalle, headers=headers)
        if resp_det.status_code >= 400:
            import logging
            logger = logging.getLogger("uvicorn")
            logger.error(f"[WOLKVOX/FIXIE ERROR] Status: {resp_det.status_code}, Body: {resp_det.text}")
            raise HTTPException(status_code=403, detail=f"Error en proveedor externo: {resp_det.text}")
        resp_det.raise_for_status()
        data_det = resp_det.json()
        
        if not data_det.get("data") or len(data_det["data"]) == 0:
            if target_empleado_id:
                raise HTTPException(status_code=404, detail="Empleado no encontrado en Wolkvox.")
            return []
            
        def extract_val(d, key, default=None):
            val = d.get(key)
            if isinstance(val, dict):
                if 'convert' in val and val['convert'] is not None:
                    return val['convert']
                return val.get("value", default)
            return val if val is not None else default

        empleados_limpios = []
        for emp_wv in data_det["data"]:
            if target_empleado_id:
                if str(emp_wv.get("ID Empleado", "")) != str(target_empleado_id):
                    continue
                    
            if emp_wv.get("wolkvox_fase") == "Retirado":
                continue

            id_opp = str(emp_wv.get("id", ""))
            raw_id_empleado = emp_wv.get("ID Empleado")
            id_empleado_str = str(raw_id_empleado) if raw_id_empleado else id_opp
            
            if not id_empleado_str or str(id_empleado_str) == str(id_aportante):
                id_empleado_str = str(emp_wv.get("contact_id") or id_opp)
            
            if not id_empleado_str:
                continue
                
            llave_unica = f"{id_aportante}_{id_empleado_str}"

            nombre_completo = emp_wv.get("Nombre del Empleado", "")
            if not nombre_completo:
                nombre_completo = extract_val(emp_wv, "Nombre del Empleado", "")

            nombre_1 = emp_wv.get("NOMBRE_1", "")
            nombre_2 = emp_wv.get("NOMBRE_2", "")
            apellido_1 = emp_wv.get("APELLIDO_1", "")
            apellido_2 = emp_wv.get("APELLIDO_2", "")
            departamento = emp_wv.get("Departamento", "")
            municipio = emp_wv.get("Municipio", "")
            riesgo_arl = emp_wv.get("Tipo de Riesgo ARL", "")
            ccf = emp_wv.get("CAJA COMPENSACION", "")
            nombre_arl = emp_wv.get("ARL", "")
            
            tipo_id_empleado = extract_val(emp_wv, "Tipo ID Empleado", "")
            tipo_contrato = extract_val(emp_wv, "Condicion Laboral", "TIEMPO COMPLETO")
            tipo_labor = extract_val(emp_wv, "Tipo de Labor", "")
            periodo_pago = extract_val(emp_wv, "Frecuencia de Pago", "QUINCENAL")
            es_smlv = extract_val(emp_wv, "Salario Minimo", "SI")
            salario_base = extract_val(emp_wv, "Salario Base", 1750905)
            salario_especie = extract_val(emp_wv, "Salario en Especie", 0)
            con_bono = extract_val(emp_wv, "Bono NO Salarial", "NO")
            vlr_bono = extract_val(emp_wv, "Vlr Bono", 0)
            raw_link = emp_wv.get("Link Nomina Empleado")
            link_drive = str(raw_link).strip() if raw_link else ""
            if link_drive.lower() in ["none", "null", "n/a", "na"]:
                link_drive = ""
                
            eps = extract_val(emp_wv, "EPS", "")
            fondo_pensiones = extract_val(emp_wv, "FONDO DE PENSIONES", "")

            raw_no_incluye = extract_val(emp_wv, "No Incluye Auxilio de Tte", "")
            val_no_incluye = str(raw_no_incluye).strip().upper() if raw_no_incluye is not None else ""
            if val_no_incluye in ["", "NO", "FALSE", "0", "NULL", "NONE"]:
                tiene_aux = "SI"
            else:
                tiene_aux = "NO"

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

            if str(con_bono).strip().upper() == "NO":
                vlr_bono = 0

            try:
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
                        nombre_empleado = EXCLUDED.nombre_empleado,
                        salario_base = EXCLUDED.salario_base,
                        eps = EXCLUDED.eps,
                        afp = EXCLUDED.afp,
                        link_drive = EXCLUDED.link_drive,
                        nombre_1 = EXCLUDED.nombre_1,
                        nombre_2 = EXCLUDED.nombre_2,
                        apellido_1 = EXCLUDED.apellido_1,
                        apellido_2 = EXCLUDED.apellido_2,
                        departamento = EXCLUDED.departamento,
                        municipio = EXCLUDED.municipio,
                        riesgo_arl = EXCLUDED.riesgo_arl,
                        ccf = EXCLUDED.ccf,
                        arl = EXCLUDED.arl,
                        estado_empleado = EXCLUDED.estado_empleado
                """)
                db.execute(insert_query, {
                    "id_contrato": llave_unica,
                    "id_aportante": id_aportante,
                    "id_empleado": id_empleado_str,
                    "t_id_empleado": str(tipo_id_empleado).upper(),
                    "nombre_empleado": nombre_completo,
                    "cargo": str(tipo_labor).upper() if tipo_labor else "NO ESPECIFICADO",
                    "tipo_contrato": str(tipo_contrato).upper(),
                    "estado_empleado": emp_wv.get("ESTADO_EMPLEADO", "ACTIVO"),
                    "periodo_pago": str(periodo_pago).upper() if periodo_pago else "QUINCENAL",
                    "salario_base": salario_base,
                    "vlr_bono": vlr_bono,
                    "sal_especie": salario_especie,
                    "eps": str(eps),
                    "afp": str(fondo_pensiones),
                    "es_smlv": True if str(es_smlv).upper() == "SI" else False,
                    "con_bono": True if str(con_bono).upper() == "SI" else False,
                    "tiene_aux": True if str(tiene_aux).upper() == "SI" else False,
                    "nombre_1": str(nombre_1).upper(),
                    "nombre_2": str(nombre_2).upper(),
                    "apellido_1": str(apellido_1).upper(),
                    "apellido_2": str(apellido_2).upper(),
                    "departamento": str(departamento).upper(),
                    "municipio": str(municipio).upper(),
                    "riesgo_arl": str(riesgo_arl).upper(),
                    "ccf": str(ccf).upper(),
                    "arl": str(nombre_arl).upper(),
                    "link_drive": link_drive
                })
                db.commit()
                
                empleados_limpios.append({
                    "ID_CONTRATO": llave_unica,
                    "ID_APORTANTE": id_aportante,
                    "ID_EMPLEADO": id_empleado_str,
                    "T_ID_EMPLEADO": str(tipo_id_empleado).upper(),
                    "NOMBRE_EMPLEADO": nombre_completo,
                    "CARGO_DESEMPENEADO": str(tipo_labor).upper() if tipo_labor else "NO ESPECIFICADO",
                    "TIPO_CONTRATO": str(tipo_contrato).upper(),
                    "ESTADO_EMPLEADO": emp_wv.get("ESTADO_EMPLEADO", "ACTIVO"),
                    "PERIODO_PAGO": str(periodo_pago).upper() if periodo_pago else "QUINCENAL",
                    "SALARIO_BASE": salario_base,
                    "VLR_BONO": vlr_bono,
                    "SALARIO_ESPECIE": salario_especie,
                    "EPS": str(eps),
                    "FONDO DE PENSIONES": str(fondo_pensiones),
                    "ES_SMLV": "SI" if str(es_smlv).upper() == "SI" else "NO",
                    "CON_BONO": "SI" if str(con_bono).upper() == "SI" else "NO",
                    "TIENE_AUX": "SI" if str(tiene_aux).upper() == "SI" else "NO",
                    "LINK_DRIVE": link_drive,
                    "RAZON_SOCIAL": razon_social
                })
            except Exception as e:
                db.rollback()
                print(f"[SYNC ERROR] Error guardando empleado {id_empleado_str}: {str(e)}")
                
        if target_empleado_id and not empleados_limpios:
            raise HTTPException(status_code=404, detail="El empleado no se encontró en las oportunidades del contacto.")
            
        return empleados_limpios
