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
        self.last_metrics = {}
        self.last_stream_failed = False

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
        self.output("Commands: /help /new /clear /models /model MODEL /status /metrics /exit /voice [on|off] /mic [INDEX] /voices /voice-status /language /tts /speed /reasoning /voice-tools")

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
        elif name in {"/voice", "/mic", "/voices", "/voice-status", "/language", "/tts", "/speed", "/reasoning", "/voice-tools"}:
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
                self.voice_session.provider = os.getenv("MOSAIC_TTS_PROVIDER", "kokoro")
                self.voice_session.reasoning = os.getenv("MOSAIC_VOICE_REASONING", "default")
                self.voice_session.tools = os.getenv("MOSAIC_VOICE_TOOLS", "1") == "1"
            session = self.voice_session
            if name in {"/language", "/tts", "/speed", "/reasoning", "/voice-tools"}:
                if name == "/language":
                    if argument and argument not in {"auto","en","hi","hinglish"}:
                        raise VoiceError("Language: auto, en, hi, hinglish")
                    if argument:
                        session.language = argument
                elif name == "/tts":
                    if argument and argument not in {"kokoro","macos"}:
                        raise VoiceError("TTS: kokoro or macos")
                    if argument:
                        session.provider = argument
                        session.voice = None
                        if argument == "kokoro":
                            response = self.client.post(f"{self.backend_url}/voice/warmup",headers=self._auth_headers())
                            response.raise_for_status()
                            self.output("Neural voice worker is ready.")
                elif name == "/speed" and argument:
                    value = float(argument)
                    if not 0.5 <= value <= 2:
                        raise VoiceError("Speed must be 0.5 to 2")
                    session.speed = value
                elif name == "/reasoning":
                    if argument and argument not in {"default","low","medium","high"}:
                        raise VoiceError("Reasoning: default, low, medium, high (model support checked by backend)")
                    if argument:
                        session.reasoning = argument
                elif name == "/voice-tools":
                    if argument and argument not in {"on","off"}:
                        raise VoiceError("Usage: /voice-tools on|off")
                    if argument:
                        session.tools = argument == "on"
                self.output(json.dumps({"language":session.language,"provider":session.provider,
                    "speed":session.speed,"reasoning":session.reasoning,"tools":session.tools}))
            elif name == "/mic":
                if argument:
                    session.device.microphone = int(argument)
                    self.output("Microphone selected.")
                else:
                    self.output(json.dumps(session.device.devices(), ensure_ascii=False))
            elif name in {"/voices", "/voice-status"}:
                path = "/voice/voices" if name == "/voices" else "/voice/status"
                response = self.client.get(f"{self.backend_url}{path}" + (f"?provider={session.provider}" if name == "/voices" and session.provider else ""), headers=self._auth_headers())
                response.raise_for_status()
                self.output(json.dumps(response.json(), ensure_ascii=False))
                if name == "/voice-status":
                    self.output(json.dumps({"language":session.language,"provider":session.provider,
                        "voice":session.voice or "automatic: af_bella/en, hf_alpha/hi/hinglish",
                        "speed":session.speed,"reasoning":session.reasoning,"tools":session.tools,
                        "metrics":session.metrics,"transport_releasing":any(t.is_alive() for t in session.pending_threads)}))
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

    def send_message(self, message: str, *, speech_sink=None, voice_options=None, cancelled=None, stream_ready=None, token_sink=None) -> str:
        self.last_stream_failed = True
        answer: list[str] = []
        completed = False
        response = self.client.stream(
            "POST",
            f"{self.backend_url}/chat/stream",
            json={"message": message, "conversation_id": self.conversation_id, **(voice_options or {})},
            headers=self._auth_headers(),
        )
        with response as stream:
            stream.raise_for_status()
            if stream_ready:
                stream_ready(stream)
            for event, raw_data in parse_sse(stream.iter_lines()):
                if cancelled is not None and cancelled.is_set():
                    return ""
                try:
                    data = json.loads(raw_data)
                except json.JSONDecodeError:
                    self.output("Backend returned malformed streaming data.")
                    return ""
                if event == "token":
                    answer.append(data.get("text", ""))
                    self.write(data.get("text", ""))
                    if token_sink:
                        token_sink(data)
                elif event == "speech_segment" and speech_sink:
                    if data.get("safety") not in {"tool_free", "completed_orchestration"}:
                        raise ValueError("Uncommitted speech event")
                    speech_sink(data)
                elif event == "approval_required":
                    if voice_options and not voice_options.get("voice_tools", True):
                        raise ValueError("Unexpected approval on tool-free voice turn")
                    self._handle_approval(data)
                elif event == "error":
                    self.output(f"Request failed: {data.get('detail', 'unknown error')}")
                elif event == "done":
                    completed = True
                    self.last_metrics = data.get("metrics", {})
                    if self.show_metrics:
                        self.output(f"Metrics: {json.dumps(data.get('metrics', {}), sort_keys=True)}")
            self.output("")
        self.last_stream_failed = not completed
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
