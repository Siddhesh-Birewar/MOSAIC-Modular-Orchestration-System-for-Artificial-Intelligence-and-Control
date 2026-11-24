"""Small asynchronous client for Ollama's local HTTP API."""

import json
import time
from copy import deepcopy
from collections.abc import AsyncIterator
from dataclasses import dataclass
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


class OllamaModelNotFoundError(OllamaError):
    pass


class OllamaInferenceError(OllamaError):
    pass


@dataclass
class StreamEvent:
    content: str = ""
    metrics: dict[str, Any] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    assistant_message: dict[str, Any] | None = None
    done: bool = False


def _merge_tool_value(current: Any, incoming: Any) -> Any:
    """Merge streamed snapshots/fragments without duplicating repeated values."""
    if isinstance(current, dict) and isinstance(incoming, dict):
        merged = dict(current)
        for key, value in incoming.items():
            merged[key] = _merge_tool_value(merged[key], value) if key in merged else deepcopy(value)
        return merged
    if isinstance(current, str) and isinstance(incoming, str):
        if incoming.startswith(current):
            return incoming
        if current.startswith(incoming) or current == incoming:
            return current
        return current + incoming
    return deepcopy(incoming)


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
            if exc.response.status_code == 404:
                raise OllamaModelNotFoundError("Requested model is not available in Ollama") from exc
            if exc.response.status_code >= 500:
                raise OllamaInferenceError("Ollama could not complete the request") from exc
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

    async def running_models(self) -> list[dict[str, Any]]:
        payload = await self._request("GET", "/api/ps")
        models = payload.get("models")
        if not isinstance(models, list) or any(not isinstance(item, dict) for item in models):
            raise OllamaResponseError("Ollama running model list is malformed")
        return models

    async def unload_model(self, model: str) -> None:
        running = await self.running_models()
        if not any((item.get("name") or item.get("model")) == model for item in running):
            return
        await self._request("POST", "/api/generate", json={
            "model": model,
            "prompt": "",
            "stream": False,
            "keep_alive": 0,
        })

    async def chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        keep_alive: str = "5m",
        tools: list[dict[str, Any]] | None = None,
    ) -> tuple[str, dict[str, Any]]:
        body: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
        }
        if tools:
            body["tools"] = tools
        payload = await self._request("POST", "/api/chat", json=body)
        response = payload.get("message")
        content = response.get("content") if isinstance(response, dict) else None
        if not isinstance(content, str):
            raise OllamaResponseError("Ollama chat response is malformed")
        return content, payload

    async def stream_chat(
        self,
        model: str,
        messages: list[dict[str, Any]],
        keep_alive: str = "5m",
        tools: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[StreamEvent]:
        started = time.monotonic()
        accumulated_tool_calls: list[dict[str, Any]] = []
        accumulated_tool_call_keys: dict[tuple[str, str | int], int] = {}
        accumulated_content: list[str] = []
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                body: dict[str, Any] = {
                    "model": model,
                    "messages": messages,
                    "stream": True,
                    "keep_alive": keep_alive,
                }
                if tools:
                    body["tools"] = tools
                async with client.stream("POST", f"{self.base_url}/api/chat", json=body) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        try:
                            payload = json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise OllamaResponseError("Ollama returned a malformed stream") from exc
                        if not isinstance(payload, dict):
                            raise OllamaResponseError("Ollama stream event must be an object")
                        if payload.get("error"):
                            raise OllamaInferenceError("Ollama could not complete the request")
                        message = payload.get("message")
                        # Keep reasoning fields private; only content is exposed to the user.
                        content = message.get("content", "") if isinstance(message, dict) else ""
                        if content and not isinstance(content, str):
                            raise OllamaResponseError("Ollama returned malformed chat content")
                        if content:
                            accumulated_content.append(content)
                        done = payload.get("done") is True
                        tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
                        if tool_calls is not None and not isinstance(tool_calls, list):
                            raise OllamaResponseError("Ollama returned malformed tool calls")
                        if tool_calls:
                            for call in tool_calls:
                                if not isinstance(call, dict):
                                    raise OllamaResponseError("Ollama returned malformed tool calls")
                                function = call.get("function")
                                function_index = function.get("index") if isinstance(function, dict) else None
                                call_id = call.get("id")
                                key = (
                                    ("index", function_index) if isinstance(function_index, int)
                                    else ("id", call_id) if isinstance(call_id, str) and call_id
                                    else None
                                )
                                if key is not None and key in accumulated_tool_call_keys:
                                    position = accumulated_tool_call_keys[key]
                                    accumulated_tool_calls[position] = _merge_tool_value(
                                        accumulated_tool_calls[position], call
                                    )
                                else:
                                    if key is not None:
                                        accumulated_tool_call_keys[key] = len(accumulated_tool_calls)
                                    accumulated_tool_calls.append(deepcopy(call))
                        assistant_message = None
                        if done and accumulated_tool_calls:
                            final_message = message if isinstance(message, dict) else {"role": "assistant"}
                            assistant_message = {
                                key: value for key, value in final_message.items()
                                if key not in ("thinking", "reasoning")
                            }
                            assistant_message["content"] = "".join(accumulated_content)
                            assistant_message["tool_calls"] = deepcopy(accumulated_tool_calls)
                        yield StreamEvent(
                            content=content,
                            metrics=payload if done else None,
                            tool_calls=deepcopy(accumulated_tool_calls) if done and accumulated_tool_calls else None,
                            assistant_message=assistant_message,
                            done=done,
                        )
                        if done:
                            return
            raise OllamaResponseError("Ollama stream ended before completion")
        except httpx.TimeoutException as exc:
            raise OllamaTimeoutError("Ollama request timed out") from exc
        except httpx.ConnectError as exc:
            raise OllamaConnectionError("Could not connect to Ollama") from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                raise OllamaModelNotFoundError("Requested model is not available in Ollama") from exc
            if exc.response.status_code >= 500:
                raise OllamaInferenceError("Ollama could not complete the request") from exc
            raise OllamaResponseError(f"Ollama returned HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise OllamaConnectionError("Ollama stream was interrupted") from exc
