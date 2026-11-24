"""Health and Ollama discovery endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from app.models.ollama_client import OllamaError

router = APIRouter()


def service(request: Request):
    return request.app.state.ollama


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/health/ollama")
async def ollama_health(request: Request) -> dict[str, str]:
    try:
        await service(request).list_models()
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"status": "ok"}


@router.get("/models")
async def models(request: Request) -> dict[str, list[dict[str, Any]]]:
    try:
        installed = await service(request).list_models()
        running = await service(request).running_models()
        running_names = {item.get("name") or item.get("model") for item in running}
        for item in installed:
            item["loaded"] = (item.get("name") or item.get("model")) in running_names
        return {"models": installed}
    except OllamaError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
