"""Interactive terminal client for the MOSAIC FastAPI backend."""

import argparse
import json
import os
import sys
from collections.abc import Iterable
from typing import Any, Callable

import httpx

if __package__ in {None, ""}:
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def parse_sse(lines: Iterable[str]):
    event = "message"
    data: list[str] = []
    for line in lines:
        if not line:
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
        elif line.startswith("event:"):
            event = line[6:].strip()
        elif line.startswith("data:"):
            data.append(line[5:].lstrip())
    if data:
        yield event, "\n".join(data)


class MosaicCLI:
    def __init__(
        self,
        backend_url: str,
        *,
        token: str = "",
        client: Any | None = None,
        input_fn: Callable[[str], str] = input,
        output_fn: Callable[[str], None] = print,
        write_fn: Callable[[str], None] | None = None,
    ) -> None:
        self.backend_url = backend_url.rstrip("/")
        self.token = token
        self.client = client or httpx.Client(timeout=300)
        self.input = input_fn
        self.output = output_fn
        self.write = write_fn or self._write_stdout
        self.conversation_id: str | None = None
        self.model: str | None = None
        self.show_metrics = False
        self.voice_session = None

    def _auth_headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    @staticmethod
    def _write_stdout(text: str) -> None:
        sys.stdout.write(text)
        sys.stdout.flush()

    def _new_conversation(self) -> None:
        body = {"model": self.model} if self.model else {}
        response = self.client.post(
            f"{self.backend_url}/conversations", json=body, headers=self._auth_headers()
        )
        response.raise_for_status()
        conversation = response.json()
        self.conversation_id = conversation["id"]
        self.model = conversation["model"]
        self.output(f"Started conversation {self.conversation_id} ({self.model}).")

    def help(self) -> None:
        self.output("Commands: /help /new /clear /models /model MODEL /status /metrics /exit /voice [on|off] /mic [INDEX] /voices /voice-status")

    def command(self, text: str) -> bool:
        parts = text.strip().split(maxsplit=1)
        name = parts[0].lower()
        argument = parts[1] if len(parts) > 1 else ""
        if name == "/help":
            self.help()
        elif name == "/exit":
            return False
        elif name == "/new":
            self._new_conversation()
        elif name == "/clear":
            response = self.client.post(
                f"{self.backend_url}/conversations/{self.conversation_id}/reset",
                headers=self._auth_headers(),
            )
            response.raise_for_status()
            self.output("Conversation cleared.")
        elif name == "/models":
            response = self.client.get(f"{self.backend_url}/models")
            response.raise_for_status()
            for model in response.json().get("models", []):
                self.output(f"{model.get('name', 'unknown')}" + (" (loaded)" if model.get("loaded") else ""))
        elif name == "/model":
            if not argument:
                self.output("Usage: /model MODEL")
            else:
                response = self.client.patch(
                    f"{self.backend_url}/conversations/{self.conversation_id}",
                    json={"model": argument}, headers=self._auth_headers(),
                )
                response.raise_for_status()
                self.model = response.json()["model"]
                self.output(f"Selected {self.model}.")
        elif name == "/status":
            backend = self.client.get(f"{self.backend_url}/health")
            ollama = self.client.get(f"{self.backend_url}/health/ollama")
            self.output(f"Backend: {backend.status_code}; Ollama: {ollama.status_code}.")
        elif name == "/metrics":
            self.show_metrics = not self.show_metrics
            self.output(f"Metrics {'on' if self.show_metrics else 'off'}.")
        elif name in {"/voice", "/mic", "/voices", "/voice-status"}:
            self._voice_command(name, argument)
        elif name.startswith("/"):
            self.output("Unknown command. Use /help.")
        else:
            self.send_message(text)
        return True

    def _voice_command(self, name: str, argument: str) -> None:
        from scripts.voice import AudioDevice, VoiceSession
        from app.voice.audio import VoiceError
        try:
            if self.voice_session is None:
                microphone = os.getenv("MOSAIC_MICROPHONE", "")
                device = AudioDevice(int(microphone) if microphone else None,
                                     float(os.getenv("MOSAIC_VAD_THRESHOLD", "0.015")),
                                     float(os.getenv("MOSAIC_VAD_SILENCE_SECONDS", "0.8")))
                self.voice_session = VoiceSession(
                    self, device, language=os.getenv("MOSAIC_VOICE_LANGUAGE", "auto"),
                    voice=os.getenv("MOSAIC_TTS_VOICE") or None,
                    speed=float(os.getenv("MOSAIC_TTS_SPEED", "1")),
                    event_sink=lambda event: self.output(f"Voice: {event.state}") if event.kind == "state" else None,
                )
            session = self.voice_session
            if name == "/mic":
                if argument:
                    session.device.microphone = int(argument)
                    self.output("Microphone selected.")
                else:
                    self.output(json.dumps(session.device.devices(), ensure_ascii=False))
            elif name in {"/voices", "/voice-status"}:
                path = "/voice/voices" if name == "/voices" else "/voice/status"
                response = self.client.get(f"{self.backend_url}{path}", headers=self._auth_headers())
                response.raise_for_status()
                self.output(json.dumps(response.json(), ensure_ascii=False))
                if name == "/voice-status":
                    self.output(json.dumps(session.metrics))
            elif argument == "off":
                session.continuous = False
                self.output("Voice off.")
            elif argument in {"", "on"}:
                self.output("Ctrl+C interrupts voice and returns to text. Microphone pauses during replies.")
                if not argument:
                    self.input("Press Enter to start one utterance (ends on silence): ")
                session.run(continuous=argument == "on")
            else:
                self.output("Usage: /voice [on|off]")
        except (VoiceError, ValueError) as exc:
            self.output(str(exc) if isinstance(exc, VoiceError) else "Invalid numeric voice configuration")
        except httpx.HTTPError:
            self.output("Voice backend unavailable; check configuration and authentication.")

    def send_message(self, message: str) -> str:
        answer: list[str] = []
        completed = False
        response = self.client.stream(
            "POST",
            f"{self.backend_url}/chat/stream",
            json={"message": message, "conversation_id": self.conversation_id},
            headers=self._auth_headers(),
        )
        with response as stream:
            stream.raise_for_status()
            for event, raw_data in parse_sse(stream.iter_lines()):
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    self.output("Backend returned malformed streaming data.")
                    return ""
                if event == "token":
                    answer.append(data.get("text", ""))
                    self.write(data.get("text", ""))
                elif event == "approval_required":
                    self._handle_approval(data)
                elif event == "error":
                    self.output(f"Request failed: {data.get('detail', 'unknown error')}")
                elif event == "done":
                    completed = True
                    if self.show_metrics:
                        self.output(f"Metrics: {json.dumps(data.get('metrics', {}), sort_keys=True)}")
            self.output("")
        return "".join(answer) if completed else ""

    def _handle_approval(self, data: dict[str, Any]) -> None:
        self.output(
            f"Permission request: {data.get('tool_id')} "
            f"{json.dumps(data.get('arguments', {}), ensure_ascii=False, sort_keys=True)}"
        )
        approved = self.input("Approve this one action? [y/N] ").strip().casefold() in {"y", "yes"}
        response = self.client.post(
            f"{self.backend_url}/approvals/{data['approval_id']}/decision",
            json={"approved": approved},
            headers=self._auth_headers(),
        )
        response.raise_for_status()
        self.output("Approved." if approved else "Rejected.")

    def run(self) -> None:
        try:
            self._new_conversation()
            self.help()
            while True:
                try:
                    line = self.input("You> ")
                except EOFError:
                    break
                if not line.strip():
                    continue
                if not self.command(line):
                    break
        except KeyboardInterrupt:
            self.output("\nCancelled; closing the stream and exiting.")
        except httpx.HTTPError as exc:
            self.output(f"Backend connection error: {type(exc).__name__}")
        finally:
            close = getattr(self.client, "close", None)
            if close:
                close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default=os.getenv("MOSAIC_API_URL", "http://127.0.0.1:8000"))
    args = parser.parse_args()
    MosaicCLI(args.backend, token=os.getenv("MOSAIC_API_TOKEN", "")).run()


if __name__ == "__main__":
    main()
