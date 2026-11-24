import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.models.ollama_client import OllamaConnectionError


class FakeOllama:
    async def list_models(self):
        return [{"name": "gpt-oss:20b"}]

    async def chat(self, model, message):
        return f"Reply to: {message}"


class BrokenOllama:
    async def list_models(self):
        raise OllamaConnectionError("Could not connect to Ollama")

    async def chat(self, model, message):
        raise OllamaConnectionError("Could not connect to Ollama")


def test_configuration_loading(monkeypatch):
    monkeypatch.setenv("MOSAIC_OLLAMA_URL", "http://localhost:11434/")
    monkeypatch.setenv("MOSAIC_PRIMARY_MODEL", "qwen3:8b")
    monkeypatch.setenv("MOSAIC_REQUEST_TIMEOUT", "45")
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.primary_model == "qwen3:8b"
    assert settings.request_timeout == 45

def test_health_models_and_chat():
    with TestClient(create_app(Settings(), FakeOllama())) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/health/ollama").status_code == 200
        assert client.get("/models").json()["models"][0]["name"] == "gpt-oss:20b"
        response = client.post("/chat", json={"message": "hello"})
        assert response.json() == {"model": "gpt-oss:20b", "response": "Reply to: hello"}


def test_ollama_connection_failure_returns_503():
    with TestClient(create_app(Settings(), BrokenOllama())) as client:
        assert client.get("/health/ollama").status_code == 503
        assert client.post("/chat", json={"message": "hello"}).status_code == 503


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 20001}])
def test_invalid_chat_requests(payload):
    with TestClient(create_app(Settings(), FakeOllama())) as client:
        assert client.post("/chat", json=payload).status_code == 422
