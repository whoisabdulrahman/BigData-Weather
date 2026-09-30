from fastapi.testclient import TestClient
from apps.api.main import app

client = TestClient(app)


def test_health_check_returns_200_and_ok():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "environment" in data
    assert "version" in data
    assert "timestamp" in data


def test_readiness_check_returns_components():
    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] in ["ready", "degraded"]
    assert "components" in data
    assert "database" in data["components"]
    assert "cache" in data["components"]
    assert "streaming" in data["components"]
    assert "object_store" in data["components"]


def test_security_headers_present():
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "x-xss-protection" in response.headers
