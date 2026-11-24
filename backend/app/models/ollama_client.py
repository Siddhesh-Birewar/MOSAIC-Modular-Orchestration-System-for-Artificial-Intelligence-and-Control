"""Small asynchronous client for Ollama's local HTTP API."""

from typing import Any

import httpx


class OllamaError(RuntimeError):
    """Base error for local Ollama API failures."""


class OllamaConnectionError(OllamaError):
    pass


class OllamaTimeoutError(OllamaError):
    pass


class OllamaResponseError(OllamaError):
    pass


class OllamaClient:
    def __init__(self, base_url: str, timeout: float = 120.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.request(method, f"{self.base_url}{path}", **kwargs)
                response.raise_for_status()
                payload = response.json()
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError("Ollama request timed out") from exc
        except httpx.ConnectError as exc:
            raise OllamaConnectionError("Could not connect to Ollama") from exc
        except httpx.HTTPStatusError as exc:
            raise OllamaResponseError(f"Ollama returned HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise OllamaResponseError("Ollama returned an invalid response") from exc
        if not isinstance(payload, dict):
            raise OllamaResponseError("Ollama response must be a JSON object")
        return payload

    async def list_models(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/tags")
        models = payload.get("models")
        if not isinstance(models, list) or any(not isinstance(item, dict) for item in models):
            raise OllamaResponseError("Ollama model list is malformed")
        return models

    async def chat(self, model: str, message: str) -> str:
        payload = await self._request("POST", "/api/chat", json={
            "model": model,
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        })
        response = payload.get("message")
        content = response.get("content") if isinstance(response, dict) else None
        if not isinstance(content, str):
            raise OllamaResponseError("Ollama chat response is malformed")
        return content
