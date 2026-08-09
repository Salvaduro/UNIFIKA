import sys
import os
import datetime
import json
from unittest.mock import patch

# Change current working directory to backend so .env can be loaded
backend_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nomina-cloud-backend")
os.chdir(backend_path)
sys.path.insert(0, backend_path)

from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

SECRET = os.environ.get("CRON_SECRET", "unifika_cron_secreto_2026")

def run_test(date_str, description):
    print(f"--- Prueba: {description} ({date_str}) ---")
    
    class MockDatetime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            dt = datetime.datetime.strptime(date_str, "%Y-%m-%d")
            if tz:
                return dt.replace(tzinfo=tz)
            return dt

    with patch('main.datetime.datetime', MockDatetime):
        response = client.post(
            "/api/v1/cron/procesar-ciclo?dry_run=true",
            headers={"X-Cron-Secret": SECRET}
        )
        print(f"Status Code: {response.status_code}")
        print(f"Response: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
        print("\n")

if __name__ == "__main__":
    run_test("2026-08-13", "13 de agosto de 2026 (Debería gatillar pre-liquidación)")
    run_test("2026-08-20", "20 de agosto de 2026 (Debería gatillar cierre)")
    run_test("2026-08-08", "8 de agosto de 2026 (Debería indicar sin acciones)")
