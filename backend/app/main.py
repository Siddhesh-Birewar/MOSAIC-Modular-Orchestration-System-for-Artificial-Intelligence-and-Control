"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.conversations import ConversationStore
from app.models.ollama_client import OllamaClient


def create_app(settings: Settings | None = None, ollama: OllamaClient | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ollama = ollama or OllamaClient(config.ollama_url, config.request_timeout)
        app.state.settings = config
        app.state.conversations = ConversationStore()
        app.state.inference_lock = asyncio.Lock()
        yield

    app = FastAPI(title="MOSAIC API", version="0.2.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(intelligence_router)
    return app


app = create_app()
