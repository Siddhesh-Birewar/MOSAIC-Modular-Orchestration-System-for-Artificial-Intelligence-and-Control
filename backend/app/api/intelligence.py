"""Conversation, chat, streaming, and model-management routes."""

import asyncio
import json
import logging
import time
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.conversations import Conversation, ConversationNotFoundError
from app.core.prompts import build_system_prompt
from app.models.metrics import InferenceMetrics
from app.models.ollama_client import (
    OllamaClient,
    OllamaConnectionError,
    OllamaError,
    OllamaInferenceError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
)
from app.schemas import ChatRequest, ChatResponse, ConversationCreate, ConversationModelRequest

router = APIRouter()
logger = logging.getLogger(__name__)


def _conversation_data(conversation: Conversation) -> dict[str, Any]:
    return {
        "id": conversation.id,
        "model": conversation.model,
        "created_at": conversation.created_at.isoformat(),
        "messages": conversation.messages,
    }


def _model_name(item: dict[str, Any]) -> str | None:
    name = item.get("name") or item.get("model")
    return name if isinstance(name, str) else None


async def _validate_model(request: Request, model: str) -> None:
    settings = request.app.state.settings
    if model not in settings.allowed_models:
        raise HTTPException(status_code=422, detail="Model is not allowed by MOSAIC configuration")
    try:
        installed = await request.app.state.ollama.list_models()
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail="Ollama model discovery is unavailable") from exc
    if model not in {_model_name(item) for item in installed}:
        raise HTTPException(status_code=422, detail="Selected model is not installed")


def _translate_error(exc: OllamaError) -> HTTPException:
    if isinstance(exc, OllamaTimeoutError):
        return HTTPException(status_code=504, detail="Ollama request timed out")
    if isinstance(exc, OllamaModelNotFoundError):
        return HTTPException(status_code=422, detail="Selected model is not installed")
    if isinstance(exc, OllamaConnectionError):
        return HTTPException(status_code=503, detail="Ollama is unavailable")
    if isinstance(exc, OllamaInferenceError):
        return HTTPException(status_code=502, detail="Ollama could not complete inference")
    return HTTPException(status_code=502, detail="Ollama returned an invalid response")


async def _prepare_model(ollama: OllamaClient, model: str, managed_models: tuple[str, ...]) -> None:
    """Unload another MOSAIC-managed model before inference to limit memory use."""
    for running in await ollama.running_models():
        loaded_name = _model_name(running)
        if loaded_name in managed_models and loaded_name != model:
            await ollama.unload_model(loaded_name)


def _messages(
    request: Request, conversation: Conversation, message: str, model: str | None = None
) -> list[dict[str, str]]:
    context = request.app.state.conversations.context(
        conversation, message, request.app.state.settings.context_limit
    )
    system = build_system_prompt(model or conversation.model, request.app.state.settings.system_prompt)
    return [{"role": "system", "content": system}, *context]


@router.post("/conversations", status_code=201)
async def create_conversation(body: ConversationCreate, request: Request) -> dict[str, Any]:
    model = body.model or request.app.state.settings.primary_model
    await _validate_model(request, model)
    return _conversation_data(request.app.state.conversations.create(model))


@router.get("/conversations/{conversation_id}")
async def get_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
    try:
        return _conversation_data(request.app.state.conversations.get(conversation_id))
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc


@router.post("/conversations/{conversation_id}/reset")
async def reset_conversation(conversation_id: str, request: Request) -> dict[str, Any]:
    try:
        return _conversation_data(request.app.state.conversations.reset(conversation_id))
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc


@router.patch("/conversations/{conversation_id}")
async def set_conversation_model(
    conversation_id: str, body: ConversationModelRequest, request: Request
) -> dict[str, Any]:
    await _validate_model(request, body.model)
    try:
        conversation = request.app.state.conversations.get(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    conversation.model = body.model
    return _conversation_data(conversation)


async def _resolve_chat(body: ChatRequest, request: Request) -> Conversation:
    store = request.app.state.conversations
    try:
        conversation = store.get(body.conversation_id) if body.conversation_id else None
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    model = body.model or (conversation.model if conversation else request.app.state.settings.primary_model)
    await _validate_model(request, model)
    if conversation is None:
        conversation = store.create(model)
    else:
        conversation.model = model
    return conversation


@router.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest, request: Request) -> ChatResponse:
    conversation = await _resolve_chat(body, request)
    ollama: OllamaClient = request.app.state.ollama
    started = time.monotonic()
    try:
        async with request.app.state.inference_lock:
            model = conversation.model
            messages = _messages(request, conversation, body.message)
            await _prepare_model(ollama, model, request.app.state.settings.allowed_models)
            answer, raw_metrics = await ollama.chat(
                model, messages, request.app.state.settings.keep_alive
            )
    except OllamaError as exc:
        raise _translate_error(exc) from exc
    metrics = InferenceMetrics.from_ollama(raw_metrics)
    metrics.total_duration_seconds = round(time.monotonic() - started, 6)
    request.app.state.conversations.append_turn(conversation, body.message, answer)
    logger.info("Chat completed")
    return ChatResponse(
        conversation_id=conversation.id,
        model=model,
        response=answer,
        metrics=asdict(metrics),
    )


def _sse(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
async def stream_chat(body: ChatRequest, request: Request) -> StreamingResponse:
    conversation = await _resolve_chat(body, request)
    ollama: OllamaClient = request.app.state.ollama

    async def events():
        started = time.monotonic()
        first_chunk_at: float | None = None
        answer: list[str] = []
        stream = None
        model = conversation.model
        yield _sse("start", {"conversation_id": conversation.id, "model": model})
        try:
            async with request.app.state.inference_lock:
                messages = _messages(request, conversation, body.message, model)
                await _prepare_model(ollama, model, request.app.state.settings.allowed_models)
                stream = ollama.stream_chat(
                    model, messages, request.app.state.settings.keep_alive
                )
                async for chunk in stream:
                    if chunk.content:
                        if first_chunk_at is None:
                            first_chunk_at = time.monotonic()
                        answer.append(chunk.content)
                        yield _sse("token", {"text": chunk.content})
                    if chunk.done:
                        metrics = InferenceMetrics.from_ollama(chunk.metrics or {})
                        metrics.time_to_first_chunk_seconds = (
                            round(first_chunk_at - started, 6) if first_chunk_at is not None else None
                        )
                        metrics.total_duration_seconds = round(time.monotonic() - started, 6)
                        request.app.state.conversations.append_turn(conversation, body.message, "".join(answer))
                        yield _sse("done", {
                            "conversation_id": conversation.id,
                            "model": model,
                            "metrics": asdict(metrics),
                        })
                        logger.info("Streaming chat completed")
                        return
            raise OllamaError("Ollama stream ended before completion")
        except asyncio.CancelledError:
            logger.info("Streaming chat cancelled")
            raise
        except OllamaError as exc:
            yield _sse("error", {"detail": _translate_error(exc).detail})
        finally:
            if stream is not None:
                await stream.aclose()
            # Closing the stream exits the HTTP client's context and releases the model lock.
            answer.clear()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get("/models/running")
async def running_models(request: Request) -> dict[str, Any]:
    try:
        return {"models": await request.app.state.ollama.running_models()}
    except OllamaError as exc:
        raise _translate_error(exc) from exc


@router.get("/models/{model_name}/availability")
async def model_availability(model_name: str, request: Request) -> dict[str, Any]:
    try:
        installed = await request.app.state.ollama.list_models()
        running = await request.app.state.ollama.running_models()
    except OllamaError as exc:
        raise _translate_error(exc) from exc
    present = model_name in {_model_name(item) for item in installed}
    return {"model": model_name, "installed": present, "allowed": model_name in request.app.state.settings.allowed_models,
            "loaded": model_name in {_model_name(item) for item in running}}


@router.post("/models/{model_name}/unload")
async def unload_model(model_name: str, request: Request) -> dict[str, str]:
    if model_name not in request.app.state.settings.allowed_models:
        raise HTTPException(status_code=422, detail="Model is not allowed by MOSAIC configuration")
    await _validate_model(request, model_name)
    try:
        async with request.app.state.inference_lock:
            await request.app.state.ollama.unload_model(model_name)
    except OllamaError as exc:
        raise _translate_error(exc) from exc
    return {"model": model_name, "status": "unloaded"}
