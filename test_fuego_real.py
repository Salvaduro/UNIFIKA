import sys
import os
import datetime
import json
from unittest.mock import patch

# Asegurar que estamos en el contexto correcto (backend)
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nomina-cloud-backend")
os.chdir(backend_path)
sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
SECRET = os.environ.get("CRON_SECRET", "unifika_cron_secreto_2026")

def main():
    date_str = "2026-08-20"
    print(f"--- DISPARO DE FUEGO REAL: Cierre Automático ({date_str}) ---")
    
    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if tz:
                return dt.replace(tzinfo=tz)
            return dt

    with patch('main.datetime.datetime', MockDatetime):
        # NOTA: No pasamos dry_run, por lo tanto será False (Fuego Real)
        url = "/api/v1/cron/procesar-ciclo?target_aportante=79624350"
        
        response = client.post(
            url,
            headers={"X-Cron-Secret": SECRET}
        )
        
        print(f"Status Code: {response.status_code}")
        try:
            print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        except Exception:
            print(f"Response: {response.text}")

if __name__ == "__main__":
    main()
