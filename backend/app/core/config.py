"""Environment-based application configuration."""

from dataclasses import dataclass
import os


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
        return cls(
            ollama_url=os.getenv("MOSAIC_OLLAMA_URL", cls.ollama_url).rstrip("/"),
            primary_model=os.getenv("MOSAIC_PRIMARY_MODEL", cls.primary_model),
            request_timeout=timeout,
            log_level=os.getenv("MOSAIC_LOG_LEVEL", cls.log_level).upper(),
            allowed_models=allowed_models,
            context_limit=context_limit,
            keep_alive=os.getenv("MOSAIC_KEEP_ALIVE", "5m"),
            system_prompt=os.getenv("MOSAIC_SYSTEM_PROMPT", ""),
        )
