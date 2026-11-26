import asyncio
import io
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
import wave

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.main import create_app
from app.voice.audio import VoiceError, amplitude, decode_wav, encode_wav
from app.voice.providers import MacOSTTS, Transcript, Voice, WhisperCpp, normalize_text, run_local
from scripts.voice import AudioDevice, VoiceSession, sentences

AUTH = {"Authorization": "Bearer " + "v" * 40}
PCM = b"\x00\x10" * 1600
WAV = encode_wav(PCM)


@pytest.mark.parametrize("data", [b"", b"not wave", b"x" * 2_000_001, WAV[:-100]])
def test_audio_rejects_malformed_oversized_and_truncated_data(data):
    with pytest.raises(VoiceError):
        decode_wav(data, microphone=True)


@pytest.mark.parametrize("rate,channels,width,frames", [(44100, 1, 2, 100), (16000, 2, 2, 100), (16000, 1, 1, 100), (16000, 1, 2, 480001)])
def test_transcription_requires_bounded_mono_pcm(rate, channels, width, frames):
    target = io.BytesIO()
    with wave.open(target, "wb") as out:
        out.setframerate(rate)
        out.setnchannels(channels)
        out.setsampwidth(width)
        out.writeframes(b"\0" * frames * channels * width)
    with pytest.raises(VoiceError):
        decode_wav(target.getvalue(), microphone=True)


def test_audio_duration_amplitude_and_normalization():
    assert decode_wav(WAV).duration == 0.1
    assert amplitude(b"\0\0" * 10) == 0
    assert 0 < amplitude(PCM) < 1
    assert normalize_text(" **Hello**\x00  नमस्ते ") == "Hello नमस्ते"
    assert len(sentences("x" * 12001)) == 24


class FakeSTT:
    ready = True

    async def transcribe(self, audio, language):
        assert decode_wav(audio, microphone=True).duration > 0
        return Transcript("test utterance", "en")


class FakeTTS:
    async def voices(self):
        return [Voice("Example", "en_US")]

    async def synthesize(self, text, voice, speed):
        return WAV


def test_voice_api_auth_validation_and_provider_contracts():
    with TestClient(create_app(Settings(api_token="v" * 40))) as client:
        client.app.state.stt, client.app.state.tts = FakeSTT(), FakeTTS()
        for method, path in [("GET", "/voice/status"), ("GET", "/voice/voices"),
                             ("POST", "/voice/transcribe"), ("POST", "/voice/synthesize")]:
            assert client.request(method, path).status_code == 401
        assert client.get("/voice/status", headers=AUTH).json()["timing_support"]["visemes"] is False
        assert client.get("/voice/voices", headers=AUTH).json()["voices"][0]["name"] == "Example"
        response = client.post("/voice/transcribe", content=WAV, headers={**AUTH, "Content-Type": "audio/wav"})
        assert response.json()["text"] == "test utterance"
        assert response.json()["transcription_seconds"] >= 0
        assert client.post("/voice/transcribe", content=WAV, headers=AUTH).status_code == 415
        assert client.post("/voice/transcribe?language=unsupported", content=WAV, headers={**AUTH, "Content-Type": "audio/wav"}).status_code == 422
        assert client.post("/voice/transcribe", content=b"x" * 2_000_001, headers={**AUTH, "Content-Type": "audio/wav"}).status_code == 413
        speech = client.post("/voice/synthesize", json={"text": "Hello"}, headers=AUTH)
        assert speech.content == WAV and speech.headers["cache-control"] == "no-store"
        assert client.post("/voice/synthesize", json={"text": "Hello", "speed": 10}, headers=AUTH).status_code == 422


def test_provider_failure_is_safe_and_next_request_recovers():
    class Broken(FakeTTS):
        async def synthesize(self, *args):
            raise VoiceError("Local speech provider unavailable")
    with TestClient(create_app(Settings(api_token="v" * 40))) as client:
        client.app.state.tts = Broken()
        assert client.post("/voice/synthesize", json={"text": "Hello"}, headers=AUTH).status_code == 503
        client.app.state.tts = FakeTTS()
        assert client.post("/voice/synthesize", json={"text": "Hello"}, headers=AUTH).status_code == 200


def test_whisper_uses_fixed_arguments_and_removes_temporary_audio(monkeypatch, tmp_path):
    executable, model = tmp_path / "whisper-cli", tmp_path / "ggml-base.bin"
    executable.touch(); executable.chmod(0o700); model.touch()
    sources = []
    async def fake_run(*args, **kwargs):
        assert args[0] == str(executable)
        source = Path(args[args.index("-f") + 1])
        sources.append(source)
        assert source.read_bytes() == WAV
        target = Path(args[args.index("-of") + 1] + ".json")
        target.write_text(json.dumps({"transcription": [{"text": "नमस्ते"}], "result": {"language": "hi"}}))
    monkeypatch.setattr("app.voice.providers.run_local", fake_run)
    result = asyncio.run(WhisperCpp(str(executable), str(model)).transcribe(WAV, "auto"))
    assert result == Transcript("नमस्ते", "hi")  # mocked output, not a quality claim
    assert not sources[0].exists()
    with pytest.raises(VoiceError):
        asyncio.run(WhisperCpp("", "").transcribe(WAV, "en"))


def test_tts_installed_voice_allowlist_stdin_and_cleanup(monkeypatch):
    paths = []
    async def fake_run(*args, **kwargs):
        if "?" in args:
            return b"Example en_US # test\nHindi hi_IN # test"
        assert kwargs["input_data"] == "Hello नमस्ते".encode()
        assert "Hello नमस्ते" not in args
        assert args[0] == "/usr/bin/say"
        target = Path(args[args.index("-o") + 1]); paths.append(target)
        target.write_bytes(WAV)
        return b""
    monkeypatch.setattr("app.voice.providers.sys.platform", "darwin")
    monkeypatch.setattr("app.voice.providers.run_local", fake_run)
    provider = MacOSTTS()
    assert asyncio.run(provider.synthesize("Hello नमस्ते", "Hindi", 1)) == WAV
    assert not paths[0].exists()
    with pytest.raises(VoiceError):
        asyncio.run(provider.synthesize("Hello", "not-installed; shell", 1))


@pytest.mark.parametrize("cancel", [False, True])
def test_provider_child_is_reaped_on_timeout_or_cancellation(monkeypatch, cancel):
    class Child:
        returncode = None
        killed = False
        waited = False
        async def communicate(self, _input):
            await asyncio.Event().wait()
        def kill(self):
            self.killed = True
        async def wait(self):
            self.waited = True
            self.returncode = -9
    child = Child()
    monkeypatch.setattr("app.voice.providers.asyncio.create_subprocess_exec", AsyncMock(return_value=child))
    async def check():
        task = asyncio.create_task(run_local("fixed-provider", timeout=0.01))
        if cancel:
            await asyncio.sleep(0)
            task.cancel()
        with pytest.raises((VoiceError, asyncio.CancelledError)):
            await task
        assert child.killed and child.waited
    asyncio.run(check())


def test_capture_vad_closes_stream_and_permission_failure_is_safe(monkeypatch):
    class Input:
        closed = False
        calls = 0
        def start(self): pass
        def read(self, frames):
            self.calls += 1
            return (b"\x00\x10" * frames if self.calls <= 5 else b"\0\0" * frames), False
        def abort(self): pass
        def close(self): self.closed = True
    stream = Input()
    monkeypatch.setattr(AudioDevice, "_driver", staticmethod(lambda: SimpleNamespace(RawInputStream=lambda **kw: stream)))
    data = AudioDevice(silence_seconds=0.2).record(lambda *a, **kw: None)
    assert stream.closed and decode_wav(data, microphone=True).duration < 1
    def denied(**kw): raise PermissionError("private hardware information")
    monkeypatch.setattr(AudioDevice, "_driver", staticmethod(lambda: SimpleNamespace(RawInputStream=denied)))
    with pytest.raises(VoiceError, match="allow Terminal microphone access"):
        AudioDevice().record(lambda *a, **kw: None)


def test_playback_interrupt_aborts_and_closes(monkeypatch):
    class Output:
        closed = aborted = False
        def start(self): pass
        def write(self, block): raise KeyboardInterrupt
        def abort(self): self.aborted = True
        def close(self): self.closed = True
    stream = Output()
    monkeypatch.setattr(AudioDevice, "_driver", staticmethod(lambda: SimpleNamespace(RawOutputStream=lambda **kw: stream)))
    with pytest.raises(KeyboardInterrupt):
        AudioDevice().play(decode_wav(WAV), lambda *a, **kw: None)
    assert stream.closed and stream.aborted


def test_voice_states_reuse_chat_conversation_and_preserve_approval(monkeypatch):
    from scripts.chat import MosaicCLI
    from app.models.ollama_client import StreamEvent
    class Ollama:
        async def list_models(self): return [{"name": "gpt-oss:20b"}]
        async def running_models(self): return []
        async def stream_chat(self, model, messages, keep_alive, tools=None):
            call = {"function": {"name": "applications_launch", "arguments": {"application": "Finder"}}}
            if messages[-1]["role"] == "tool":
                yield StreamEvent(content="Request rejected.")
                yield StreamEvent(done=True)
            else:
                yield StreamEvent(tool_calls=[call], assistant_message={"role": "assistant", "tool_calls": [call]}, done=True)
    # Real HTTP CLI + FastAPI stream; approval occurs on another concurrent request.
    monkeypatch.setattr("app.main.installed_application_path", lambda name: "/fixed/Finder.app")
    class Hardware:
        played = False
        def record(self, emit): return WAV
        def play(self, audio, emit): self.played = True
    events = []
    with TestClient(create_app(Settings(api_token="v" * 40), Ollama())) as client:
        client.app.state.stt, client.app.state.tts = FakeSTT(), FakeTTS()
        cli = MosaicCLI("http://localhost", token="v" * 40, client=client,
                        input_fn=lambda prompt: "no", output_fn=lambda s: None, write_fn=lambda s: None)
        cli._new_conversation()
        identity = cli.conversation_id
        hardware = Hardware()
        session = VoiceSession(cli, hardware, event_sink=events.append)
        session.once()
        assert session.state == "idle" and hardware.played
        assert [e.state for e in events if e.kind == "state"] == ["listening", "transcribing", "thinking", "speaking", "idle"]
        assert any(e.kind == "speech_start" for e in events) and any(e.kind == "speech_end" for e in events)
        assert all(e.visemes is None and e.phonemes is None for e in events)
        history = client.get(f"/conversations/{identity}", headers=AUTH).json()["messages"]
        assert [m["content"] for m in history] == ["test utterance", "Request rejected."]
        assert any(e["approval_outcome"] == "denied" for e in client.app.state.audit.recent())


def test_voice_continuous_requires_activation_and_recovers_after_error():
    class Hardware:
        def record(self, emit): raise VoiceError("No speech detected")
    outputs = []
    cli = SimpleNamespace(output=outputs.append, backend_url="http://localhost")
    session = VoiceSession(cli, Hardware())
    assert not session.continuous
    session.run(continuous=True)
    assert not session.continuous and session.state == "idle"
    assert outputs == ["No speech detected"]


@pytest.mark.parametrize("url", ["https://example.com", "http://user:secret@localhost", "file:///tmp/input"])
def test_voice_refuses_nonlocal_backend_and_embedded_credentials(url):
    with pytest.raises(VoiceError):
        VoiceSession(SimpleNamespace(backend_url=url), AudioDevice())


def test_no_speech_capture_releases_microphone(monkeypatch):
    class Input:
        closed = False
        def start(self): pass
        def read(self, frames): return b"\0\0" * frames, False
        def abort(self): pass
        def close(self): self.closed = True
    source = Input()
    monkeypatch.setattr(AudioDevice, "_driver", staticmethod(lambda: SimpleNamespace(RawInputStream=lambda **kw: source)))
    with pytest.raises(VoiceError, match="No speech detected"):
        AudioDevice().record(lambda *args, **kwargs: None)
    assert source.closed


def test_disconnected_voice_request_cancels_provider():
    from app.api.voice import _connected
    from fastapi import HTTPException
    closed = []
    class Request:
        async def is_disconnected(self):
            await asyncio.sleep(0)
            return True
    async def hanging():
        try:
            await asyncio.Event().wait()
        finally:
            closed.append(True)
    async def check():
        with pytest.raises(HTTPException):
            await _connected(Request(), hanging())
        assert closed == [True]
    asyncio.run(check())


def test_cli_voice_commands_are_explicit_and_preserve_text_mode():
    from scripts.chat import MosaicCLI
    output = []
    runs = []
    session = SimpleNamespace(continuous=False, metrics={}, device=SimpleNamespace(microphone=None),
                              run=lambda **kwargs: runs.append(kwargs))
    cli = MosaicCLI("http://localhost", token="test", output_fn=output.append,
                    input_fn=lambda prompt: "", client=SimpleNamespace())
    cli.voice_session = session
    assert cli.command("/voice")
    assert runs == [{"continuous": False}]
    cli.command("/voice on")
    assert runs[-1] == {"continuous": True}
    cli.command("/mic 2")
    assert session.device.microphone == 2
    cli.command("/voice off")
    assert not session.continuous
    assert not cli.command("/exit")
