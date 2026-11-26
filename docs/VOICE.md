# Local voice intelligence — Phase 6 preview

Phase 5 (dashboard and humanoid) is deferred; original phase numbering is preserved.
Phase 6 is active but not complete. Stable API/package metadata stays at 0.4.0 until
voice verification is accepted; the intended next milestone is v0.6.0, without implying
completion of Phase 5. No frontend files or humanoid designs are part of this change.

## Provider decisions and model evaluation

Whisper.cpp is the initial STT adapter: it is MIT licensed and optimized for Apple Silicon
with Metal/Accelerate support. Upstream lists tiny/base/small at 75/142/466 MiB disk and
approximately 273/388/852 MB runtime memory, respectively. These are upstream estimates,
not measured peak memory on this Mac. Prefer multilingual **base** for the first evaluation;
small is a later quality comparison if needed. Use multilingual weights rather than `.en`
weights for Hindi/Hinglish. Language detection is `auto`; `en` and `hi` explicitly select a
language. Code-switching quality is unverified. No model has been downloaded by MOSAIC.
[Whisper.cpp upstream setup, platform and memory documentation](https://github.com/ggml-org/whisper.cpp)

The adapter invokes an administrator-configured absolute `whisper-cli` path with an
existing local model. It uses 16 kHz mono PCM and the CLI's JSON output, not stdout parsing.
[Whisper.cpp CLI source and flags](https://github.com/ggml-org/whisper.cpp/blob/master/examples/cli/cli.cpp)

Kokoro was evaluated as an optional later TTS provider: its 82M weights are Apache-2.0;
its Python example uses PyTorch, soundfile, Misaki and espeak-ng. Raw FP32 parameter storage
alone is about 328 MB (82M × 4 bytes); actual peak memory and M4 performance have not been
measured here. Upstream lists English and Hindi voices but notes sparse non-English data.
It is not installed or claimed tested in MOSAIC. A future adapter can implement `TTSProvider`.
[Kokoro model card](https://huggingface.co/hexgrad/Kokoro-82M),
[upstream voices and quality caveats](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)

IndicF5 is a multilingual alternative with Hindi among eleven Indian languages. Its model
card specifies MIT licensing but gated access/terms; it needs reference audio and text plus
Transformers/custom model code. Peak memory and macOS ARM64 compatibility are unmeasured
here. It was not selected because it adds dependencies and reference-voice handling.
[IndicF5 model card and terms](https://huggingface.co/ai4bharat/IndicF5)

The initial TTS implementation uses `/usr/bin/say` and **installed** macOS voices. No weights
are redistributed; OS voice use remains subject to Apple's installed software terms. Voice
selection and speed are configurable. English WAV generation was exercised; naturalness,
Hindi and Hinglish pronunciation have not been verified by listening. `/voices` reports
OS locale metadata, not a MOSAIC language-quality guarantee. It does not fabricate alignment.

Optional `sounddevice` uses PortAudio raw streams without NumPy. A universal macOS wheel
and ARM64 CFFI installed successfully in the existing Python 3.14 environment; no microphone
was opened during development. Permissions and device behavior require user testing.
[Raw stream API](https://python-sounddevice.readthedocs.io/en/latest/api/raw-streams.html),
[sounddevice MIT license](https://github.com/spatialaudio/python-sounddevice/blob/master/LICENSE)

## Setup and exact manual commands

From the repository root:

```sh
backend/.venv/bin/python -m pip install -e 'backend[voice]'
```

Install/build Whisper.cpp separately using its upstream instructions if not already
available. A source build uses `cmake -B build` followed by
`cmake --build build -j --config Release` from its own checkout. Keep that checkout and
weights outside MOSAIC. Before downloading weights, approve a specific model/size; no
repository script downloads weights. Set these values in the ignored repository-root `.env`:

```sh
MOSAIC_WHISPER_EXECUTABLE=/absolute/path/to/whisper.cpp/build/bin/whisper-cli
MOSAIC_WHISPER_MODEL=/absolute/path/to/approved/ggml-base.bin
MOSAIC_VOICE_LANGUAGE=auto
MOSAIC_MICROPHONE=
MOSAIC_VAD_THRESHOLD=0.015
MOSAIC_VAD_SILENCE_SECONDS=0.8
MOSAIC_TTS_VOICE=
MOSAIC_TTS_SPEED=1
```

Keep the existing strong `MOSAIC_API_TOKEN` and `MOSAIC_DB_PATH` configuration. Start the
backend in one terminal:

```sh
cd backend
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

In a second terminal, from the repository root:

```sh
set -a
source .env
set +a
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

Inside the CLI:

```text
/voice-status
/mic
/mic 0
/voices
/voice
/voice on
/voice off
```

Choose an actual input index from `/mic`; `0` is an example. `/voice` waits for Enter to
arm one utterance, then records until end-of-speech silence (or 30-second cap). There is
no speech-triggered background recording before activation. `/voice on` explicitly loops
through utterances. Ctrl+C interrupts capture, inference, generation or playback and returns
to text commands; then `/voice off` keeps continuous listening disabled. Text `/exit` closes
the CLI normally. A permission failure returns a safe message; allow the launching terminal
or application microphone permission in macOS Privacy & Security and retry.

`/voices` lists real voice names/locales. To select another voice, set
`MOSAIC_TTS_VOICE` to its exact name and restart the CLI; speed is 0.5–2.0. Set
`MOSAIC_VOICE_LANGUAGE=hi` for forced Hindi STT or `auto` for language detection. These
options enable provider capabilities; they do not establish tested multilingual accuracy.

## Pipeline and interruption semantics

Microphone → energy VAD → authenticated `/voice/transcribe` → existing `/chat/stream` →
authenticated `/voice/synthesize` per sentence → speaker. Existing conversation UUID,
selected model, saved memory retrieval, persistence and tool orchestration are reused.
A voice turn must not parse slash commands or approve an action from spoken text.
Sensitive tool requests still display the existing typed `y/N` prompt. Reject and approve
separate harmless allowlisted requests manually; no actual app was launched in these tests.

Input capture closes before transcription/thinking/speech. This half-duplex policy prevents
self-transcription; headphones are still useful in noisy rooms. Interruption is **Ctrl+C**,
not acoustic barge-in or a wake word. Continuous listening stops on silence-without-speech,
provider errors or cancellation; explicitly activate again after correcting the cause.

Reply text streams immediately but speech begins after the completed reply. Synthesis is
sentence-level rather than waveform streaming. Spoken output is capped at 12,000 characters,
500 per chunk; long code blocks/markup are normalized. No unfinished/failed reply is spoken.
Energy VAD is a configurable RMS threshold with 200 ms pre-roll and silence hangover;
background noise may trigger it. It is not neural VAD or speaker identification.

The `VoiceEvent` sink exposes listening/transcribing/thinking/speaking/idle, speech start/end,
software playback offsets, and measured PCM RMS amplitude. Timing is software timing rather
than calibrated audible onset. Phoneme/viseme fields stay null. No humanoid is implemented.

Raw capture is held in memory and a private provider temporary directory, removed on normal
completion/failure/cancellation. No WAV is persisted in the database. Temporary-file deletion
is not secure erasure and a hard kill can leave temporary files. Conversation text persists
under the existing explicit chat behavior. Speech responses use `Cache-Control: no-store`.

## Benchmarks and acceptance

A local silent native-TTS benchmark generated a valid 3.299-second English WAV. One run of:

```sh
backend/.venv/bin/python scripts/benchmark_voice.py --tts-only
```

reported 1.763 seconds to generated audio, 1.763 seconds total and 64,012,288 bytes sampled
peak RSS for the benchmark process plus children. This excludes system speech daemons,
Ollama and playback latency. The earlier generation-only smoke took 1.55 seconds; these
single runs are setup evidence, not representative quality/latency claims.

To benchmark the complete configured pipeline with a disposable **already existing** mono
16 kHz WAV (this explicitly persists a new test conversation, rejects all tool approvals,
and does not play audio):

```sh
backend/.venv/bin/python scripts/benchmark_voice.py \
  --audio /absolute/path/to/disposable-test.wav \
  --backend http://127.0.0.1:8000 --backend-pid BACKEND_PID
```

Replace `BACKEND_PID` with the running backend PID. RSS is sampled every 20 ms over the
benchmark/backend process trees; it can miss short spikes and excludes independently
running Ollama/system daemons. `transcription_seconds` includes the voice lock wait;
time-to-first-generated-audio includes completed chat plus first sentence synthesis. Total
response latency spans transcription through last synthesis, without speaker playback.
`/voice-status` also shows last interactive transcription, first playback-ready audio, and
total reply timing. Real STT/full-pipeline metrics are pending an installed model and manual
voice input; no model-download permission was assumed.

Before merging/tagging, confirm on the MacBook:

1. Mic selection, permission denial/retry, VAD end-of-speech, and silence timeout.
2. English, Hindi and Hinglish transcription and voice quality separately; report failures.
3. A voice conversation survives restart and retrieves an intentionally saved fictional memory.
4. Tool approval reject/approve and non-allowlisted denial remain enforced.
5. Ctrl+C stops recording/playback promptly and returns to text; no feedback loop in continuous mode.
6. Record STT/first-audio/total latency and memory observations with the intended Ollama model loaded.

Phase 6 remains work in progress until the user confirms these checks. Do not merge or tag.
