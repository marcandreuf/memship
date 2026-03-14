"""Health endpoint tests."""


def test_health_returns_200(client):
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_health_returns_status_and_version(client):
    response = client.get("/api/v1/health")
    data = response.json()
    assert data["status"] == "healthy"
    assert "version" in data
    assert "environment" in data
