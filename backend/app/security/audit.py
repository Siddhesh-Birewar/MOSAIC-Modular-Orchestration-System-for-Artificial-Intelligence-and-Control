"""Bounded, in-memory structured audit history with content-free fields."""

from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any


class AuditLog:
    def __init__(self, capacity: int = 500) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=max(1, capacity))
        self._lock = Lock()

    def record(
        self,
        *,
        tool_id: str,
        conversation_id: str | None,
        decision: str,
        approval_outcome: str | None = None,
        execution_result: str,
        duration_seconds: float | None = None,
        error_category: str | None = None,
    ) -> None:
        event = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "tool_id": tool_id,
            "conversation_id": conversation_id,
            "decision": decision,
            "approval_outcome": approval_outcome,
            "execution_result": execution_result,
            "duration_seconds": duration_seconds,
            "error_category": error_category,
        }
        with self._lock:
            self._events.append(event)

    def recent(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)[-min(max(1, limit), 200):]
