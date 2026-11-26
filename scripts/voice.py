"""Terminal voice orchestration; imports audio hardware only after explicit activation."""

from collections.abc import Callable
from dataclasses import dataclass
import re
import time
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from scripts.chat import MosaicCLI

from app.voice.audio import Audio, VoiceError, amplitude, decode_wav, encode_wav, require_loopback

State = Literal["idle", "listening", "transcribing", "thinking", "speaking"]


@dataclass(frozen=True)
class VoiceEvent:
    kind: str
    state: State
    elapsed_seconds: float
    amplitude: float | None = None
    playback_seconds: float | None = None
    # Timing is unavailable unless a future provider supplies actual alignment.
    phonemes: None = None
    visemes: None = None


class AudioDevice:
    def __init__(self, microphone: int | None = None, threshold: float = 0.015,
                 silence_seconds: float = 0.8) -> None:
        if not 0 < threshold < 1 or not 0.2 <= silence_seconds <= 3:
            raise VoiceError("Invalid VAD threshold or silence duration")
        self.microphone, self.threshold, self.silence_seconds = microphone, threshold, silence_seconds

    @staticmethod
    def _driver():
        try:
            import sounddevice
            return sounddevice
        except (ImportError, OSError) as exc:
            raise VoiceError("Install backend[voice] and a working local PortAudio runtime") from exc

    def devices(self) -> list[dict]:
        try:
            return [{"index": index, "name": item["name"], "inputs": item["max_input_channels"]}
                    for index, item in enumerate(self._driver().query_devices()) if item["max_input_channels"]]
        except VoiceError:
            raise
        except Exception as exc:
            raise VoiceError("Cannot enumerate microphones; check macOS audio permissions") from exc

    def record(self, emit: Callable[..., None]) -> bytes:
        """Energy VAD with bounded pre-roll, silence hangover and 30 second hard cap."""
        stream = None
        try:
            stream = self._driver().RawInputStream(samplerate=16000, channels=1, dtype="int16",
                                                   device=self.microphone, blocksize=320)
            stream.start()
            frames: list[bytes] = []
            pre_roll: list[bytes] = []
            speech = False
            quiet = 0
            for _ in range(1500):  # 30s, 20ms blocks
                data, overflowed = stream.read(320)
                if overflowed:
                    raise VoiceError("Microphone overflow; try again")
                block = bytes(data)
                level = amplitude(block)
                emit("input_amplitude", amplitude=level)
                if level >= self.threshold:
                    if not speech:
                        frames.extend(pre_roll)
                        pre_roll.clear()
                    speech, quiet = True, 0
                else:
                    quiet += 1
                if speech:
                    frames.append(block)
                    if quiet * 0.02 >= self.silence_seconds:
                        break
                else:
                    pre_roll.append(block)
                    pre_roll = pre_roll[-10:]
                    if quiet >= 500:  # no speech in 10s
                        break
            if not speech:
                raise VoiceError("No speech detected; check the microphone or VAD threshold")
            return encode_wav(b"".join(frames))
        except (VoiceError, KeyboardInterrupt):
            raise
        except Exception as exc:
            raise VoiceError("Microphone unavailable; allow Terminal microphone access in macOS Settings") from exc
        finally:
            if stream is not None:
                try:
                    stream.abort()
                finally:
                    stream.close()

    def play(self, audio: Audio, emit: Callable[..., None]) -> None:
        stream = None
        try:
            stream = self._driver().RawOutputStream(samplerate=audio.rate, channels=1, dtype="int16")
            stream.start()
            block_bytes = int(audio.rate * 0.02) * 2
            for offset in range(0, len(audio.pcm), block_bytes):
                block = audio.pcm[offset:offset + block_bytes]
                emit("playback_amplitude", amplitude=amplitude(block), playback_seconds=offset / (audio.rate * 2))
                stream.write(block)
            stream.stop()
        except (VoiceError, KeyboardInterrupt):
            raise
        except Exception as exc:
            raise VoiceError("Audio playback unavailable; check output device") from exc
        finally:
            if stream is not None:
                try:
                    stream.abort()
                finally:
                    stream.close()


def sentences(text: str) -> list[str]:
    """Bound chunks for sentence-level TTS; do not speak arbitrary unbounded replies."""
    result: list[str] = []
    for sentence in re.split(r"(?<=[.!?।])\s+|\n+", text[:12000]):
        while sentence:
            result.append(sentence[:500])
            sentence = sentence[500:]
    return result


class VoiceSession:
    def __init__(self, cli: "MosaicCLI", device: AudioDevice, *, language: str = "auto", voice: str | None = None,
                 speed: float = 1, event_sink: Callable[[VoiceEvent], None] | None = None) -> None:
        if language not in {"en", "hi", "auto"} or not 0.5 <= speed <= 2:
            raise VoiceError("Invalid voice language or speaking speed")
        require_loopback(cli.backend_url)
        self.cli, self.device = cli, device
        self.language, self.voice, self.speed = language, voice, speed
        self.state: State = "idle"
        self.continuous = False
        self.started = time.monotonic()
        self.event_sink = event_sink or (lambda event: None)
        self.metrics: dict[str, float | None] = {}

    def emit(self, kind: str, **values) -> None:
        self.event_sink(VoiceEvent(kind, self.state, round(time.monotonic() - self.started, 6), **values))

    def change(self, state: State) -> None:
        self.state = state
        self.emit("state")

    def once(self) -> None:
        self.started = time.monotonic()
        self.metrics = {"transcription_seconds": None, "time_to_first_audio_seconds": None,
                        "total_response_seconds": None}
        try:
            self.change("listening")
            audio = self.device.record(self.emit)
            decode_wav(audio, microphone=True)
            self.change("transcribing")
            response = self.cli.client.post(
                f"{self.cli.backend_url}/voice/transcribe", content=audio,
                params={"language": self.language},
                headers={**self.cli._auth_headers(), "Content-Type": "audio/wav"},
            )
            audio = b""
            response.raise_for_status()
            transcript = response.json()
            self.metrics["transcription_seconds"] = transcript.get("transcription_seconds")
            text = transcript.get("text", "").strip()
            if not text:
                raise VoiceError("No speech was transcribed")
            # No slash-command interpretation: transcription is conversation input only.
            self.change("thinking")
            reply_started = time.monotonic()
            answer = self.cli.send_message(text)
            for sentence in sentences(answer):
                response = self.cli.client.post(
                    f"{self.cli.backend_url}/voice/synthesize", headers=self.cli._auth_headers(),
                    json={"text": sentence, "voice": self.voice, "speed": self.speed},
                )
                response.raise_for_status()
                audio_result = decode_wav(response.content)
                self.change("speaking")
                if self.metrics["time_to_first_audio_seconds"] is None:
                    self.metrics["time_to_first_audio_seconds"] = round(time.monotonic() - reply_started, 6)
                self.emit("speech_start", playback_seconds=0)
                try:
                    self.device.play(audio_result, self.emit)
                finally:
                    self.emit("speech_end")
            self.metrics["total_response_seconds"] = round(time.monotonic() - reply_started, 6)
        finally:
            self.change("idle")

    def run(self, continuous: bool = False) -> None:
        self.continuous = continuous  # only an explicit /voice on sets this true
        try:
            while True:
                self.once()
                if not self.continuous:
                    break
        except KeyboardInterrupt:
            self.cli.output("Voice interrupted. Returned to text mode.")
        except VoiceError as exc:
            self.cli.output(str(exc))
        except Exception as exc:
            # Do not echo request objects, bearer tokens, audio or transcript content.
            self.cli.output(f"Voice request failed: {type(exc).__name__}. Use /voice-status.")
        finally:
            self.continuous = False
            self.change("idle")
