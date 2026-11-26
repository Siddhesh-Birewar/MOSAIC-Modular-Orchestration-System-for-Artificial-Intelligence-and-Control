"""Environment-based application configuration."""

from dataclasses import dataclass
import os

from app.database import default_database_path


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    primary_model: str = "gpt-oss:20b"
    request_timeout: float = 120.0
    log_level: str = "INFO"
    allowed_models: tuple[str, ...] = ("gpt-oss:20b", "qwen3:8b")
    context_limit: int = 20
    keep_alive: str = "5m"
    system_prompt: str = ""
    api_token: str = ""
    whisper_executable: str = ""
    whisper_model: str = ""
    database_path: str = ":memory:"
    allowed_roots: tuple[str, ...] = ()
    allowed_applications: tuple[str, ...] = (
        "Visual Studio Code", "Finder", "Calculator", "Notes", "Safari", "Google Chrome"
    )
    audit_capacity: int = 500
    max_tool_calls: int = 3
    max_tool_seconds: float = 30.0
    max_tool_iterations: int = 3
    max_orchestration_seconds: float = 180.0

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = float(os.getenv("MOSAIC_REQUEST_TIMEOUT", "120"))
        if timeout <= 0:
            raise ValueError("MOSAIC_REQUEST_TIMEOUT must be positive")
        context_limit = int(os.getenv("MOSAIC_CONTEXT_LIMIT", "20"))
        if context_limit < 2:
            raise ValueError("MOSAIC_CONTEXT_LIMIT must be at least 2")
        allowed_models = tuple(
            model.strip()
            for model in os.getenv("MOSAIC_ALLOWED_MODELS", "gpt-oss:20b,qwen3:8b").split(",")
            if model.strip()
        )
        allowed_roots = tuple(
            root.strip() for root in os.getenv("MOSAIC_ALLOWED_ROOTS", "").split(os.pathsep) if root.strip()
        )
        allowed_applications = tuple(
            name.strip()
            for name in os.getenv(
                "MOSAIC_ALLOWED_APPLICATIONS",
                "Visual Studio Code,Finder,Calculator,Notes,Safari,Google Chrome",
            ).split(",")
            if name.strip()
        )
        return cls(
            ollama_url=os.getenv("MOSAIC_OLLAMA_URL", cls.ollama_url).rstrip("/"),
            primary_model=os.getenv("MOSAIC_PRIMARY_MODEL", cls.primary_model),
            request_timeout=timeout,
            log_level=os.getenv("MOSAIC_LOG_LEVEL", cls.log_level).upper(),
            allowed_models=allowed_models,
            context_limit=context_limit,
            keep_alive=os.getenv("MOSAIC_KEEP_ALIVE", "5m"),
            system_prompt=os.getenv("MOSAIC_SYSTEM_PROMPT", ""),
            whisper_executable=os.getenv("MOSAIC_WHISPER_EXECUTABLE", ""),
            whisper_model=os.getenv("MOSAIC_WHISPER_MODEL", ""),
            api_token=os.getenv("MOSAIC_API_TOKEN", ""),
            database_path=os.getenv("MOSAIC_DB_PATH", "").strip() or str(default_database_path()),
            allowed_roots=allowed_roots,
            allowed_applications=allowed_applications,
            audit_capacity=int(os.getenv("MOSAIC_AUDIT_CAPACITY", "500")),
            max_tool_calls=int(os.getenv("MOSAIC_MAX_TOOL_CALLS", "3")),
            max_tool_seconds=float(os.getenv("MOSAIC_MAX_TOOL_SECONDS", "30")),
            max_tool_iterations=int(os.getenv("MOSAIC_MAX_TOOL_ITERATIONS", "3")),
            max_orchestration_seconds=float(os.getenv("MOSAIC_MAX_ORCHESTRATION_SECONDS", "180")),
        )
