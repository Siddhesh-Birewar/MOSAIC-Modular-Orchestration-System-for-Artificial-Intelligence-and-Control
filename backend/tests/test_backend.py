import pytest
import asyncio
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.api.intelligence import stream_chat
from app.core.config import Settings
from app.main import create_app
from app.models.ollama_client import OllamaConnectionError, StreamEvent
from app.schemas import ChatRequest


class FakeOllama:
    def __init__(self):
        self.calls = []
        self.loaded = []
        self.unloaded = []

    async def list_models(self):
        return [{"name": name} for name in ("gpt-oss:20b", "qwen3:8b")]

    async def running_models(self):
        return list(self.loaded)

    async def unload_model(self, model):
        self.unloaded.append(model)
        self.loaded = [item for item in self.loaded if item.get("name") != model]

    async def chat(self, model, messages, keep_alive="5m"):
        self.calls.append((model, messages, keep_alive))
        return f"Reply to: {messages[-1]['content']}", {
            "load_duration": 1_000_000_000,
            "prompt_eval_count": len(messages),
            "eval_count": 3,
            "eval_duration": 500_000_000,
        }

    async def stream_chat(self, model, messages, keep_alive="5m"):
        self.calls.append((model, messages, keep_alive))
        yield StreamEvent(content="A ")
        yield StreamEvent(content="reply")
        yield StreamEvent(metrics={"eval_count": 2, "eval_duration": 1_000_000_000}, done=True)


class BrokenOllama:
    async def list_models(self):
        return [{"name": "gpt-oss:20b"}]

    async def running_models(self):
        return []

    async def unload_model(self, model):
        return None

    async def chat(self, model, messages, keep_alive="5m"):
        raise OllamaConnectionError("private internal connection detail")

    async def stream_chat(self, model, messages, keep_alive="5m"):
        raise OllamaConnectionError("private internal connection detail")
        yield


def test_configuration_loading(monkeypatch):
    monkeypatch.setenv("MOSAIC_OLLAMA_URL", "http://localhost:11434/")
    monkeypatch.setenv("MOSAIC_PRIMARY_MODEL", "qwen3:8b")
    monkeypatch.setenv("MOSAIC_REQUEST_TIMEOUT", "45")
    monkeypatch.setenv("MOSAIC_CONTEXT_LIMIT", "8")
    settings = Settings.from_env()
    assert settings.ollama_url == "http://localhost:11434"
    assert settings.primary_model == "qwen3:8b"
    assert settings.request_timeout == 45
    assert settings.context_limit == 8


def test_health_models_and_chat():
    fake = FakeOllama()
    with TestClient(create_app(Settings(), fake)) as client:
        assert client.get("/health").json() == {"status": "ok"}
        assert client.get("/health/ollama").status_code == 200
        model = client.get("/models").json()["models"][0]
        assert model["name"] == "gpt-oss:20b" and model["loaded"] is False
        response = client.post("/chat", json={"message": "hello"})
        data = response.json()
        assert data["model"] == "gpt-oss:20b"
        assert data["response"] == "Reply to: hello"
        assert data["conversation_id"]
        assert data["metrics"]["input_tokens"] >= 1


def test_ollama_connection_failure_returns_sanitized_503():
    with TestClient(create_app(Settings(), BrokenOllama())) as client:
        assert client.get("/health/ollama").status_code == 200
        response = client.post("/chat", json={"message": "hello"})
        assert response.status_code == 503
        assert response.json()["detail"] == "Ollama is unavailable"


@pytest.mark.parametrize("payload", [{}, {"message": ""}, {"message": "x" * 20001}])
def test_invalid_chat_requests(payload):
    with TestClient(create_app(Settings(), FakeOllama())) as client:
        assert client.post("/chat", json=payload).status_code == 422


def test_prompt_multi_turn_context_trimming_and_conversation_isolation():
    fake = FakeOllama()
    with TestClient(create_app(Settings(context_limit=3), fake)) as client:
        first = client.post("/conversations", json={}).json()
        second = client.post("/conversations", json={}).json()
        assert first["id"] != second["id"]
        for message in ("one", "two", "three"):
            client.post("/chat", json={"conversation_id": first["id"], "message": message})
        client.post("/chat", json={"conversation_id": second["id"], "message": "private"})
        _, context, _ = fake.calls[-2]
        assert context[0]["role"] == "system"
        assert "You are MOSAIC" in context[0]["content"]
        assert "underlying model for this response is gpt-oss:20b" in context[0]["content"]
        assert [message["content"] for message in context[1:]] == ["two", "Reply to: two", "three"]
        assert "private" not in str(context)


def test_model_selection_invalid_ids_and_reset():
    with TestClient(create_app(Settings(), FakeOllama())) as client:
        conversation = client.post("/conversations", json={"model": "qwen3:8b"}).json()
        assert conversation["model"] == "qwen3:8b"
        invalid = client.patch(
            f"/conversations/{conversation['id']}", json={"model": "nomic-embed-text:latest"}
        )
        assert invalid.status_code == 422
        assert client.post("/chat", json={"conversation_id": "missing", "message": "hi"}).status_code == 404
        client.post("/chat", json={"conversation_id": conversation["id"], "message": "hello"})
        cleared = client.post(f"/conversations/{conversation['id']}/reset").json()
        assert cleared["messages"] == []


def test_streaming_response_and_context_cleanup():
    fake = FakeOllama()
    with TestClient(create_app(Settings(), fake)) as client:
        response = client.post("/chat/stream", json={"message": "stream me"})
        assert response.status_code == 200
        assert "event: start" in response.text
        assert "event: token" in response.text and '"text": "A "' in response.text
        assert "event: done" in response.text
        assert "reasoning" not in response.text
        cid = response.text.split('"conversation_id": "')[1].split('"')[0]
        assert len(client.get(f"/conversations/{cid}").json()["messages"]) == 2


def test_stream_failure_emits_sanitized_error_event():
    with TestClient(create_app(Settings(), BrokenOllama())) as client:
        response = client.post("/chat/stream", json={"message": "hello"})
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "private internal connection detail" not in response.text
        assert "Ollama is unavailable" in response.text


def test_stream_cancellation_releases_response_and_model_lock():
    class HangingStream(FakeOllama):
        def __init__(self):
            super().__init__()
            self.closed = False

        async def stream_chat(self, model, messages, keep_alive="5m"):
            try:
                yield StreamEvent(content="first")
                await asyncio.Event().wait()
            finally:
                self.closed = True

    async def check():
        fake = HangingStream()
        app = create_app(Settings(), fake)
        async with app.router.lifespan_context(app):
            request = Request({"type": "http", "app": app, "method": "POST", "path": "/chat/stream", "headers": []})
            response = await stream_chat(ChatRequest(message="cancel me"), request)
            iterator = response.body_iterator
            assert "event: start" in await anext(iterator)
            assert "event: token" in await anext(iterator)
            await iterator.aclose()
            assert fake.closed
            assert not app.state.inference_lock.locked()

    asyncio.run(check())


def test_model_availability_and_unload_endpoint():
    fake = FakeOllama()
    fake.loaded = [{"name": "gpt-oss:20b"}]
    with TestClient(create_app(Settings(), fake)) as client:
        status = client.get("/models/gpt-oss:20b/availability").json()
        assert status == {"model": "gpt-oss:20b", "installed": True, "allowed": True, "loaded": True}
        response = client.post("/models/gpt-oss:20b/unload")
        assert response.status_code == 200
        assert response.json()["status"] == "unloaded"


def test_switching_models_unloads_only_other_mosaic_model():
    fake = FakeOllama()
    fake.loaded = [{"name": "gpt-oss:20b"}, {"name": "nomic-embed-text:latest"}]
    with TestClient(create_app(Settings(), fake)) as client:
        conversation = client.post("/conversations", json={"model": "qwen3:8b"}).json()
        response = client.post(
            "/chat", json={"conversation_id": conversation["id"], "message": "switch"}
        )
        assert response.status_code == 200
        assert fake.unloaded == ["gpt-oss:20b"]
        assert fake.loaded == [{"name": "nomic-embed-text:latest"}]
