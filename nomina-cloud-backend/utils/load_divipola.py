import pandas as pd
import json
import os

def load_divipola():
    """
    Lee el archivo municipios.xlsx de la raíz del proyecto y lo convierte a divipola.json en core/
    """
    # Rutas
    base_dir = os.path.dirname(os.path.dirname(__file__))
    excel_path = os.path.join(os.path.dirname(base_dir), "municipios.xlsx")
    
    # En caso de que se pase al backend folder:
    if not os.path.exists(excel_path):
        excel_path = os.path.join(base_dir, "municipios.xlsx")

    out_path = os.path.join(base_dir, "core", "divipola.json")
    
    if not os.path.exists(excel_path):
        print(f"Error: No se encontró el archivo en {excel_path}")
        return

    print(f"Leyendo archivo excel desde {excel_path}...")
    try:
        # Se asume que el excel tiene las columnas que corresponden al divipola, 
        # Típicamente: Codigo Departamento, Nombre Departamento, Codigo Municipio, Nombre Municipio
        # Asumimos que podemos leer los headers.
        df = pd.read_excel(excel_path, dtype=str)
        
        # Intentar inferir nombres de columnas si son estándar
        col_depto_cod = [c for c in df.columns if 'código departamento' in c.lower() or 'cod_depto' in c.lower() or 'código dp' in c.lower()][0]
        col_depto_nom = [c for c in df.columns if 'nombre departamento' in c.lower() or 'departamento' == c.lower()][0]
        col_muni_cod = [c for c in df.columns if 'código municipio' in c.lower() or 'cod_municipio' in c.lower() or 'código mp' in c.lower()][0]
        col_muni_nom = [c for c in df.columns if 'nombre municipio' in c.lower() or 'municipio' == c.lower()][0]
        
        divipola = {}
        
        for _, row in df.iterrows():
            d_cod = str(row[col_depto_cod]).strip().zfill(2)
            d_nom = str(row[col_depto_nom]).strip().upper()
            m_cod = str(row[col_muni_cod]).strip()
            
            # El código de municipio suele venir como concatenado "11001", necesitamos aislar el "001" si es el caso
            if len(m_cod) > 3 and m_cod.startswith(d_cod):
                m_cod = m_cod[len(d_cod):].zfill(3)
            else:
                m_cod = m_cod.zfill(3)
                
            m_nom = str(row[col_muni_nom]).strip().upper()
            
            if d_cod not in divipola:
                divipola[d_cod] = {
                    "nombre": d_nom,
                    "municipios": {}
                }
            
            divipola[d_cod]["municipios"][m_cod] = m_nom
            
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(divipola, f, indent=2, ensure_ascii=False)
            
        print(f"Éxito: divipola.json generado correctamente en {out_path} con {len(divipola)} departamentos.")
        
    except Exception as e:
        print(f"Error procesando DIVIPOLA: {e}")
        # Volcado simple si falla la inferencia
        print("Asegúrate de que las columnas se llamen parecido a: 'Código Departamento', 'Nombre Departamento', 'Código Municipio', 'Nombre Municipio'.")

if __name__ == "__main__":
    load_divipola()
