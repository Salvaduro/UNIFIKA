import sys
import os
import uuid
from dotenv import load_dotenv

# Aseguramos que Python encuentre el backend para importar database y models
backend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "nomina-cloud-backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)

# Cargamos el .env del backend
load_dotenv(os.path.join(backend_path, ".env"))

from database import SessionLocal
from models import Novedad, CierreNomina, AuditoriaLog

def sellar_historicos():
    print("Iniciando el proceso de Cierre Masivo Histórico...")
    db = SessionLocal()
    
    try:
        # 1. Obtener cierres existentes en memoria para evitar duplicados
        print("Obteniendo candados existentes...")
        cierres_query = db.query(CierreNomina.id_contrato, CierreNomina.periodo_liq, CierreNomina.quincena_pago).all()
        cierres_existentes = {(c[0], c[1], c[2]) for c in cierres_query}
        
        # 2. Obtener todas las novedades únicas
        print("Obteniendo novedades históricas...")
        novedades_unicas = db.query(Novedad.id_contrato, Novedad.periodo_liq, Novedad.quincena_pago).distinct().all()
        
        # 3. Filtrar novedades que no tienen cierre y preparar los objetos
        cierres_a_insertar = []
        for n in novedades_unicas:
            tupla = (n[0], n[1], n[2])
            if tupla not in cierres_existentes:
                nuevo_cierre = CierreNomina(
                    id_cierre=str(uuid.uuid4()),
                    id_contrato=n[0],
                    periodo_liq=n[1],
                    quincena_pago=n[2],
                    cerrado_por="SISTEMA_MIGRACION"
                )
                cierres_a_insertar.append(nuevo_cierre)
        
        # 4. Inserción masiva
        total_cerrados = len(cierres_a_insertar)
        if total_cerrados > 0:
            print(f"Insertando {total_cerrados} nuevos candados...")
            db.bulk_save_objects(cierres_a_insertar)
            
            # 5. Auditoría
            print("Generando registro de auditoría...")
            log = AuditoriaLog(
                id_log=str(uuid.uuid4()), # Por si acaso tampoco tiene autogenerador
                usuario_email="SISTEMA_MIGRACION",
                rol_usuario="SISTEMA",
                tipo_accion="CIERRE_HISTORICO_MASIVO",
                detalles={"registros_cerrados": total_cerrados, "comentario": "Cierre masivo inicial post-migración"}
            )
            db.add(log)
            
            # 6. Commit definitivo
            db.commit()
            print(f"¡ÉXITO! Se han sellado permanentemente {total_cerrados} nóminas históricas.")
        else:
            print("No hay nóminas pendientes por sellar. Todo está al día.")
            db.rollback()

    except Exception as e:
        print(f"\n[ERROR CRÍTICO] Ocurrió un error al sellar históricos: {e}")
        db.rollback()
        print("Rollback de emergencia ejecutado.")
    finally:
        db.close()

if __name__ == "__main__":
    sellar_historicos()
