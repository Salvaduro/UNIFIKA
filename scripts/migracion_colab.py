import sys
import os
import pandas as pd
import numpy as np
import uuid
from dotenv import load_dotenv

# Aseguramos que Python encuentre el backend para importar database y models
backend_path = os.path.join(os.path.dirname(__file__), "nomina-cloud-backend")
if backend_path not in sys.path:
    sys.path.append(backend_path)

# Cargamos el .env del backend para que DATABASE_URL esté disponible
load_dotenv(os.path.join(backend_path, ".env"))

from database import SessionLocal
from models import Aportante, Empleado, Novedad

def procesar_dataframe(df, model_class):
    """
    Convierte encabezados a minúsculas, aplica mapeos de excepciones, 
    convierte Nulos a None nativo y filtra columnas válidas para el modelo.
    """
    # 1. Convertir todas las columnas a minúsculas
    df.columns = df.columns.str.lower()
    
    # 2. Casteo Dirigido de Identificadores (antes del mapeo)
    identificadores = ['id_aportante', 'id_contrato', 'documento', 'telefono', 'id_novedad']
    
    def limpiar_id(val):
        if pd.isnull(val):
            return val
        s = str(val).strip()
        # Limpiamos el ".0" solo si está al final, para no afectar otros textos
        if s.endswith('.0'):
            return s[:-2]
        return s

    for col in identificadores:
        if col in df.columns:
            df[col] = df[col].apply(limpiar_id)
            
    # 3. Aplicar mapeos explícitos para excepciones (Excel -> DB)
    # Según la instrucción: id_empleado corresponde a documento en el excel, 
    # y nombre_empleado corresponde a nombre en el excel.
    mapeo = {
        "documento": "id_empleado",
        "nombre": "nombre_empleado"
    }
    df = df.rename(columns=mapeo)
    
    # 4. Manejo de Nulos: Convertir NaN / NaT a None
    df = df.replace({np.nan: None, pd.NaT: None})
    df = df.where(pd.notnull(df), None)
    
    # 4. Obtener las columnas válidas del modelo ORM
    valid_keys = [c.name for c in model_class.__table__.columns]
    
    return df, valid_keys

def run_migration():
    excel_path = "Liquidacion_de_Salarios_Parametrizada.xlsx"
    
    if not os.path.exists(excel_path):
        print(f"Error: No se encontró el archivo {excel_path}")
        return

    print(f"Cargando archivo Excel: {excel_path}")
    xls = pd.ExcelFile(excel_path)
    
    db = SessionLocal()
    
    try:
        procesados = 0
        
        # --- 1. M_APORTANTES ---
        # if "M_APORTANTES" in xls.sheet_names:
        #     print("\n--- Procesando M_APORTANTES ---")
        #     df = pd.read_excel(xls, "M_APORTANTES")
        #     df, valid_keys = procesar_dataframe(df, Aportante)
        #     
        #     for _, row in df.iterrows():
        #         data = row.to_dict()
        #         filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        #         
        #         print(f"Preparando inserción de Aportante: {filtered_data.get('id_aportante')}")
        #         obj = Aportante(**filtered_data)
        #         db.merge(obj)
        # else:
        #     print("\nHoja M_APORTANTES no encontrada, omitiendo.")

        # --- 2. M_EMPLEADOS ---
        # if "M_EMPLEADOS" in xls.sheet_names:
        #     print("\n--- Procesando M_EMPLEADOS ---")
        #     df = pd.read_excel(xls, "M_EMPLEADOS")
        #     df, valid_keys = procesar_dataframe(df, Empleado)
        #     
        #     for _, row in df.iterrows():
        #         data = row.to_dict()
        #         filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        #         
        #         print(f"Preparando inserción de Empleado: {filtered_data.get('id_empleado')}")
        #         obj = Empleado(**filtered_data)
        #         db.merge(obj)
        # else:
        #     print("\nHoja M_EMPLEADOS no encontrada, omitiendo.")

        # --- 3. T_NOVEDADES ---
        if "T_NOVEDADES" in xls.sheet_names:
            print("\n--- Procesando T_NOVEDADES ---")
            
            print("Extrayendo llaves válidas de m_empleados...")
            contratos_validos = {c[0] for c in db.query(Empleado.id_contrato).all()}
            
            print("Extrayendo novedades existentes para deduplicación...")
            novedades_existentes = {(n[0], n[1], str(n[2]) if n[2] is not None else None) for n in db.query(Novedad.id_contrato, Novedad.periodo_liq, Novedad.quincena_pago).all()}
            
            df = pd.read_excel(xls, "T_NOVEDADES")
            df, valid_keys = procesar_dataframe(df, Novedad)
            
            # Deduplicación de Pandas (Eliminar duplicados internos del Excel)
            df = df.drop_duplicates(subset=['id_contrato', 'periodo_liq', 'quincena_pago'], keep='last')
            
            for _, row in df.iterrows():
                data = row.to_dict()
                
                id_contrato = data.get('id_contrato')
                
                # Proteger la base de datos de filas vacías
                if not id_contrato:
                    continue
                    
                # Proteger contra registros huérfanos
                if id_contrato not in contratos_validos:
                    print(f"[WARNING] Omitiendo registro huérfano (contrato inexistente): {id_contrato}")
                    continue
                    
                # Alinear tipos para la búsqueda en memoria (quincena a string sin .0)
                periodo_actual = data.get('periodo_liq')
                quincena_raw = data.get('quincena_pago')
                quincena_actual = str(quincena_raw).replace('.0', '') if quincena_raw is not None else None
                
                # Proteger contra duplicados en base de datos
                if (id_contrato, periodo_actual, quincena_actual) in novedades_existentes:
                    print(f"[WARNING] Omitiendo novedad duplicada en BD: {id_contrato} | {periodo_actual} | {quincena_actual}")
                    continue
                    
                filtered_data = {k: v for k, v in data.items() if k in valid_keys}
                
                # SQLAlchemy exige un primary_key no nulo. Generamos un UUID si el Excel no lo trae.
                if not filtered_data.get('id_novedad'):
                    filtered_data['id_novedad'] = str(uuid.uuid4())
                
                print(f"Preparando inserción de Novedad: {filtered_data.get('id_novedad')}")
                obj = Novedad(**filtered_data)
                db.merge(obj)
                procesados += 1
        else:
            print("\nHoja T_NOVEDADES no encontrada, omitiendo.")

        # --- FIN DEL PROCESAMIENTO ---
        print("\n--- RESUMEN ---")
        print(f"¡MIGRACIÓN HISTÓRICA EXITOSA! Los {procesados} registros de T_NOVEDADES han sido inyectados permanentemente.")
        db.commit()

    except Exception as e:
        print(f"\n[ERROR CRÍTICO] Ocurrió un error durante la migración: {e}")
        db.rollback()
        print("Rollback de emergencia ejecutado.")
    finally:
        db.close()

if __name__ == "__main__":
    run_migration()
