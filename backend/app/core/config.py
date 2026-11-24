"""Environment-based application configuration."""

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    ollama_url: str = "http://127.0.0.1:11434"
    primary_model: str = "gpt-oss:20b"
    request_timeout: float = 120.0
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Settings":
        timeout = float(os.getenv("MOSAIC_REQUEST_TIMEOUT", "120"))
        if timeout <= 0:
            raise ValueError("MOSAIC_REQUEST_TIMEOUT must be positive")
        return cls(
            ollama_url=os.getenv("MOSAIC_OLLAMA_URL", cls.ollama_url).rstrip("/"),
            primary_model=os.getenv("MOSAIC_PRIMARY_MODEL", cls.primary_model),
            request_timeout=timeout,
            log_level=os.getenv("MOSAIC_LOG_LEVEL", cls.log_level).upper(),
        )
