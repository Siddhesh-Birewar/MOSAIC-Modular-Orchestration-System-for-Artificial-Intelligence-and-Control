"""Bounded lifecycle manager for a single isolated Kokoro worker per model/user."""
import asyncio
import base64
from collections import deque
import hashlib
import json
import math
import os
from pathlib import Path
import time

import psutil

from app.voice.audio import VoiceError, VoiceInputError, decode_wav
from app.voice.providers import MacOSTTS, Voice
from app.voice.text import VOICES, language_for, normalize_speech
from app.voice.diagnostics import CATEGORIES, VoiceDiagnosticError
from app.voice.language import script_counts


def cached_model(configured: str = '') -> Path:
    if configured:
        path = Path(configured).expanduser()
    else:
        root = Path(os.getenv('HF_HOME', Path.home()/'.cache/huggingface')) / 'hub/models--mlx-community--Kokoro-82M-bf16'
        ref = root/'refs/main'
        if not ref.is_file():
            raise VoiceError('Cached Kokoro revision is missing; configure MOSAIC_KOKORO_MODEL')
        revision = ref.read_text().strip()
        if not revision or any(c not in '0123456789abcdef' for c in revision):
            raise VoiceError('Invalid cached model revision')
        path = root/'snapshots'/revision
    for file in ('config.json','kokoro-v1_0.safetensors','voices/af_bella.safetensors','voices/hf_alpha.safetensors'):
        if not (path/file).is_file():
            raise VoiceError('Required offline Kokoro weights or selected voice assets are missing')
    return path.resolve()


class KokoroWorker:
    def __init__(self, python: str, model: str = '', *, warmup: bool = True, queue_size: int = 3,
                 timeout: float = 60, idle_seconds: float = 180, min_available_mb: int = 1024) -> None:
        if min_available_mb < 1:
            raise ValueError('Neural memory admission floor must be positive')
        self.python, self.model = python, model
        self.warmup, self.capacity, self.timeout = warmup, queue_size, timeout
        self.idle_seconds, self.min_available_mb = idle_seconds, min_available_mb
        self.process = None
        self.lock = asyncio.Lock()
        self.pending = 0
        self.sequence = 0
        self.restarts = deque()
        self.idle_task = None
        self.closed = False
        self.info = {'state':'stopped','warmed':False,'error':None}
        self.last_used = 0.0
        self.metrics = {}
        self.last_diagnostic = None
        self.last_stop = None
        self.completed_requests = 0

    def status(self) -> dict:
        ready = self.process is not None and self.process.returncode is None and self.info.get('state') == 'ready'
        available = psutil.virtual_memory().available
        try:
            rss = psutil.Process(self.process.pid).memory_info().rss if ready else None
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            rss = None
        peak = self.metrics.get('mlx_peak_bytes',self.info.get('mlx_peak_bytes')) if ready else None
        return {**self.info, 'mlx_peak_bytes':peak, 'rss_bytes':rss, 'ready':ready,'pid':self.process.pid if ready else None,
                'pending':self.pending, 'capacity':self.capacity, 'recent_metrics':self.metrics,
                'last_diagnostic':self.last_diagnostic, 'last_stop':self.last_stop,
                'completed_requests':self.completed_requests,
                'available_bytes':available, 'memory_admitted':available >= self.min_available_mb * 1024**2,
                'minimum_available_bytes':self.min_available_mb * 1024**2}

    def _memory_check(self, stage: str) -> None:
        available = psutil.virtual_memory().available
        required = self.min_available_mb * 1024**2
        if available < required:
            raise VoiceDiagnosticError('memory_limit', stage, available_bytes=available, required_bytes=required)

    async def _read(self, stage: str = 'reply') -> dict:
        try:
            line = await self.process.stdout.readline()
            if not line:
                try:
                    await asyncio.wait_for(self.process.wait(), 0.2)
                except TimeoutError:
                    raise VoiceDiagnosticError('invalid_ipc', stage)
                raise VoiceDiagnosticError('worker_exit', stage, exit_code=self.process.returncode)
            if len(line) > 3_000_000 or not line.endswith(b'\n'):
                raise ValueError()
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError()
            return value
        except (ValueError, UnicodeError) as exc:
            raise VoiceDiagnosticError('invalid_ipc', stage) from exc

    async def _stop(self, reason: str = 'shutdown') -> None:
        process, self.process = self.process, None
        if process is not None:
            if process.returncode is None:
                try:
                    process.kill()
                except ProcessLookupError:
                    pass  # Child exited between checking returncode and signalling it.
            await process.wait()
            self.last_stop = {'reason':reason, 'exit_code':process.returncode}
        self.info.update(state='stopped', warmed=False)

    async def _start(self) -> None:
        if self.closed:
            raise VoiceDiagnosticError('cancelled', 'startup')
        if self.process is not None and self.process.returncode is None:
            return
        if self.process is not None:
            self.last_diagnostic = VoiceDiagnosticError('worker_exit','retention',exit_code=self.process.returncode).diagnostic
            await self._stop('worker_exit')
        now = time.monotonic()
        while self.restarts and now-self.restarts[0] > 60:
            self.restarts.popleft()
        if len(self.restarts) >= 3:
            raise VoiceDiagnosticError('restart_limit', 'startup')
        self._memory_check('startup')
        try:
            model = cached_model(self.model)
        except VoiceError as exc:
            raise VoiceDiagnosticError('unavailable', 'assets') from exc
        if not Path(self.python).is_absolute() or not os.access(self.python, os.X_OK):
            raise VoiceDiagnosticError('unavailable', 'interpreter')
        lock_dir = Path.home()/'.cache/mosaic-voice'
        lock_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        key = hashlib.sha256(str(model).encode()).hexdigest()[:16]
        # Do not inherit backend credentials, API tokens or user Python startup configuration.
        env = {k:v for k,v in os.environ.items() if k in {'HOME','PATH','TMPDIR','LANG','LC_ALL','HF_HOME'}}
        env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',TOKENIZERS_PARALLELISM='false',
                   MOSAIC_NEURAL_MODEL=str(model), MOSAIC_NEURAL_LOCK=str(lock_dir/(key+'.lock')),
                   MOSAIC_NEURAL_WARMUP='1' if self.warmup else '0')
        self.metrics = {}
        startup = time.monotonic()
        self.info.update(state='loading', error=None)
        self.restarts.append(now)  # Admission/configuration failures are not process restarts.
        self.process = await asyncio.create_subprocess_exec(
            self.python, '-u', str(Path(__file__).with_name('neural_worker.py')),
            stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL, env=env, limit=3_000_001)
        ready = await asyncio.wait_for(self._read('startup'), self.timeout)
        if ready.get('version') != 1 or ready.get('state') != 'ready':
            error = ready.get('error')
            category = error.get('category') if isinstance(error,dict) else None
            raise VoiceDiagnosticError(category if category in CATEGORIES else 'invalid_ipc', 'startup')
        self.info.update(state='ready',warmed=ready.get('warmed') is True)
        for key in ('model_load_seconds','mlx_peak_bytes'):
            if type(ready.get(key)) in (int,float) and math.isfinite(ready[key]) and ready[key] >= 0:
                self.info[key] = ready[key]
        dtypes = ready.get('parameter_dtypes',[])
        self.info['parameter_dtypes'] = [value for value in dtypes if isinstance(value,str) and value in {
            'mlx.core.float32','mlx.core.bfloat16','mlx.core.float16','float32','float16','bfloat16'}] if isinstance(dtypes,list) else []
        self.info["initialization_seconds"] = time.monotonic()-startup
        self.last_used = time.monotonic()
        if self.idle_task is None:
            self.idle_task = asyncio.create_task(self._idle())

    async def _idle(self) -> None:
        try:
            while not self.closed:
                await asyncio.sleep(min(5, self.idle_seconds))
                memory_low = psutil.virtual_memory().available < self.min_available_mb * 1024**2
                if self.pending == 0 and (memory_low or time.monotonic()-self.last_used >= self.idle_seconds):
                    async with self.lock:
                        if self.pending == 0:
                            await self._stop('memory_pressure' if memory_low else 'idle_timeout')
        except asyncio.CancelledError:
            pass

    async def warm(self) -> dict:
        await self.request(None)
        return self.status()

    async def request(self, payload: dict | None) -> bytes | None:
        if self.pending >= self.capacity:
            error = VoiceDiagnosticError('queue_full', 'queue')
            self.last_diagnostic = error.diagnostic
            raise error
        self.pending += 1
        acquired = False
        stage = 'queue'
        inflight = False
        try:
            await asyncio.wait_for(self.lock.acquire(), self.timeout)
            acquired = True
            stage = 'startup'
            await self._start()
            if payload is None:
                return None
            stage = 'admission'
            self._memory_check('admission')
            self.sequence += 1
            packet = json.dumps({'id':self.sequence, **payload}, ensure_ascii=False).encode()+b'\n'
            if len(packet) > 8192:
                raise VoiceDiagnosticError('invalid_ipc', 'request')
            stage = 'write'
            inflight = True
            self.process.stdin.write(packet)
            await asyncio.wait_for(self.process.stdin.drain(), self.timeout)
            stage = 'reply'
            result = await asyncio.wait_for(self._read(), self.timeout)
            if type(result.get('id')) is not int or result['id'] != self.sequence:
                raise VoiceDiagnosticError('invalid_ipc', 'identity')
            if result.get('error'):
                error = result['error']
                category = error.get('category') if isinstance(error,dict) else None
                raise VoiceDiagnosticError(category if category in CATEGORIES else 'synthesis_failure', 'synthesis')
            stage = 'audio'
            try:
                data = base64.b64decode(result.get('audio',''), validate=True)
                decode_wav(data)
            except (ValueError, TypeError, VoiceError) as exc:
                raise VoiceDiagnosticError('invalid_ipc', 'audio') from exc
            if not isinstance(result.get('metrics'), dict):
                raise VoiceDiagnosticError('invalid_ipc', 'metrics')
            # Never forward arbitrary worker data or error strings in diagnostics/status.
            self.metrics = {key:value for key,value in result['metrics'].items()
                            if key in {'sample_rate','synthesis_seconds','audio_seconds','mlx_peak_bytes','mlx_active_bytes','mlx_cache_bytes'}
                            and type(value) in (int,float) and math.isfinite(value) and value >= 0}
            self.completed_requests += 1
            self.info['error'] = None
            return data
        except asyncio.CancelledError:
            self.last_diagnostic = VoiceDiagnosticError('cancelled', stage).diagnostic
            if acquired and (inflight or stage == 'startup'):
                await self._stop('cancelled')  # MLX cannot be interrupted safely in its thread.
            raise
        except Exception as exc:
            if isinstance(exc,VoiceDiagnosticError):
                error = exc
            elif isinstance(exc,TimeoutError):
                error = VoiceDiagnosticError('timeout', stage)
            elif isinstance(exc,MemoryError):
                error = VoiceDiagnosticError('memory_limit', stage)
            elif self.process is not None and self.process.returncode is not None:
                error = VoiceDiagnosticError('worker_exit',stage,exit_code=self.process.returncode)
            else:
                error = VoiceDiagnosticError('unavailable' if stage == 'startup' else 'synthesis_failure',stage)
            # A rejected admission or queued waiter must not kill a healthy worker.
            if acquired and (inflight or stage == 'startup'):
                await self._stop(error.category)
            self.info['error'] = str(error)
            self.last_diagnostic = error.diagnostic
            raise error from exc
        finally:
            self.last_used = time.monotonic()
            self.pending -= 1
            if acquired:
                self.lock.release()

    async def close(self) -> None:
        self.closed = True
        if self.idle_task:
            self.idle_task.cancel()
            await asyncio.gather(self.idle_task, return_exceptions=True)
        async with self.lock:
            await self._stop()


class VoiceEngine:
    def __init__(self, worker: KokoroWorker, default: str = 'kokoro', fallback: bool = False) -> None:
        self.worker, self.default, self.fallback = worker, default, fallback
        self.macos = MacOSTTS()
        self.last = {'provider':default, 'fallback':False, 'error':None}
        self.native_lock = asyncio.Lock()
        self.native_pending = 0

    async def voices(self) -> list[Voice]:
        return [Voice('af_bella','en'), Voice('hf_alpha','hi/hinglish')]

    async def synthesize(self, text: str, voice: str | None, speed: float, *, provider: str | None = None,
                         language: str = 'auto', detected: str | None = None) -> bytes:
        chosen = provider or self.default
        if script_counts(text)['unsupported']:
            raise VoiceInputError('Unsupported speech script; use English, Devanagari Hindi or Hinglish')
        text = normalize_speech(text)
        if not text or len(text) > 500 or not 0.5 <= speed <= 2:
            raise VoiceInputError('Neural speech requires 1–500 normalized characters and speed 0.5–2')
        metadata = {'provider':chosen,'fallback':False,'error':None}
        if chosen == 'kokoro':
            lang = language_for(text,language,detected)
            voice = voice or VOICES[lang]
            if voice not in VOICES.values():
                raise VoiceInputError('Select an allowed neural voice: af_bella or hf_alpha')
            # Direct API calls must respect the same Hindi bounds as streamed segmentation.
            if voice == 'hf_alpha' and len(text) > 160:
                raise VoiceInputError('Hindi/Hinglish speech segments must be at most 160 characters')
            try:
                audio = await self.worker.request({'text':text,'voice':voice,'speed':speed})
                metadata.update(provider='kokoro',voice=voice,language=lang,**self.worker.metrics)
                self.last = metadata
                return audio
            except VoiceError:
                if not self.fallback:
                    raise
                metadata.update(provider='macos',fallback=True,error='Kokoro unavailable; explicit configured fallback used')
        if self.native_pending >= 3:
            raise VoiceError('Native synthesis queue is full')
        self.native_pending += 1
        try:
            async with self.native_lock:
                audio = await self.macos.synthesize(text, None if metadata['fallback'] else voice, speed)
                self.last = metadata
                return audio
        finally:
            self.native_pending -= 1
