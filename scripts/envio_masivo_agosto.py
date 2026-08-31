import sys
import os
import time
import base64
import resend
from dotenv import load_dotenv

# Path Resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../nomina-cloud-backend')))

# Environment Loading
load_dotenv(os.path.join(os.path.dirname(__file__), '../nomina-cloud-backend/.env'))
resend.api_key = os.getenv("RESEND_API_KEY")

from database import SessionLocal
from models import Aportante, Empleado, Novedad
from main import generar_comprobante, liquidar_nomina

PERIODO_OBJETIVO = "AGOSTO 2026"
QUINCENA_OBJETIVO = "1"
# TARGET_PRUEBA eliminado para liberar el script a todos los aportantes

def enviar_desprendibles_agosto():
    print(f"Iniciando envío masivo TOTAL | Periodo: {PERIODO_OBJETIVO} | Quincena: {QUINCENA_OBJETIVO}")
    db = SessionLocal()
    
    try:
        # Query: t_novedades + m_empleados + m_aportantes
        resultados = db.query(Novedad, Empleado, Aportante).join(
            Empleado, Novedad.id_contrato == Empleado.id_contrato
        ).outerjoin(
            Aportante, Empleado.id_aportante == Aportante.id_aportante
        ).filter(
            Novedad.periodo_liq == PERIODO_OBJETIVO,
            Novedad.quincena_pago == QUINCENA_OBJETIVO
        ).all()
        
        if not resultados:
            print("No se encontraron novedades para los criterios especificados.")
            return
            
        aportantes_dict = {}
        for n, e, a in resultados:
            if not a:
                continue
            if a.id_aportante not in aportantes_dict:
                aportantes_dict[a.id_aportante] = {'aportante': a, 'empleados': []}
            aportantes_dict[a.id_aportante]['empleados'].append((n, e, a))
            
        print(f"Se encontraron {len(aportantes_dict)} aportantes y {len(resultados)} empleados para procesar.")
        
        for id_aport, data in aportantes_dict.items():
            a_obj = data['aportante']
            aportante_correo = a_obj.email if hasattr(a_obj, 'email') else None
            
            if not aportante_correo:
                print(f"Advertencia: El aportante {a_obj.razon_social} ({id_aport}) no tiene un email configurado. Omitiendo.")
                continue
                
            attachments = []
            
            print(f"\n--- Procesando Aportante: {a_obj.razon_social} ({id_aport}) ---")
            for n, e, a in data['empleados']:
                print(f"  Generando PDF para empleado: {e.nombre_empleado}")
                
                row_dict = {
                    **e.__dict__,
                    **n.__dict__,
                    "razon_social": a.razon_social if a else "SIN EMPRESA",
                    "tipo_documento": a.tipo_documento if a else "NIT",
                    "tipo_empleador": a.tipo_empleador if a else ""
                }
                row_dict.pop('_sa_instance_state', None)
                
                # Capitalize to align with factory
                row_dict = {k.upper(): v for k, v in row_dict.items()}
                
                if 'SALARIO_BASE_NOVEDAD' in row_dict and row_dict['SALARIO_BASE_NOVEDAD'] is not None:
                    row_dict['SALARIO_BASE'] = row_dict['SALARIO_BASE_NOVEDAD']
                if 'VLR_BONO_NOVEDAD' in row_dict and row_dict['VLR_BONO_NOVEDAD'] is not None:
                    row_dict['VALOR_BONO'] = row_dict['VLR_BONO_NOVEDAD']
                if 'SAL_ESPECIE_NOVEDAD' in row_dict and row_dict['SAL_ESPECIE_NOVEDAD'] is not None:
                    row_dict['SALARIO_ESPECIE_MES'] = row_dict['SAL_ESPECIE_NOVEDAD']
                    
                row_dict['VALOR_BONO'] = float(row_dict.get('VALOR_BONO') or row_dict.get('VLR_BONO') or 0.0)
                row_dict['SALARIO_ESPECIE_MES'] = float(row_dict.get('SALARIO_ESPECIE_MES') or row_dict.get('SAL_ESPECIE') or 0.0)
                row_dict['SALARIO_BASE'] = float(row_dict.get('SALARIO_BASE') or 0.0)
                    
                # Salvaguardar Inmutabilidad Histórica
                db_salud = float(row_dict.get('SALUD_4') or 0.0)
                db_pension = float(row_dict.get('PENSION_4') or 0.0)
                db_total_deducido = float(row_dict.get('TOTAL_DEDUCIDO') or 0.0)
                db_total_devengado = float(row_dict.get('TOTAL_DEVENGADO') or 0.0)
                db_neto_pagar = float(row_dict.get('NETO_PAGAR') or 0.0)
                db_ibc_pila = float(row_dict.get('IBC_PILA') or 0.0)
                
                pdf_bytes = None
                
                try:
                    # Re-liquidamos en vuelo EXCLUSIVAMENTE para recuperar el desglose visual
                    resultado_liquidado = liquidar_nomina([row_dict], {})
                    if resultado_liquidado:
                        resultado_final = resultado_liquidado[0]
                        
                        # Restaurar metadata clave
                        for key in ['RAZON_SOCIAL', 'TIPO_DOCUMENTO', 'TIPO_EMPLEADOR', 'ID_APORTANTE', 
                                    'PERIODO_LIQ', 'QUINCENA_PAGO', 'OBSERVACIONES', 'CARGO', 
                                    'TIPO_CONTRATO', 'T_ID_EMPLEADO', 'ID_EMPLEADO']:
                            resultado_final[key] = row_dict.get(key, '')
                        
                        resultado_final['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
                        
                        # CRITICO: Sobreescritura de Inmutabilidad
                        resultado_final['SALUD_4'] = db_salud
                        resultado_final['PENSION_4'] = db_pension
                        resultado_final['TOTAL_DEDUCIDO'] = db_total_deducido
                        resultado_final['TOTAL_DEVENGADO'] = db_total_devengado
                        resultado_final['NETO_PAGAR'] = db_neto_pagar
                        resultado_final['IBC_PILA'] = db_ibc_pila
                        
                        if not resultado_final.get('SAL_REF'):
                            resultado_final['SAL_REF'] = 1750905 if str(resultado_final.get('ES_SMLV')).upper() in ['SI', 'TRUE', '1'] else float(resultado_final.get('SALARIO_BASE') or 0.0)

                        resp = generar_comprobante(resultado_final)
                        if hasattr(resp, "body"):
                            pdf_bytes = resp.body
                except Exception as ex:
                    print(f"Error liquidando {e.nombre_empleado}: {ex}")
                    
                # Fallback en caso de fallo matemático
                if not pdf_bytes:
                    row_dict['SALUD_4'] = db_salud
                    row_dict['PENSION_4'] = db_pension
                    row_dict['TOTAL_DEDUCIDO'] = db_total_deducido
                    row_dict['TOTAL_DEVENGADO'] = db_total_devengado
                    row_dict['NETO_PAGAR'] = db_neto_pagar
                    row_dict['IBC_PILA'] = db_ibc_pila
                    if not row_dict.get('SAL_REF'):
                        row_dict['SAL_REF'] = 1750905 if str(row_dict.get('ES_SMLV')).upper() in ['SI', 'TRUE', '1'] else float(row_dict.get('SALARIO_BASE') or 0.0)
                    row_dict['tipo_empleador'] = row_dict.get('TIPO_EMPLEADOR', '')
                    
                    resp = generar_comprobante(row_dict)
                    if hasattr(resp, "body"):
                        pdf_bytes = resp.body
                        
                if pdf_bytes:
                    encoded_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
                    nombre_archivo = f"Desprendible_{e.id_empleado}_{PERIODO_OBJETIVO.replace(' ', '_')}_Q{QUINCENA_OBJETIVO}.pdf"
                    
                    attachments.append({
                        "content": encoded_pdf,
                        "filename": nombre_archivo
                    })
                    
            if attachments:
                print(f"  -> Generación completada. Despachando {len(attachments)} adjuntos a {aportante_correo}...")
                
                html_body = f"""
                <div style="font-family: Arial, sans-serif; color: #333; line-height: 1.6; max-width: 600px; margin: auto; padding: 20px; border: 1px solid #ddd; border-radius: 10px;">
                    <h2 style="color: #2c3e50; text-align: center;">Comprobantes de Nómina</h2>
                    <p>Estimado Empleador,</p>
                    <p>Adjuntamos a este correo los comprobantes de nómina históricos de sus empleados correspondientes al periodo <strong>{PERIODO_OBJETIVO}</strong>, quincena <strong>{QUINCENA_OBJETIVO}</strong>.</p>
                    <p>Estos desprendibles ya se encuentran disponibles en su portal <strong>UNIFIKA Nómina Cloud</strong>.</p>
                    <br>
                    <p style="text-align: center; color: #7f8c8d; font-size: 12px;">Generado automáticamente por el equipo de UNIFIKA.</p>
                </div>
                """
                
                try:
                    response = resend.Emails.send({
                        "from": "nomina@unifika.co",
                        "to": aportante_correo,
                        "subject": f"Sus Desprendibles de Nómina - {PERIODO_OBJETIVO} Q{QUINCENA_OBJETIVO}",
                        "html": html_body,
                        "attachments": attachments
                    })
                    print(f"  -> Correo despachado exitosamente. API Response: {response}")
                    time.sleep(0.5)
                except Exception as e:
                    print(f"  -> Error crítico en el despachador de Resend para {aportante_correo}: {e}")
            else:
                print("  -> No se logró empaquetar ningún PDF para enviar.")

    except Exception as e:
        print(f"Error crítico de ejecución: {e}")
    finally:
        db.close()
        print("Conexión de solo-lectura cerrada.")

if __name__ == "__main__":
    enviar_desprendibles_agosto()
