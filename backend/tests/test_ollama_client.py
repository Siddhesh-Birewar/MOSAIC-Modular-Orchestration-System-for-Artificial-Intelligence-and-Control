import asyncio
import json

import httpx
import pytest

from app.models.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaInferenceError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
)


def test_list_models_and_chat_with_mocked_responses(monkeypatch):
    responses = [
        httpx.Response(200, json={"models": [{"name": "gpt-oss:20b"}]}),
        httpx.Response(200, json={"message": {"content": "Hello"}, "eval_count": 1}),
    ]

    async def handle(self, method, url, **kwargs):
        return httpx.Response(200, json=responses.pop(0).json(), request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", handle)
    client = OllamaClient("http://127.0.0.1:11434")
    async def check():
        assert (await client.list_models())[0]["name"] == "gpt-oss:20b"
        answer, metrics = await client.chat("gpt-oss:20b", [{"role": "user", "content": "Hi"}])
        assert answer == "Hello" and metrics["eval_count"] == 1

    asyncio.run(check())


def test_connection_failure(monkeypatch):
    async def fail(self, method, url, **kwargs):
        raise httpx.ConnectError("refused")

    monkeypatch.setattr(httpx.AsyncClient, "request", fail)
    async def check():
        with pytest.raises(OllamaConnectionError):
            await OllamaClient("http://127.0.0.1:11434").list_models()

    asyncio.run(check())


def test_timeout(monkeypatch):
    async def timeout(self, method, url, **kwargs):
        raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr(httpx.AsyncClient, "request", timeout)

    async def check():
        with pytest.raises(OllamaTimeoutError):
            await OllamaClient("http://127.0.0.1:11434").list_models()

    asyncio.run(check())


def test_malformed_response(monkeypatch):
    async def malformed(self, method, url, **kwargs):
        return httpx.Response(200, json={"unexpected": True}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", malformed)
    async def check():
        with pytest.raises(OllamaResponseError):
            await OllamaClient("http://127.0.0.1:11434").list_models()

    asyncio.run(check())


def test_model_status_unload_requests(monkeypatch):
    requests = []

    async def handle(self, method, url, **kwargs):
        requests.append((method, url, kwargs))
        payload = {"models": [{"name": "qwen3:8b"}]} if url.endswith("/api/ps") else {}
        return httpx.Response(200, json=payload, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", handle)

    async def check():
        client = OllamaClient("http://localhost:11434")
        assert (await client.running_models())[0]["name"] == "qwen3:8b"
        await client.unload_model("qwen3:8b")
        assert requests[-1][1].endswith("/api/generate")
        assert requests[-1][2]["json"]["keep_alive"] == 0
        count = len(requests)
        await client.unload_model("gpt-oss:20b")
        assert len(requests) == count + 1  # status check only; absent model is never loaded to unload

    asyncio.run(check())


def test_stream_chunks_separate_reasoning_and_close_on_cancel(monkeypatch):
    state = {"closed": False}

    class Response:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "part", "thinking": "private reasoning"}, "done": False})

    class StreamContext:
        async def __aenter__(self):
            return Response()

        async def __aexit__(self, *args):
            state["closed"] = True

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, *args, **kwargs):
            return StreamContext()

    monkeypatch.setattr("app.models.ollama_client.httpx.AsyncClient", FakeAsyncClient)

    async def check():
        stream = OllamaClient("http://127.0.0.1:11434").stream_chat(
            "gpt-oss:20b", [{"role": "user", "content": "hello"}]
        )
        chunk = await anext(stream)
        assert chunk.content == "part"
        assert "private reasoning" not in chunk.content
        await stream.aclose()
        assert state["closed"] is True

    asyncio.run(check())


def test_incomplete_stream_is_reported(monkeypatch):
    class Response:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield json.dumps({"message": {"content": "partial"}, "done": False})

    class StreamContext:
        async def __aenter__(self):
            return Response()

        async def __aexit__(self, *args):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, *args, **kwargs):
            return StreamContext()

    monkeypatch.setattr("app.models.ollama_client.httpx.AsyncClient", FakeAsyncClient)

    async def check():
        stream = OllamaClient("http://127.0.0.1:11434").stream_chat(
            "gpt-oss:20b", [{"role": "user", "content": "hello"}]
        )
        assert (await anext(stream)).content == "partial"
        with pytest.raises(OllamaResponseError, match="ended before completion"):
            await anext(stream)

    asyncio.run(check())


def test_stream_parses_only_structured_tool_calls_and_strips_reasoning(monkeypatch):
    captured = {}
    event = {
        "message": {
            "role": "assistant",
            "content": "",
            "thinking": "internal reasoning must not be returned",
            "tool_calls": [{"function": {"name": "system_cpu_usage", "arguments": {}}}],
        },
        "done": True,
        "eval_count": 1,
    }

    class Response:
        def raise_for_status(self):
            return None

        async def aiter_lines(self):
            yield json.dumps(event)

    class StreamContext:
        async def __aenter__(self):
            return Response()

        async def __aexit__(self, *args):
            return None

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def stream(self, method, url, **kwargs):
            captured.update(kwargs["json"])
            return StreamContext()

    monkeypatch.setattr("app.models.ollama_client.httpx.AsyncClient", FakeAsyncClient)

    async def check():
        stream = OllamaClient("http://127.0.0.1:11434").stream_chat(
            "gpt-oss:20b", [{"role": "user", "content": "cpu"}], tools=[{"type": "function"}]
        )
        result = await anext(stream)
        assert result.done and result.tool_calls[0]["function"]["name"] == "system_cpu_usage"
        assert result.assistant_message is not None
        assert "thinking" not in result.assistant_message
        assert captured["tools"] == [{"type": "function"}]

    asyncio.run(check())


@pytest.mark.parametrize(
    ("status", "exception"),
    [(404, OllamaModelNotFoundError), (500, OllamaInferenceError)],
)
def test_http_failures_are_classified(monkeypatch, status, exception):
    async def failed(self, method, url, **kwargs):
        return httpx.Response(status, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", failed)

    async def check():
        with pytest.raises(exception):
            await OllamaClient("http://127.0.0.1:11434").list_models()

    asyncio.run(check())
