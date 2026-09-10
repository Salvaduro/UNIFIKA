import pandas as pd
import os
import logging

# Directorio base del proyecto (2 niveles arriba de core/)
# Asume que el archivo está en c:\UNIFIKA-Nomina-Cloud\nomina-cloud-backend\core\
# El directorio del proyecto es c:\UNIFIKA-Nomina-Cloud\
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
ADMINISTRADORAS_EXCEL = os.path.join(BASE_DIR, "Codigos_ Administradoras.xlsx")
MUNICIPIOS_EXCEL = os.path.join(BASE_DIR, "municipios.xlsx")

TIPO_DOC_CATALOGO = {
    "CC": "CC", "NI": "NI", "CE": "CE", "PA": "PA", "TI": "TI",
    "RC": "RC", "CD": "CD", "SC": "SC", "PE": "PE", "PT": "PT"
}

_eps_catalogo = {}
_afp_catalogo = {}
_arl_catalogo = {}
_ccf_catalogo = {}
_divipola_df = None
_catalogs_loaded = False

def _load_catalogs():
    global _eps_catalogo, _afp_catalogo, _arl_catalogo, _ccf_catalogo, _divipola_df, _catalogs_loaded
    if _catalogs_loaded:
        return

    # Load Administradoras
    if os.path.exists(ADMINISTRADORAS_EXCEL):
        try:
            xls = pd.ExcelFile(ADMINISTRADORAS_EXCEL)
            for sheet_name in xls.sheet_names:
                df = pd.read_excel(xls, sheet_name=sheet_name)
                if df.empty or len(df.columns) < 2:
                    continue
                    
                # Assuming first two columns are name and code
                for _, row in df.iterrows():
                    # Check for null values before proceeding
                    if pd.isna(row.iloc[0]) or pd.isna(row.iloc[1]):
                        continue
                        
                    name = str(row.iloc[0]).strip().upper()
                    code = str(row.iloc[1]).strip()
                    
                    # Store based on sheet name, or infer from headers if sheet names are generic
                    if "EPS" in sheet_name.upper():
                        _eps_catalogo[name] = code
                    elif "AFP" in sheet_name.upper():
                        _afp_catalogo[name] = code
                    elif "ARL" in sheet_name.upper():
                        _arl_catalogo[name] = code
                    elif "CCF" in sheet_name.upper() or "CAJA" in sheet_name.upper():
                        _ccf_catalogo[name] = code
        except Exception as e:
            logging.error(f"Error loading Codigos_ Administradoras.xlsx: {e}")
    else:
        logging.error(f"File not found: {ADMINISTRADORAS_EXCEL}")

    # Load Municipios
    if os.path.exists(MUNICIPIOS_EXCEL):
        try:
            _divipola_df = pd.read_excel(MUNICIPIOS_EXCEL, dtype=str)
        except Exception as e:
            logging.error(f"Error loading municipios.xlsx: {e}")
            _divipola_df = None
    else:
        logging.error(f"File not found: {MUNICIPIOS_EXCEL}")

    _catalogs_loaded = True

def get_codigo_eps(nombre: str) -> str:
    if not _catalogs_loaded:
        _load_catalogs()
    if not nombre:
        return ""
    return _eps_catalogo.get(str(nombre).strip().upper(), "")

def get_codigo_afp(nombre: str) -> str:
    if not _catalogs_loaded:
        _load_catalogs()
    if not nombre:
        return ""
    return _afp_catalogo.get(str(nombre).strip().upper(), "")

def get_codigo_arl(nombre: str) -> str:
    if not _catalogs_loaded:
        _load_catalogs()
    if not nombre:
        return ""
    return _arl_catalogo.get(str(nombre).strip().upper(), "")

def get_codigo_ccf(nombre: str) -> str:
    if not _catalogs_loaded:
        _load_catalogs()
    if not nombre:
        return ""
    return _ccf_catalogo.get(str(nombre).strip().upper(), "")

def obtener_codigo_ubicacion(departamento_nombre: str, municipio_nombre: str) -> dict:
    if not _catalogs_loaded:
        _load_catalogs()
        
    default_ubicacion = {"departamento": "11", "municipio": "001"}
    
    if not departamento_nombre or not municipio_nombre:
        return default_ubicacion
        
    if _divipola_df is None or _divipola_df.empty:
        return default_ubicacion
        
    depto_str = str(departamento_nombre).strip().upper()
    muni_str = str(municipio_nombre).strip().upper()
    
    try:
        # Infer column names
        col_depto_cod = [c for c in _divipola_df.columns if 'código departamento' in c.lower() or 'cod_depto' in c.lower() or 'código dp' in c.lower()][0]
        col_depto_nom = [c for c in _divipola_df.columns if 'nombre departamento' in c.lower() or 'departamento' == c.lower()][0]
        col_muni_cod = [c for c in _divipola_df.columns if 'código municipio' in c.lower() or 'cod_municipio' in c.lower() or 'código mp' in c.lower()][0]
        col_muni_nom = [c for c in _divipola_df.columns if 'nombre municipio' in c.lower() or 'municipio' == c.lower()][0]
        
        # Filter dataframe
        mask = (_divipola_df[col_depto_nom].str.strip().str.upper() == depto_str) & \
               (_divipola_df[col_muni_nom].str.strip().str.upper() == muni_str)
               
        match = _divipola_df[mask]
        if not match.empty:
            d_cod = str(match.iloc[0][col_depto_cod]).strip().zfill(2)
            m_cod = str(match.iloc[0][col_muni_cod]).strip()
            
            # Clean municipio code if it includes depto code
            if len(m_cod) > 3 and m_cod.startswith(d_cod):
                m_cod = m_cod[len(d_cod):].zfill(3)
            else:
                m_cod = m_cod.zfill(3)
                
            return {"departamento": d_cod, "municipio": m_cod}
            
    except Exception as e:
        logging.error(f"Error inferring divipola logic: {e}")
        
    return default_ubicacion
