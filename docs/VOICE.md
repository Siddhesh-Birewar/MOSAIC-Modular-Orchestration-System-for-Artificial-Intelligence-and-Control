# Phase 6 — Neural voice intelligence (draft)

Phase 5 dashboard/humanoid remains deferred; no frontend files are changed. Continue on
`feature/phase-6-voice-intelligence` / draft PR #4. Stable milestone remains v0.4.0 (30%).
Do not merge, create v0.6.0, or begin Phase 7 before user acceptance.

## Verified runtime and offline assets

The existing `/opt/anaconda3/envs/mosaic-voice/bin/python` reports Python 3.12.16,
mlx-audio 0.6.8, mlx 0.32.5 and misaki 0.9.4. The backend retains its separate existing
virtual environment. No packages were reinstalled and no assets were downloaded for this
upgrade. Whisper is `/opt/homebrew/bin/whisper-cli` with the existing multilingual Base at
`~/AI-Models/Whisper/ggml-base.bin`.

Kokoro assets resolve from the local Hugging Face cache for
`mlx-community/Kokoro-82M-bf16`, currently revision
`a71e4d38b236d968966a2002c4c895dbd12b1c3c`. An explicit `MOSAIC_KOKORO_MODEL` directory pins
another local snapshot. Required files are config.json, kokoro-v1_0.safetensors and the
selected af_bella/hf_alpha voice files. The cache lacks some irrelevant repository files;
a whole-repository `snapshot_download(local_files_only=True)` reports an incomplete snapshot.
MOSAIC checks only the required local files and never tries to complete that download.

**Precision caveat:** despite the repository's BF16 name, the cached weight header declares
548 F32 tensors. Files are preserved without conversion. Worker status exposes loaded
parameter dtypes; a repository name does not establish actual runtime precision. Memory
and performance results below apply to the files actually loaded.

Kokoro model weights are Apache-2.0; mlx-audio integration uses the existing installed
package. Whisper.cpp and sounddevice are MIT licensed. macOS fallback uses installed system
voices subject to Apple's installed software terms. No weights/voices are redistributed.
[Model card](https://huggingface.co/mlx-community/Kokoro-82M-bf16),
[Whisper.cpp](https://github.com/ggml-org/whisper.cpp),
[Sounddevice raw streams](https://python-sounddevice.readthedocs.io/en/latest/api/raw-streams.html)

## Persistent worker architecture

FastAPI owns one lazily started Kokoro subprocess using the neural interpreter. The backend
never imports MLX or installs it into its environment. The child loads one model instance
and reuses the installed model's cached English/Hindi pipelines. English af_bella / code a
and Hindi/Hinglish hf_alpha / code h are the supported neural voice choices. Voice and speed
can be selected per synthesis request; neural input is bounded to 500 normalized characters,
with Hindi/Hinglish capped at 160. CLI speech segments use a 160-character word boundary.

Private inherited pipes carry newline-delimited JSON; there is no neural network listener.
Protocol version 1 readiness includes warmed state, initialization/load timings, MLX peak
allocation and dtypes. Requests contain exactly integer id, text, voice and speed (8 KiB cap).
Replies contain the matching id, base64 mono PCM WAV, sample-rate/latency/allocation metadata,
or a generic error (3 MB IPC cap; 2 MB validated WAV cap). Workers never echo private text.
Third-party Python and native stdout/stderr are discarded; only protocol messages use the
private duplicated stdout pipe. Credentials are excluded from the child's environment.

Warm-up runs both language pipelines before ready when enabled. Queue capacity defaults to
three active/waiting requests; only one synthesis runs at a time. Overflow fails rather than
growing without bound. Timeout defaults to 60 seconds for queue acquisition/startup/reply
stages, not a promise of a 60-second total cold request. Cancellation kills and reaps an
in-flight MLX worker because its synchronous generation cannot be safely interrupted in a
Python thread. Later requests may restart it; normal sentences never spawn new workers.
There are at most three startup attempts per 60 seconds. A per-user/model OS file lock
prevents duplicate MOSAIC workers. No unrelated process is killed or unloaded.

Idle retention defaults to 180 seconds. Idle memory pressure or timeout releases the child;
loading/synthesis admission requires at least 1024 MiB system available memory by default.
This is a conservative admission signal, not a complete unified-memory pressure model.
Ollama retention remains controlled by existing `MOSAIC_KEEP_ALIVE`; do not keep every model
loaded. Run one backend worker. Shutdown cancels the idle monitor and reaps the voice child.

The neural worker enforces HF/Transformers offline flags and rejects network connects.
Missing weights, voice packs, phonemizer/spaCy assets or interpreter dependencies fail safely.
No implicit download or network fallback is permitted. Native macOS fallback is disabled by
default; enable it explicitly with MOSAIC_TTS_FALLBACK=1. Fallback appears in status,
X-TTS-Provider/X-TTS-Fallback headers and CLI output. It does not promise the neural voice's
pronunciation or naturalness. `/tts macos` explicitly selects the native provider.

## Safe streaming and language behavior

Voice reuses `/chat/stream`, UUID conversations, saved memory, unchanged text history,
registered tools and typed approvals. The spoken representation is separate: normalization
handles code/JSON notices, headings/emphasis, bullets/lists, links, emoji, percentages,
mathematical operators, abbreviations, dates/numbers and Devanagari punctuation. Numbers
and dates are not reinterpreted into guessed calendar meanings. Original text is not edited.
Incremental segmentation holds fences, structured blobs, decimals, abbreviations and partial
sentences until an appropriate boundary; long speech is split at bounded word boundaries.

**Tools on (default):** all speech waits for completed orchestration. Intermediate model
prefaces, hidden reasoning, raw tool arguments and results never become speech events. Only
the final model iteration is eligible. A launcher success is described as a submitted request,
not proof that a GUI window opened. Any denied/rejected/failed tool causes a deterministic
spoken noncompletion notice; original detailed text remains in the chat transcript.

**Tools off (explicit `/voice-tools off`):** backend sends no tool schemas and rejects
unexpected structured calls. It emits ordered `speech_segment` events as meaningful answer
segments arrive, permitting synthesis during continued model generation. Event safety is
`tool_free`; this is eligibility for playback, not a completed SQLite turn. A failed/aborted
turn does not commit unfinished history, and pending speech is cancelled. Already played
sentences cannot be retracted. This mode cannot perform actions or approvals. Like any LLM
answer, factual accuracy still requires judgment; do not treat fluent speech as verification.

Clients consume only these speech events, never raw text tokens or reasoning for playback.
Each event has a consecutive sequence number. Tool-enabled safety is
`completed_orchestration`. Text and audio queues are bounded at three and two segments,
respectively; backpressure limits look-ahead and playback stays ordered. Generation,
synthesis and main-thread playback overlap only where that safety contract allows.

Automatic routing considers response script first, then explicit language preference and
Roman Hindi markers. It does not rely solely on input language; a user can request an answer
in a different language. All bounded chunks of one logical sentence retain its language route so an English-only
chunk within a Hindi sentence does not switch voices. This is heuristic routing, not
perfect language detection. Hindi long-text phonemizer truncation/mixed-language switching
and word-count warnings remain upstream limitations; short segmentation mitigates them
without guaranteeing pronunciation or alignment. User-reported initial Bella naturalness
was 9/10 and Hindi/Hinglish samples were liked; integrated acceptance is still pending.

Ollama 0.40.16 on this machine reports GPT-OSS thinking values low/medium/high via `/api/show`.
MOSAIC validates requested reasoning levels against that response before sending `think`.
`default` omits the parameter; low/medium/high are explicit choices. Qwen may advertise
different controls and unsupported levels are rejected. No guessed adaptive classifier or
silent switch from GPT-OSS 20B is used. Voice prompts request concise natural answers,
minimal formatting and longer teaching explanations when requested without removing safety.
[Ollama model-specific thinking controls](https://docs.ollama.com/capabilities/thinking)

## Commands and exact startup

Preserve your actual `.env`; add reviewed values using `.env.example` as a guide:

```sh
MOSAIC_TTS_PROVIDER=kokoro
MOSAIC_NEURAL_PYTHON=/opt/anaconda3/envs/mosaic-voice/bin/python
MOSAIC_KOKORO_MODEL=
MOSAIC_NEURAL_WARMUP=1
MOSAIC_NEURAL_TIMEOUT=60
MOSAIC_NEURAL_IDLE_SECONDS=180
MOSAIC_NEURAL_QUEUE_SIZE=3
MOSAIC_NEURAL_MIN_AVAILABLE_MB=1024
MOSAIC_TTS_FALLBACK=0
MOSAIC_WHISPER_EXECUTABLE=/opt/homebrew/bin/whisper-cli
MOSAIC_WHISPER_MODEL="${HOME}/AI-Models/Whisper/ggml-base.bin"
MOSAIC_VOICE_LANGUAGE=auto
MOSAIC_VOICE_REASONING=default
MOSAIC_VOICE_TOOLS=1
MOSAIC_TTS_SPEED=1
```

Keep existing MOSAIC_API_TOKEN, database, allowed-root and application settings private.
Start from backend/:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

Second terminal, from repository root:

```sh
set -a
source .env
set +a
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

Supported voice commands (all text commands remain available):

```text
/tts kokoro
/voice-status
/voices
/mic
/mic INDEX
/language auto
/language en
/language hi
/language hinglish
/speed 1.0
/reasoning default
/reasoning low
/reasoning medium
/reasoning high
/voice-tools off
/voice
/voice on
/voice off
/tts macos
/metrics
```

Replace INDEX with an actual microphone index. `/tts kokoro` initializes/warms the worker.
Commands without arguments inspect current settings. `MOSAIC_TTS_VOICE` may select either
supported neural voice (af_bella/hf_alpha); `/tts` resets an explicit voice so routing applies.
Status reports selected CLI configuration, worker readiness/warmth, queue/error information,
last fallback/provider, timing capabilities and metrics. English/Hindi/Hinglish pronunciation
is not guaranteed by locale metadata.

`/voice` waits for Enter, captures one VAD-bounded utterance, and stops on silence. `/voice on`
explicitly enables repeated conversation. Capture closes before transcription/thinking/
playback (half-duplex). Ctrl+C cancels queued audio/synthesis and the active HTTP stream;
`/voice off` keeps repeated listening disabled after return to text. States include idle,
listening, transcribing, thinking, speaking, cancelling and recoverable error. If an HTTP
transport has not released within the bounded thread join, the CLI reports it and refuses
another voice turn until it releases. There is no wake word, echo cancellation or acoustic
barge-in. Allow the launching terminal/application microphone permission in macOS Settings.

Authenticated API additions: POST /voice/warmup, POST /voice/cancel/{session_uuid}; synthesis
accepts provider/language/detected_language plus existing text/voice/speed. X-Voice-Session
binds cancellation to a UUID's pending provider operations. Chat accepts voice_mode,
voice_tools, voice_language and reasoning; old clients/contracts retain their defaults.

## Events, privacy and diagnostics

VoiceEvent remains provider-independent: voice state, speech start/end, playback start/end,
submitted-PCM position/RMS amplitude and cancellation. Playback start is emitted after the
actual output stream starts; timing is software/device-stream timing, **not measured physical
audible onset**. Event offsets are not phoneme/viseme alignment; these fields remain null.
No humanoid or frontend is built. No event includes transcript text or credentials.

Only speech text and ordinary conversation history use existing SQLite behavior. No raw mic
or generated speech is persisted by default. Whisper uses a private temporary WAV directory
removed on success/error/cancellation. Worker speech WAVs stay in memory/IPC. Hard process
termination, OS swap/caches and filesystem recovery can leave traces; deletion is not secure
erasure. Logs never include audio/text/model warnings; .env/tokens/weights are not committed.

Neural RSS and MLX allocation are distinct metrics; MLX peak does not equal total system
memory and RSS may omit separately accounted GPU/shared allocations. Watch macOS Activity
Monitor memory pressure and swap alongside application status. A missing cached dependency
should be fixed deliberately in the neural environment; do not enable runtime downloads.

## Measured benchmarks (synthetic, silent, no microphone/playback)

On this machine during implementation:

- Worker initialization with both language warm-ups: 2.677 s; load-function wall time 0.024 s.
- Short warm English/Hindi synthesis: 0.130/0.171/0.139 s; RTF 0.059–0.067.
- Synthetic Whisper Base transcription: first 0.331 s, repeat 0.229 s. Each call still launches
  whisper-cli; the repeat benefits from OS/device caches, not a resident Whisper model.
- Six concurrent 4.7-second audio segments: 0.596–0.875 s generation, RTF 0.127–0.186. The <0.5 s synthesis target
  was not met under this load, while RTF <0.2 was met for these short samples.
- GPT-OSS throughput: 22.45 tokens/s alone vs 14.54 with TTS. First answer token 13.522 s in
  the cold-LLM run (12.325 s model load), 1.098 s in the concurrent warm-LLM run. These are
  order/cache-biased single samples; they do not prove a latency benefit or sustained rate.
- Available memory fell from 13,685,293,056 to 3,487,318,016 bytes; system swap used increased
  from 5,131,927,552 to 6,574,505,984 bytes during the component experiment. Other processes
  also influence system counters. Concurrent MLX peak reached 1,701,601,240 bytes.
- A separate warm real HTTP tool-free probe measured first answer token 1.998 s, first
  complete segment 2.941 s, first generated audio 4.074 s, chat complete 4.323 s and total
  generation 4.945 s (two audio segments). Synthesis overlapped generation but the ideal
  three-second first-audible target is not met by that generated-audio measurement.
- With warm-up disabled: worker init 0.587 s, first English synthesis 2.976 s, first Hindi
  pipeline 0.468 s, repeated English 0.143 s. This demonstrates why explicit warm-up matters.
- Actual playback/audible end-to-end latency remains unmeasured. No value is fabricated.

Reproduce component and concurrent probes (no personal content is stored):

```sh
backend/.venv/bin/python scripts/benchmark_neural_voice.py --llm
backend/.venv/bin/python scripts/benchmark_neural_voice.py --cold-start --skip-stt
```

The script uses the configured existing neural interpreter/cache, synthetic local speech,
Whisper Base, and optional direct local GPT-OSS calls. It prints numeric metrics only,
including system before/after memory/swap, worker RSS and MLX allocation. It does not measure
actual audio hardware. `scripts/benchmark_voice.py --tts-only` remains the native baseline;
use the interactive voice metrics for the application pipeline. Do not interpret short
experiments as a sustained thermal/memory-pressure acceptance test.

## Automated checks

The complete deterministic suite reports 116 passed, with the real-model test skipped by
default and one existing Starlette/httpx warning. The explicit cached-model integration test
was separately executed and passed, verifying model reuse, readiness/warm-up, parameter dtype
reporting, offline English/Hindi generation and shutdown. Both Python environments compiled;
Git whitespace and tracked credential/artifact checks are part of publication review.

```sh
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q
MOSAIC_TEST_NEURAL=1 backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q -m integration
```

## Manual acceptance checklist

1. `/tts kokoro` then `/voice-status`: ready+warmed; repeated calls reuse a PID until idle.
2. Test short English, Hindi, Hinglish and English technical terms in Hindi; report dropped
   words, long-text truncation or bad pronunciation. Verify response-language changes.
3. `/voice-tools off`, `/reasoning low`: test safe conversational speech starting before the
   displayed reply finishes. Inspect first-token/segment/audio/playback-ready timing.
4. `/voice-tools on`: reject then separately approve a harmless allowlisted action. No
   provisional success may be spoken; failed actions get a noncompletion notice. Verify
   non-allowlisted apps remain denied and saved memory/conversations survive restart.
5. Ctrl+C during listening, LLM thinking, synthesis and playback: stop promptly and recover
   to text; no stale audio may play during the next turn. Test explicit continuous mode and
   permission denial without microphone feedback. Phoneme/viseme support remains absent.
6. Test fallback explicitly and confirm visible labeling; test missing model/interpreter,
   worker crash, idle release and restart without downloading or killing unrelated jobs.
7. Run sustained GPT-OSS+TTS conversation while watching memory pressure, swap and heat;
   record actual audible first response latency. Targets are engineering goals, not claims.

A silent real-HTTP cancellation probe injected KeyboardInterrupt at playback entry. After
fixing cross-thread socket shutdown and cancellation-before-registration, both voice threads
joined in 0.050 s and a subsequent chat completed successfully. This tests transport/provider
recovery, not physical microphone/speaker latency. UUID cancellation is remembered for 60
seconds (bounded to 512 sessions) so a late synthesis request cannot escape an earlier cancel.

No merge or v0.6.0 tag until these application-level checks are accepted by the user.
