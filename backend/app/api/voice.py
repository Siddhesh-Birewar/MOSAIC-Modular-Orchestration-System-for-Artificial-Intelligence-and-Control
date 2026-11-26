"""Authenticated, bounded, local speech APIs. Hardware belongs to the CLI client."""

import asyncio
from dataclasses import asdict
import time
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from app.api.tools import require_local_token
from app.voice.audio import MAX_AUDIO_BYTES, VoiceError, VoiceInputError, decode_wav
from app.voice.diagnostics import VoiceDiagnosticError
from app.voice.language import language_issue, script_counts

router = APIRouter(prefix="/voice", dependencies=[Depends(require_local_token)])


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: Literal["kokoro", "macos"] | None = None
    language: Literal["auto", "en", "hi", "hinglish"] = "auto"
    detected_language: Literal["en", "hi"] | None = None
    text: str = Field(min_length=1, max_length=1000)
    voice: str | None = Field(default=None, max_length=100)
    speed: float = Field(default=1, ge=0.5, le=2, allow_inf_nan=False)


async def _connected(request: Request, operation):
    """Cancel speech work when its HTTP client disconnects, including child cleanup."""
    task = asyncio.create_task(operation)
    session = request.headers.get("x-voice-session") if hasattr(request, "headers") else None
    active = getattr(getattr(getattr(request, "app", None), "state", None), "voice_requests", None)
    if session and active is not None:
        try:
            session = str(UUID(session))
        except ValueError:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            raise HTTPException(status_code=422, detail="Invalid voice session")
        active.setdefault(session, set()).add(task)
        if request.app.state.voice_cancelled_sessions.get(session,0) > time.monotonic():
            task.cancel()
    try:
        while not task.done():
            if await request.is_disconnected():
                raise HTTPException(status_code=499, detail="Voice request disconnected")
            await asyncio.sleep(0.05)
        try:
            return await task
        except asyncio.CancelledError:
            raise HTTPException(status_code=409, detail="Voice synthesis cancelled",
                                headers={"X-Voice-Error-Category":"cancelled"})
    finally:
        if session and active is not None:
            active.get(session, set()).discard(task)
            if not active.get(session):
                active.pop(session, None)
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@router.post("/cancel/{session_id}")
async def cancel(session_id: UUID, request: Request):
    now = time.monotonic()
    cancelled = {key:expiry for key,expiry in request.app.state.voice_cancelled_sessions.items() if expiry > now}
    if len(cancelled) >= 512:
        cancelled.pop(next(iter(cancelled)))
    cancelled[str(session_id)] = now + 60
    request.app.state.voice_cancelled_sessions = cancelled
    tasks = list(request.app.state.voice_requests.get(str(session_id), set()))
    for task in tasks:
        task.cancel()
    return {"cancelled_requests":len(tasks)}


@router.get("/status")
async def status(request: Request):
    provider = request.app.state.stt
    return {"stt": "whisper.cpp", "stt_ready": provider.ready,
            "tts": request.app.state.settings.tts_provider,
            "worker":request.app.state.neural.status(),
            "last_synthesis":request.app.state.voice_engine.last,
            "active_provider":request.app.state.voice_engine.last.get("provider"),
            "capabilities":{"languages":["en","hi","hinglish"],"neural_voices":["af_bella","hf_alpha"],
                            "waveform_streaming":False,"sentence_streaming":True,"acoustic_barge_in":False}, "language_quality_verified": False,
            "recordings_retained": False, "max_recording_seconds": 30,
            "timing_support": {"phonemes": False, "visemes": False}}


@router.get("/voices")
async def voices(request: Request, provider: Literal["kokoro", "macos"] | None = None):
    try:
        async with request.app.state.voice_lock:
            engine = request.app.state.voice_engine if provider == "kokoro" else (request.app.state.voice_engine.macos if provider == "macos" else request.app.state.tts)
            result = await _connected(request, engine.voices())
        return {"voices": [asdict(item) for item in result]}
    except VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/transcribe")
async def transcribe(request: Request, response: Response, language: Literal["auto", "en", "hi"] = "auto"):
    if request.headers.get("content-type", "").split(";")[0] not in {"audio/wav", "audio/x-wav"}:
        raise HTTPException(status_code=415, detail="Send audio/wav PCM data")
    data = bytearray()
    async for chunk in request.stream():
        data.extend(chunk)
        if len(data) > MAX_AUDIO_BYTES:
            raise HTTPException(status_code=413, detail="Audio exceeds 2 MB limit")
    try:
        decode_wav(bytes(data), microphone=True)
        started = time.monotonic()
        async with request.app.state.voice_lock:
            result = await _connected(request, request.app.state.stt.transcribe(bytes(data), language))
        response.headers["Cache-Control"] = "no-store"
        issue = language_issue(result.text, language, result.language)
        return {"text": result.text, "language": result.language, "requested_language":language,
                "language_source":"detected" if language == "auto" else "selected",
                "validation":{"accepted":issue is None, "category":issue, "scripts":script_counts(result.text)},
                "transcription_seconds": round(time.monotonic() - started, 6)}
    except VoiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        data.clear()


@router.post("/warmup")
async def warmup(request: Request):
    try:
        return await _connected(request, request.app.state.neural.warm())
    except VoiceDiagnosticError as exc:
        return _diagnostic_response(exc)
    except VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _diagnostic_response(error: VoiceDiagnosticError) -> JSONResponse:
    return JSONResponse(status_code=503, content={"detail":str(error), "diagnostic":error.diagnostic},
                        headers={"Cache-Control":"no-store", "X-Voice-Error-Category":error.category})


@router.post("/synthesize")
async def synthesize(body: SpeechRequest, request: Request):
    started = time.monotonic()
    try:
        if body.provider is not None or request.app.state.settings.tts_provider == "kokoro":
            data = await _connected(request, request.app.state.voice_engine.synthesize(
                body.text, body.voice, body.speed, provider=body.provider, language=body.language,
                detected=body.detected_language))
            metadata = request.app.state.voice_engine.last
        else:
            async with request.app.state.voice_lock:
                data = await _connected(request, request.app.state.tts.synthesize(body.text, body.voice, body.speed))
            metadata = {"provider":"macos", "fallback":False}
        audio = decode_wav(data)
        return Response(data, media_type="audio/wav", headers={
            "Cache-Control": "no-store", "X-Synthesis-Seconds": str(round(time.monotonic() - started, 6)),
            "X-TTS-Provider":str(metadata["provider"]), "X-TTS-Fallback":str(metadata["fallback"]).lower(),
            "X-Sample-Rate":str(audio.rate),
            "X-Audio-Duration": str(round(audio.duration, 6)),
        })
    except VoiceDiagnosticError as exc:
        return _diagnostic_response(exc)
    except VoiceInputError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except VoiceError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
