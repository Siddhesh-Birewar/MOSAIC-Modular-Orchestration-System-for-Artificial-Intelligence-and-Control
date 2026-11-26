"""Opt-in local speech benchmark. Never records the microphone or logs transcripts."""

import argparse
import asyncio
import json
import os
from pathlib import Path
import sys
import threading
import time

import httpx
import psutil

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.voice.audio import decode_wav, require_loopback
from app.voice.providers import MacOSTTS
from scripts.chat import MosaicCLI
from scripts.voice import sentences


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tts-only", action="store_true", help="Measure native synthesis without chat or playback")
    parser.add_argument("--audio", type=Path, help="Explicit disposable mono PCM WAV for full pipeline benchmark")
    parser.add_argument("--backend", default="http://127.0.0.1:8000")
    parser.add_argument("--backend-pid", type=int, help="Include backend and its children in RSS sampling")
    args = parser.parse_args()
    if not args.tts_only and args.audio is None:
        parser.error("Choose --tts-only or --audio; --audio persists the transcript and answer as a new conversation")
    require_loopback(args.backend)
    stopped = threading.Event()
    peak = [0]
    processes = [psutil.Process()]
    if args.backend_pid:
        processes.append(psutil.Process(args.backend_pid))
    def sample():
        while not stopped.is_set():
            seen = set()
            rss = 0
            for parent in processes:
                try:
                    for process in [parent, *parent.children(recursive=True)]:
                        if process.pid not in seen:
                            seen.add(process.pid)
                            rss += process.memory_info().rss
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            peak[0] = max(peak[0], rss)
            stopped.wait(0.02)
    worker = threading.Thread(target=sample, daemon=True)
    worker.start()
    metrics = {"transcription_seconds": None, "time_to_first_audio_seconds": None,
               "total_response_seconds": None, "peak_sampled_rss_bytes": None}
    try:
        started = time.monotonic()
        if args.tts_only:
            data = asyncio.run(MacOSTTS().synthesize("MOSAIC local speech verification.", None, 1))
            metrics["time_to_first_audio_seconds"] = round(time.monotonic() - started, 6)
            metrics["generated_audio_seconds"] = round(decode_wav(data).duration, 6)
        else:
            # No microphone use; this explicitly selected test clip is sent to localhost.
            data = args.audio.read_bytes()
            decode_wav(data, microphone=True)
            token = os.getenv("MOSAIC_API_TOKEN", "")
            headers = {"Authorization": f"Bearer {token}"}
            with httpx.Client(timeout=180) as client:
                result = client.post(args.backend + "/voice/transcribe", content=data,
                                     headers={**headers, "Content-Type": "audio/wav"})
                result.raise_for_status()
                transcript = result.json()
                metrics["transcription_seconds"] = transcript["transcription_seconds"]
                cli = MosaicCLI(args.backend, token=token, client=client,
                                output_fn=lambda text: None, write_fn=lambda text: None,
                                input_fn=lambda prompt: "no")  # reject every sensitive action
                cli._new_conversation()
                response_started = time.monotonic()
                answer = cli.send_message(transcript["text"])
                for sentence in sentences(answer):
                    speech = client.post(args.backend + "/voice/synthesize", json={"text": sentence}, headers=headers)
                    speech.raise_for_status()
                    decode_wav(speech.content)
                    if metrics["time_to_first_audio_seconds"] is None:
                        metrics["time_to_first_audio_seconds"] = round(time.monotonic() - response_started, 6)
        metrics["total_response_seconds"] = round(time.monotonic() - started, 6)
    finally:
        stopped.set()
        worker.join(timeout=1)
        metrics["peak_sampled_rss_bytes"] = peak[0]
    print(json.dumps(metrics, sort_keys=True))


if __name__ == "__main__":
    main()
