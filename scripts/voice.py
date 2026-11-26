"""Terminal voice orchestration; imports audio hardware only after explicit activation."""

from collections.abc import Callable
from dataclasses import dataclass
import re
import queue
import threading
import socket
from uuid import uuid4
import time
from typing import TYPE_CHECKING, Literal, Any

if TYPE_CHECKING:
    from scripts.chat import MosaicCLI

from app.voice.audio import Audio, VoiceError, amplitude, decode_wav, encode_wav, require_loopback
from app.voice.text import Segmenter, language_for

State = Literal["idle", "listening", "transcribing", "thinking", "speaking", "cancelling", "error"]


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
        started = ended = False
        submitted = 0.0
        try:
            stream = self._driver().RawOutputStream(samplerate=audio.rate, channels=1, dtype="int16")
            stream.start()
            started = True
            emit("playback_started", playback_seconds=0)
            block_bytes = int(audio.rate * 0.02) * 2
            for offset in range(0, len(audio.pcm), block_bytes):
                block = audio.pcm[offset:offset + block_bytes]
                emit("playback_amplitude", amplitude=amplitude(block), playback_seconds=offset / (audio.rate * 2))
                stream.write(block)
                submitted = (offset + len(block))/(audio.rate*2)
            stream.stop()
            ended = True
            emit("playback_ended", playback_seconds=audio.duration)
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
                    if started and not ended:
                        emit("playback_ended", playback_seconds=submitted)


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
        if language not in {"en", "hi", "hinglish", "auto"} or not 0.5 <= speed <= 2:
            raise VoiceError("Invalid voice language or speaking speed")
        require_loopback(cli.backend_url)
        self.cli, self.device = cli, device
        self.language, self.voice, self.speed = language, voice, speed
        self.state: State = "idle"
        self.continuous = False
        self.provider = None
        self.reasoning = "default"
        self.tools = True
        self.cancelled = threading.Event()
        self.active_stream = None
        self.pending_threads = []
        self.started = time.monotonic()
        self.event_sink = event_sink or (lambda event: None)
        self.metrics: dict[str, Any] = {}

    def emit(self, kind: str, **values) -> None:
        if kind == "playback_amplitude" and self.cancelled.is_set():
            raise VoiceError("Voice playback cancelled")
        if kind == "playback_started" and hasattr(self,"eos"):
            self.metrics.setdefault("playback_started_seconds",time.monotonic()-self.eos)
        self.event_sink(VoiceEvent(kind, self.state, round(time.monotonic() - self.started, 6), **values))

    def change(self, state: State) -> None:
        if self.state == state:
            return
        self.state = state
        self.emit("state")

    def once(self) -> None:
        if any(thread.is_alive() for thread in self.pending_threads):
            raise VoiceError("Previous voice transport is still cancelling; wait before retrying")
        self.started = time.monotonic()
        self.metrics = {"transcription_seconds": None, "time_to_first_audio_seconds": None,
                        "total_response_seconds": None}
        try:
            self.change("listening")
            audio = self.device.record(self.emit)
            decode_wav(audio, microphone=True)
            self.eos = time.monotonic()
            self.change("transcribing")
            response = self.cli.client.post(
                f"{self.cli.backend_url}/voice/transcribe", content=audio,
                params={"language": "auto" if self.language == "hinglish" else self.language},
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
            self._reply(text, transcript.get("language"))
            self.metrics["total_response_seconds"] = round(time.monotonic() - reply_started, 6)
            self.metrics["end_to_end_seconds"] = round(time.monotonic()-self.eos,6)
        except KeyboardInterrupt:
            if self.state != "cancelling":
                self.change("cancelling")
                self.emit("cancellation")
            raise
        except Exception:
            self.change("error")
            raise
        else:
            self.change("idle")

    def _reply(self, text: str, detected: str | None) -> None:
        # Two bounded stages: LLM -> text segments -> synthesis -> ordered main-thread playback.
        self.cancelled.clear()
        session = str(uuid4())
        segments = queue.Queue(maxsize=3)
        audios = queue.Queue(maxsize=2)
        failures = []
        end = object()
        expected = [1]
        def put(target, value):
            while not self.cancelled.is_set():
                try:
                    target.put(value, timeout=0.05)
                    return
                except queue.Full:
                    pass
        def get(target):
            while not self.cancelled.is_set():
                try:
                    return target.get(timeout=0.05)
                except queue.Empty:
                    pass
            return end
        def accept(data):
            if data.get("sequence") != expected[0]:
                raise VoiceError("Speech event ordering mismatch")
            expected[0] += 1
            if self.tools:
                self.metrics.setdefault("first_safe_token_seconds",time.monotonic()-self.eos)
            if "first_segment_seconds" not in self.metrics:
                self.metrics["first_segment_seconds"] = time.monotonic()-self.eos
            put(segments, (data["text"],data.get("language")))
        options = {"voice_mode":True, "voice_tools":self.tools, "voice_language":self.language, "reasoning":self.reasoning}
        # Tool turns read approvals on the main thread and buffer only committed final speech.
        buffered = []
        if self.tools:
            self.cli.send_message(text, speech_sink=buffered.append, voice_options=options)
            if getattr(self.cli,"last_stream_failed",False):
                raise VoiceError("Voice conversation failed; reply was not spoken")
        def produce():
            try:
                if self.tools:
                    for data in buffered:
                        accept(data)
                else:
                    self.cli.send_message(text, speech_sink=accept, voice_options=options,
                        cancelled=self.cancelled, stream_ready=lambda stream: setattr(self,"active_stream",stream),
                        token_sink=lambda data: self.metrics.setdefault("first_safe_token_seconds",time.monotonic()-self.eos))
                    if getattr(self.cli,"last_stream_failed",False):
                        raise VoiceError("Voice conversation stream failed")
            except Exception:
                failures.append("Voice generation failed; no further audio will play")
                self.cancelled.set()
            finally:
                put(segments, end)
        def synthesize():
            try:
                while not self.cancelled.is_set():
                    segment = get(segments)
                    if segment is end:
                        break
                    segment, route = segment
                    started = time.monotonic()
                    response = self.cli.client.post(
                        f"{self.cli.backend_url}/voice/synthesize",
                        headers={**self.cli._auth_headers(),"X-Voice-Session":session},
                        json={"text":segment,"voice":self.voice,"speed":self.speed,
                              "provider":self.provider,"language":route if route in {"en","hi","hinglish"} else language_for(segment,self.language,detected),
                              "detected_language":detected if detected in {"en","hi"} else None})
                    response.raise_for_status()
                    audio = decode_wav(response.content)
                    self.metrics["synthesis_seconds"] = self.metrics.get("synthesis_seconds",0)+time.monotonic()-started
                    self.metrics["audio_seconds"] = self.metrics.get("audio_seconds",0)+audio.duration
                    self.metrics["real_time_factor"] = self.metrics["synthesis_seconds"]/self.metrics["audio_seconds"]
                    if response.headers.get("x-tts-fallback") == "true":
                        self.cli.output("Voice fallback: macOS speech is active.")
                    self.metrics.setdefault("first_generated_audio_seconds",time.monotonic()-self.eos)
                    put(audios, audio)
            except Exception:
                if not self.cancelled.is_set():
                    failures.append("Voice synthesis unavailable; check /voice-status")
                self.cancelled.set()
            finally:
                put(audios, end)
        threads = [threading.Thread(target=produce,daemon=True,name="mosaic-voice-llm"),threading.Thread(target=synthesize,daemon=True,name="mosaic-voice-tts")]
        self.pending_threads = threads
        for thread in threads:
            thread.start()
        try:
            while not self.cancelled.is_set():
                audio = get(audios)
                if audio is end:
                    break
                self.change("speaking")
                self.metrics.setdefault("time_to_first_audio_seconds",time.monotonic()-self.eos)
                self.emit("speech_start",playback_seconds=0)
                try:
                    self.device.play(audio,self.emit)
                finally:
                    self.emit("speech_end")
            if failures:
                raise VoiceError(failures[0])
        except BaseException:
            if self.state != "cancelling":
                self.change("cancelling")
                self.emit("cancellation")
            self.cancelled.set()
            if self.active_stream:
                # close() alone may leave another thread blocked in recv until keep-alive timeout.
                network = getattr(self.active_stream,"extensions",{}).get("network_stream")
                connection = network.get_extra_info("socket") if network else None
                if connection:
                    try:
                        connection.shutdown(socket.SHUT_RDWR)
                    except OSError:
                        pass
                self.active_stream.close()
            try:
                self.cli.client.post(f"{self.cli.backend_url}/voice/cancel/{session}",headers=self.cli._auth_headers())
            except Exception:
                pass
            raise
        finally:
            self.cancelled.set()
            for thread in threads:
                thread.join(timeout=3)
            self.active_stream = None
            self.metrics["llm"] = getattr(self.cli,"last_metrics",{})
            if any(thread.is_alive() for thread in threads):
                self.cli.output("Voice cancellation is still releasing a transport; wait for backend timeout before retrying.")

    def run(self, continuous: bool = False) -> None:
        self.continuous = continuous  # only an explicit /voice on sets this true
        try:
            while True:
                self.once()
                if not self.continuous:
                    break
        except KeyboardInterrupt:
            if self.state != "cancelling":
                self.change("cancelling")
                self.emit("cancellation")
            self.cli.output("Voice interrupted. Returned to text mode.")
        except VoiceError as exc:
            self.change("error")
            self.cli.output(str(exc))
        except Exception as exc:
            self.change("error")
            # Do not echo request objects, bearer tokens, audio or transcript content.
            self.cli.output(f"Voice request failed: {type(exc).__name__}. Use /voice-status.")
        finally:
            self.continuous = False
            self.change("idle")
