from fastapi.testclient import TestClient

from delibra.main import create_app
from verdictforge.config import Settings


def make_settings(tmp_path, *, api_key=None) -> Settings:
    return Settings(
        _env_file=None,
        database_path=tmp_path / "api.db",
        api_key=api_key,
        groq_api_key=None,
        nvidia_api_key=None,
        nvidia_openai_api_key=None,
    )


def test_health_and_frontend_are_served(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path))) as client:
        health = client.get("/api/v1/health")
        frontend = client.get("/")

    assert health.status_code == 200
    assert health.json()["status"] == "degraded"
    assert health.headers["x-content-type-options"] == "nosniff"
    assert "Delibra" in frontend.text


def test_unknown_debate_returns_404(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path))) as client:
        response = client.get("/api/v1/debates/4a716694-7e3c-4eba-9935-31860e10165b")

    assert response.status_code == 404


def test_api_key_protects_debate_creation(tmp_path) -> None:
    with TestClient(create_app(make_settings(tmp_path, api_key="secret-key"))) as client:
        response = client.post("/api/v1/debates", json={"question": "Test access"})

    assert response.status_code == 401
    assert response.headers["x-request-id"]
