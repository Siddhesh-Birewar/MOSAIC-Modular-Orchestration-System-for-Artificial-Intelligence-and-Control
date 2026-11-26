"""Content-free speech failures; never construct messages from provider exceptions."""

from typing import Any

from app.voice.audio import VoiceError

CATEGORIES = {
    "memory_limit": "Voice memory admission or allocation failed",
    "worker_exit": "Neural worker exited",
    "timeout": "Voice operation timed out",
    "invalid_ipc": "Neural worker returned invalid protocol data",
    "synthesis_failure": "Neural synthesis failed",
    "audio_limit": "Generated audio exceeds the validated limit",
    "cancelled": "Voice operation was cancelled",
    "queue_full": "Neural synthesis queue is full",
    "unavailable": "Offline voice assets or interpreter are unavailable",
    "restart_limit": "Neural worker restart budget is exhausted",
}


class VoiceDiagnosticError(VoiceError):
    def __init__(self, category: str, stage: str, **measurements: Any) -> None:
        self.category = category if category in CATEGORIES else "synthesis_failure"
        # Only callers in this module's trusted integration supply numeric measurements.
        self.diagnostic = {"category": self.category, "stage": stage,
                           **{key: value for key, value in measurements.items()
                              if key in {"exit_code", "available_bytes", "required_bytes"}
                              and (type(value) is int or value is None)}}
        super().__init__(CATEGORIES[self.category])
