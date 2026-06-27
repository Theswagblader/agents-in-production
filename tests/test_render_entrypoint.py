from fastapi.testclient import TestClient

from main import app


def test_root_entrypoint_uses_clearance_app():
    assert app.title == "Clearance"

    with TestClient(app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
