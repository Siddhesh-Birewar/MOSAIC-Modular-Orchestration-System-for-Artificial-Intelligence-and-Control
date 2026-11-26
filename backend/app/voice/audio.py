"""Bounded PCM WAV validation shared by providers and the terminal client."""

from array import array
from dataclasses import dataclass
import io
import math
import sys
import wave

MAX_AUDIO_BYTES = 2_000_000


class VoiceError(RuntimeError):
    """A safe error message suitable for presentation to the local user."""


class VoiceInputError(VoiceError):
    """Invalid speech input; does not indicate a worker availability failure."""


@dataclass(frozen=True)
class Audio:
    pcm: bytes
    rate: int
    channels: int

    @property
    def duration(self) -> float:
        return len(self.pcm) / (self.rate * self.channels * 2)


def decode_wav(data: bytes, *, microphone: bool = False) -> Audio:
    if not data or len(data) > MAX_AUDIO_BYTES:
        raise VoiceError("Audio is empty or exceeds the 2 MB limit")
    try:
        with wave.open(io.BytesIO(data), "rb") as source:
            rate, channels = source.getframerate(), source.getnchannels()
            if source.getsampwidth() != 2 or source.getcomptype() != "NONE":
                raise VoiceError("Audio must be uncompressed 16-bit PCM WAV")
            if channels != 1 or not 8000 <= rate <= 48000:
                raise VoiceError("Audio must be mono PCM between 8 and 48 kHz")
            if microphone and rate != 16000:
                raise VoiceError("Transcription requires mono 16 kHz PCM WAV")
            frames = source.getnframes()
            duration = frames / rate
            if not 0 < duration <= (30 if microphone else 60):
                raise VoiceError("Audio duration exceeds the allowed limit")
            pcm = source.readframes(frames)
            if len(pcm) != frames * channels * 2:
                raise VoiceError("Audio data is truncated")
    except (wave.Error, EOFError, ValueError) as exc:
        raise VoiceError("Invalid PCM WAV audio") from exc
    return Audio(pcm, rate, channels)


def encode_wav(pcm: bytes, rate: int = 16000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as target:
        target.setnchannels(1)
        target.setsampwidth(2)
        target.setframerate(rate)
        target.writeframes(pcm)
    return buffer.getvalue()


def amplitude(pcm: bytes) -> float:
    """Measured RMS amplitude in [0,1], not a phoneme/viseme estimate."""
    samples = array("h", pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return math.sqrt(sum(value * value for value in samples) / max(1, len(samples))) / 32768


def require_loopback(url: str) -> None:
    """Speech uploads are restricted to a local backend origin."""
    from ipaddress import ip_address
    from urllib.parse import urlsplit
    parsed = urlsplit(url)
    try:
        local = parsed.hostname == "localhost" or ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        local = False
    if not local or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise VoiceError("Voice requires a localhost backend URL without embedded credentials")
