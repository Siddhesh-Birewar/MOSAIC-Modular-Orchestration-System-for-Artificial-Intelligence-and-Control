"""Narrow local speech adapters. No shell, downloads, or arbitrary model commands."""

import asyncio
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import sys
from tempfile import TemporaryDirectory
import unicodedata
from typing import Protocol

from app.voice.audio import MAX_AUDIO_BYTES, VoiceError, decode_wav


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None


@dataclass(frozen=True)
class Voice:
    name: str
    language: str


class STTProvider(Protocol):
    @property
    def ready(self) -> bool: ...
    async def transcribe(self, audio: bytes, language: str) -> Transcript: ...


class TTSProvider(Protocol):
    async def voices(self) -> list[Voice]: ...
    async def synthesize(self, text: str, voice: str | None, speed: float) -> bytes: ...


async def run_local(*arguments: str, timeout: float = 120, input_data: bytes | None = None) -> bytes:
    """Run fixed provider arguments; reap children on timeout or cancellation."""
    try:
        process = await asyncio.create_subprocess_exec(
            *arguments, stdin=asyncio.subprocess.PIPE if input_data is not None else asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
    except OSError as exc:
        raise VoiceError("Local speech executable is unavailable") from exc
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(input_data), timeout)
        if process.returncode != 0:
            raise VoiceError("Local speech provider failed; check installation and configuration")
        if len(stdout) > MAX_AUDIO_BYTES:
            raise VoiceError("Speech provider output exceeds limit")
        return stdout
    except TimeoutError as exc:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise VoiceError("Local speech provider timed out") from exc
    except BaseException:
        if process.returncode is None:
            process.kill()
        await process.wait()
        raise


class WhisperCpp:
    def __init__(self, executable: str, model: str) -> None:
        self.executable, self.model = executable, model

    @property
    def ready(self) -> bool:
        return (Path(self.executable).is_absolute() and Path(self.executable).is_file() and os.access(self.executable, os.X_OK)
                and Path(self.model).is_absolute() and Path(self.model).is_file())

    async def transcribe(self, audio: bytes, language: str) -> Transcript:
        decode_wav(audio, microphone=True)
        if language not in {"auto", "en", "hi"}:
            raise VoiceError("Language must be auto, en, or hi")
        if not self.ready:
            raise VoiceError("Configure existing local whisper-cli and multilingual model paths")
        with TemporaryDirectory(prefix="mosaic-stt-") as directory:
            source = Path(directory) / "input.wav"
            output = Path(directory) / "result"
            source.write_bytes(audio)
            try:
                await run_local(self.executable, "-m", self.model, "-f", str(source),
                                "-l", language, "-oj", "-of", str(output), "-nt")
                result = Path(str(output) + ".json")
                if result.stat().st_size > MAX_AUDIO_BYTES:
                    raise VoiceError("Transcription exceeds output limit")
                payload = json.loads(result.read_text(encoding="utf-8"))
                segments = payload["transcription"]
                if not isinstance(segments, list) or any(
                    not isinstance(segment, dict) or not isinstance(segment.get("text"), str)
                    for segment in segments
                ):
                    raise VoiceError("Local transcription returned invalid segments")
                text = " ".join(segment["text"].strip() for segment in segments)
                detected = payload.get("result", {}).get("language")
                if len(text) > 20000:
                    raise VoiceError("Transcription exceeds text limit")
                return Transcript(text, detected if isinstance(detected, str) else None)
            except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
                raise VoiceError("Local transcription returned invalid output") from exc


def normalize_text(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    # Avoid sending markup/control characters to a speech engine; preserve Devanagari.
    text = re.sub(r"```.*?```", " Code omitted. ", text, flags=re.S)
    text = re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", " ", text)
    text = re.sub(r"[*_`#]", "", text)
    text = " ".join(text.split())
    if not text or len(text) > 1000:
        raise VoiceError("Speakable text must contain 1 to 1000 characters")
    return text


class MacOSTTS:
    """Use installed macOS voices. No implicit voice/model downloads."""

    async def voices(self) -> list[Voice]:
        if sys.platform != "darwin":
            raise VoiceError("macOS speech is unavailable on this platform")
        output = await run_local("/usr/bin/say", "-v", "?", timeout=10)
        voices = []
        for line in output.decode("utf-8").splitlines():
            match = re.match(r"^(.+?)\s+([a-z]{2,3}_[A-Z]{2})\s+#", line)
            if match:
                voices.append(Voice(match[1].strip(), match[2]))
        return voices

    async def synthesize(self, text: str, voice: str | None, speed: float) -> bytes:
        text = normalize_text(text)
        if not 0.5 <= speed <= 2:
            raise VoiceError("Speaking speed must be between 0.5 and 2")
        voices = await self.voices()
        chosen = next((item for item in voices if item.name == voice), None) if voice else next(
            (item for item in voices if item.language == "en_US"), None)
        if chosen is None:
            raise VoiceError("Select an installed voice using /voices")
        with TemporaryDirectory(prefix="mosaic-tts-") as directory:
            path = Path(directory) / "speech.wav"
            # Input uses stdin so personal content is absent from process arguments.
            await run_local("/usr/bin/say", "-v", chosen.name, "-r", str(int(175 * speed)),
                            "-o", str(path), "--file-format=WAVE", "--data-format=LEI16@22050",
                            "-f", "-", input_data=text.encode("utf-8"), timeout=60)
            try:
                if path.stat().st_size > MAX_AUDIO_BYTES:
                    raise VoiceError("Speech output exceeds audio limit; use shorter sentences")
                data = path.read_bytes()
                decode_wav(data)
                return data
            except OSError as exc:
                raise VoiceError("Speech provider did not generate audio") from exc
