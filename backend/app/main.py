"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import asyncio
from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.tools import router as tools_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.conversations import ConversationStore
from app.models.ollama_client import OllamaClient
from app.security.approvals import ApprovalManager
from app.security.audit import AuditLog
from app.security.permissions import PermissionManager
from app.tools.builtin.files import FileAccess
from app.tools.builtin.registry import build_registry
from app.tools.builtin.applications import installed_application_path
from app.tools.executor import ToolExecutor


def create_app(settings: Settings | None = None, ollama: OllamaClient | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    if config.api_token and len(config.api_token) < 32:
        raise ValueError("MOSAIC_API_TOKEN must contain at least 32 characters")
    configure_logging(config.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.ollama = ollama or OllamaClient(config.ollama_url, config.request_timeout)
        app.state.settings = config
        app.state.conversations = ConversationStore()
        app.state.inference_lock = asyncio.Lock()
        app.state.file_access = FileAccess(config.allowed_roots)
        app.state.permission_manager = PermissionManager(
            app.state.file_access, config.allowed_applications,
            application_available=lambda name: installed_application_path(name) is not None,
        )
        app.state.approvals = ApprovalManager()
        app.state.audit = AuditLog(config.audit_capacity)
        app.state.tool_registry = build_registry()
        app.state.tool_services = {
            "file_access": app.state.file_access,
            "ollama": app.state.ollama,
            "allowed_applications": config.allowed_applications,
        }
        app.state.tool_executor = ToolExecutor(
            app.state.tool_registry,
            app.state.permission_manager,
            app.state.approvals,
            app.state.audit,
        )
        yield

    app = FastAPI(title="MOSAIC API", version="0.2.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(intelligence_router)
    app.include_router(tools_router)
    return app


app = create_app()
