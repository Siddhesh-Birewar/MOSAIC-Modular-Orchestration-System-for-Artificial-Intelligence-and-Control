"""FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.api.health import router as health_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.models.ollama_client import OllamaClient, OllamaConnectionError, OllamaError, OllamaTimeoutError

logger = logging.getLogger(__name__)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=20_000)
    model: str | None = Field(default=None, min_length=1, max_length=200)


class ChatResponse(BaseModel):
    model: str
    response: str


def create_app(settings: Settings | None = None, ollama: OllamaClient | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ollama = ollama or OllamaClient(config.ollama_url, config.request_timeout)
        app.state.settings = config
        yield

    app = FastAPI(title="MOSAIC API", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)

    @app.post("/chat", response_model=ChatResponse)
    async def chat(body: ChatRequest, request: Request) -> ChatResponse:
        model = body.model or request.app.state.settings.primary_model
        try:
            answer = await request.app.state.ollama.chat(model, body.message)
        except OllamaTimeoutError as exc:
            raise HTTPException(status_code=504, detail=str(exc)) from exc
        except (OllamaConnectionError, OllamaError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        logger.info("Chat completed for configured model")
        return ChatResponse(model=model, response=answer)

    return app


app = create_app()
