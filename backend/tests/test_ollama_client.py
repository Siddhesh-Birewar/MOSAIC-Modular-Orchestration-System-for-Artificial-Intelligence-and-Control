import asyncio

import httpx
import pytest

from app.models.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaResponseError,
    OllamaTimeoutError,
)


def test_list_models_and_chat_with_mocked_responses(monkeypatch):
    responses = [
        httpx.Response(200, json={"models": [{"name": "gpt-oss:20b"}]}),
        httpx.Response(200, json={"message": {"content": "Hello"}}),
    ]

    async def handle(self, method, url, **kwargs):
        return httpx.Response(200, json=responses.pop(0).json(), request=httpx.Request(method, url))

    monkeypatch.setattr(httpx.AsyncClient, "request", handle)
    client = OllamaClient("http://127.0.0.1:11434")
    async def check():
        assert (await client.list_models())[0]["name"] == "gpt-oss:20b"
        assert await client.chat("gpt-oss:20b", "Hi") == "Hello"

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
