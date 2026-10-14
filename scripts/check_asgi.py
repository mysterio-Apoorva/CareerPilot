from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from fastapi.testclient import TestClient
from server import app

with TestClient(app) as client:
    assert client.get("/api/health").json()["status"] == "ok"
    assert client.get("/").status_code == 200
    assert client.get("/_stcore/health").status_code == 200
print("PASS: ASGI lifecycle, app HTML, and health endpoints.")
