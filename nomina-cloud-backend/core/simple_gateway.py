import httpx
import json
import logging

logger = logging.getLogger("uvicorn")

class SimpleGateway:
    def __init__(self):
        self.base_url = "https://reportes.pagosimple.com.co/apis/back-api-simple/v1/local/api-simple"
        self.nit = "900623820"
        self.document = "79624350"
        
        self.login_payload = {
            "document_type": "CC",
            "document": self.document,
            "password": "4350",
            "secret_key": "ANIcT3gZWlNLlxK3VJ5QXWUuc63O8DoV7WfUsPIiZJg",
            "nit": self.nit,
            "company": "f2b030d9b06accc2bee366c3c383de5037eef49a15855e62b33194cb7a255740017f5aa67cac1e594098dcb6ab7a67ca6a784050be11da59f40207ce1b988554"
        }

    def validar_planilla(self, txt_bytes: bytes, nombre_archivo: str = "PILA_LOCAL.txt"):
        """Orquesta el flujo completo: Login -> Auth -> Validate"""
        try:
            with httpx.Client(timeout=30.0) as client:
                # --- PASO 1: LOGIN ---
                login_url = f"{self.base_url}/auth/login"
                resp_login = client.post(login_url, json=self.login_payload)
                
                # Guardamos el JSON crudo para depurar
                raw_login_json = resp_login.json()
                
                # Si la API retorna error pero con status 200 OK
                if not raw_login_json.get("success", True):
                    raise ValueError(f"El Login fue rechazado por el operador: {json.dumps(raw_login_json)}")

                data_login = raw_login_json.get("data")
                if not data_login:
                    raise ValueError(f"La API no devolvió el nodo 'data'. Respuesta cruda: {json.dumps(raw_login_json)}")
                    
                token = data_login.get("token")
                session_token = data_login.get("session_token")
                
                # El ID de usuario no viene en el Login, se usa el estático asignado por Simple
                user_id = "5445433" 
                
                if not token or not session_token:
                    raise ValueError(f"Faltan tokens en 'data'. Respuesta completa: {json.dumps(raw_login_json)}")
                    
                # --- PASO 2: AUTORIZACIÓN ---
                auth_url = f"{self.base_url}/auth/{user_id}/CC/{self.document}"
                headers_auth = {
                    "accept": "application/json",
                    "nit": self.nit,
                    "token": token,
                    "session_token": session_token
                }
                
                resp_auth = client.get(auth_url, headers=headers_auth)
                resp_auth.raise_for_status()
                
                auth_token = resp_auth.json().get("data", {}).get("auth_token")
                if not auth_token:
                    raise ValueError("La Autorización no devolvió el auth_token.")

                # --- PASO 3: VALIDACIÓN DE PLANILLA ---
                val_url = f"{self.base_url}/payroll/validate"
                headers_val = {
                    "accept": "application/json",
                    "nit": self.nit,
                    "token": token,
                    "session_token": session_token,
                    "auth_token": auth_token
                }
                
                # Construcción Multipart (Equivalente al -F de cURL)
                files = {
                    "payroll_file": (nombre_archivo, txt_bytes, "text/plain")
                }
                data = {
                    "execution_params": '{"is_UGPP":false,"is_novelties_planillaN":false,"file_type":"I"}'
                }
                
                resp_val = client.post(val_url, headers=headers_val, files=files, data=data)
                resp_val.raise_for_status()
                
                return resp_val.json()
                
        except httpx.HTTPStatusError as e:
            logger.error(f"[SIMPLE_GATEWAY] HTTP Error {e.response.status_code}: {e.response.text}")
            return {"error": f"HTTP {e.response.status_code}", "details": e.response.json() if e.response.text else str(e)}
        except Exception as ex:
            logger.error(f"[SIMPLE_GATEWAY] Excepción interna: {str(ex)}")
            return {"error": "Error Interno Gateway", "details": str(ex)}
