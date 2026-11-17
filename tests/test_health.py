
from fastapi.testclient import TestClient

from api.main import app


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "spresso-rag-api",
    }


def test_root_endpoint():
    with TestClient(app) as client:
        response = client.get("/")

    assert response.status_code == 200
    assert response.json()["message"] == "S-Presso RAG API"
