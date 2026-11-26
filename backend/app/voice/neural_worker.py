"""Isolated MLX worker. Private stdin/stdout JSONL; never a network service.

Run only with the trusted neural Python interpreter. stdout is IPC, not a log stream.
"""
import base64
from contextlib import redirect_stdout, redirect_stderr
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from app.voice.audio import encode_wav

MAX_LINE = 8192
MAX_RESPONSE = 3_000_000
VOICES = {'af_bella': 'a', 'hf_alpha': 'h'}


def validate_request(value):
    if not isinstance(value, dict) or set(value) != {'id','text','voice','speed'}:
        raise ValueError('Invalid IPC request')
    if (type(value['id']) is not int or not isinstance(value['text'],str) or not 0 < len(value['text']) <= 500
        or value['voice'] not in VOICES or type(value['speed']) not in (float,int) or not 0.5 <= value['speed'] <= 2):
        raise ValueError('Invalid IPC request')
    return value


def main() -> None:
    import fcntl
    lock = open(os.environ['MOSAIC_NEURAL_LOCK'], 'a')
    os.chmod(lock.name, 0o600)
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    pipe = os.fdopen(os.dup(sys.stdout.fileno()), "w", buffering=1)
    # Third-party libraries print pipeline warnings and text: discard, never IPC/log them.
    with open(os.devnull, 'w') as null, redirect_stdout(null), redirect_stderr(null):
        os.dup2(null.fileno(), 1)
        os.dup2(null.fileno(), 2)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1')
        # Enforce offline even if a dependency tries an implicit asset download.
        import socket
        def offline(*args, **kwargs):
            raise RuntimeError('Neural voice runtime is offline')
        socket.socket.connect = offline
        import mlx.core as mx
        import numpy as np
        from mlx_audio.tts.utils import load_model
        from mlx.utils import tree_flatten
        model_path = Path(os.environ['MOSAIC_NEURAL_MODEL'])
        for file in ['config.json', 'kokoro-v1_0.safetensors', 'voices/af_bella.safetensors', 'voices/hf_alpha.safetensors']:
            if not (model_path / file).is_file():
                raise RuntimeError('Missing cached model asset')
        started = time.monotonic()
        model = load_model(model_path)
        loaded = time.monotonic() - started
        def generate(text, voice, speed):
            started = time.monotonic()
            pcm = []
            rate = None
            for part in model.generate(text, voice=voice, speed=speed, lang_code=VOICES[voice]):
                rate = part.sample_rate
                values = np.asarray(part.audio).reshape(-1)
                pcm.append((np.clip(values, -1, 1) * 32767).astype('<i2').tobytes())
            raw = b''.join(pcm)
            if rate != 24000 or not raw or len(raw) > 1_900_000:
                raise RuntimeError('Invalid generated audio')
            return encode_wav(raw, rate), {'synthesis_seconds': time.monotonic()-started,
                'audio_seconds':len(raw)/(rate*2), 'sample_rate':rate, 'mlx_peak_bytes':mx.get_peak_memory()}
        warm = os.environ.get('MOSAIC_NEURAL_WARMUP', '1') == '1'
        if warm:
            generate('Ready.', 'af_bella', 1)
            generate('नमस्ते।', 'hf_alpha', 1)
        def send(value):
            encoded = json.dumps(value, separators=(',', ':'))
            if len(encoded) > MAX_RESPONSE:
                raise RuntimeError('IPC response exceeds limit')
            pipe.write(encoded+'\n'); pipe.flush()
        send({'version':1, 'state':'ready', 'warmed':warm, 'model_load_seconds':loaded,
              'parameter_dtypes':sorted({str(value.dtype) for _,value in tree_flatten(model.parameters())}),
              'mlx_peak_bytes':mx.get_peak_memory()})
        while True:
            line = sys.stdin.buffer.readline(MAX_LINE+1)
            if not line:
                break
            if len(line) > MAX_LINE or not line.endswith(b'\n'):
                break
            identity = None
            try:
                value = json.loads(line)
                identity = value['id']
                validate_request(value)
                audio, metrics = generate(value['text'], value['voice'], value['speed'])
                send({'id':identity,'audio':base64.b64encode(audio).decode('ascii'),'metrics':metrics})
            except Exception:
                send({'id':identity,'error':'Neural synthesis failed; inspect offline assets and voice configuration'})


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # No third-party stack traces, text, credentials, or model contents on stderr.
        sys.exit(1)
