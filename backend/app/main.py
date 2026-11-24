"""FastAPI application entry point."""

from contextlib import asynccontextmanager
import asyncio
import sqlite3
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.personal_data import router as personal_data_router
from app.api.tools import router as tools_router
from app.core.config import Settings
from app.core.logging import configure_logging
from app.database import Database
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
        app.state.database = Database(config.database_path)
        app.state.conversations = ConversationStore(app.state.database)
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
        try:
            yield
        finally:
            app.state.database.close()

    app = FastAPI(title="MOSAIC API", version="0.4.0", lifespan=lifespan)
    @app.exception_handler(sqlite3.IntegrityError)
    async def integrity_error(_request: Request, _exc: sqlite3.IntegrityError) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": "Record conflicts with stored data"})

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Default validation responses echo submitted personal content.
        errors = [{"loc": error["loc"], "type": error["type"]} for error in exc.errors()]
        return JSONResponse(status_code=422, content={"detail": errors})

    app.include_router(health_router)
    app.include_router(intelligence_router)
    app.include_router(tools_router)
    app.include_router(personal_data_router)
    return app


app = create_app()
