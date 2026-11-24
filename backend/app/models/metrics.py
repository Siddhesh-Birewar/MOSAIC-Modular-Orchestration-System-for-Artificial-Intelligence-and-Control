"""Inference metrics returned by Ollama and measured by the API."""

from dataclasses import dataclass
from typing import Any


def nanoseconds_to_seconds(value: Any) -> float | None:
    if isinstance(value, (int, float)) and value >= 0:
        return round(value / 1_000_000_000, 6)
    return None


@dataclass
class InferenceMetrics:
    model_load_seconds: float | None = None
    time_to_first_chunk_seconds: float | None = None
    total_duration_seconds: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    generation_tokens_per_second: float | None = None

    @classmethod
    def from_ollama(cls, payload: dict[str, Any]) -> "InferenceMetrics":
        load_seconds = nanoseconds_to_seconds(payload.get("load_duration"))
        eval_seconds = nanoseconds_to_seconds(payload.get("eval_duration"))
        output_tokens = payload.get("eval_count")
        rate = None
        if isinstance(output_tokens, int) and eval_seconds and eval_seconds > 0:
            rate = round(output_tokens / eval_seconds, 3)
        return cls(
            model_load_seconds=load_seconds,
            input_tokens=payload.get("prompt_eval_count") if isinstance(payload.get("prompt_eval_count"), int) else None,
            output_tokens=output_tokens if isinstance(output_tokens, int) else None,
            generation_tokens_per_second=rate,
        )
