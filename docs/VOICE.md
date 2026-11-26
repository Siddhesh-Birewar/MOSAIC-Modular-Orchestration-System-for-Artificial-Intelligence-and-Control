# Phase 6 — Neural voice intelligence (draft)

For a beginner-friendly implementation walkthrough, source/function map, rebuilding
exercises and evidence labels, see the [Phase 6 learning guide](learning/phases/PHASE_06_VOICE.md).
The shared [benchmark history](learning/BENCHMARK_HISTORY.md) separates owner-reported
component results from implementation measurements and pending audible/sustained checks.

Phase 5 dashboard/humanoid remains deferred; no frontend files are changed. Continue on
`feature/phase-6-voice-intelligence` / draft PR #4. Stable milestone remains v0.4.0 (30%).
Do not merge, create v0.6.0, or begin Phase 7 before user acceptance.

## Reliability and language investigation — 2026-11-26

The owner reported a worker stop after 11.175 s of generated audio in an automatic-language
concurrent turn, but successful sequential 42.35 s and English-concurrent 54.35 s turns.
Recovery succeeded. **The cause of that particular stop remains unconfirmed.** Audio
duration alone cannot identify a timeout, memory rejection or process crash.

Worker status now retains a content-free `last_diagnostic` with category/stage and, when
known, numeric exit code or available/required bytes. Categories include `memory_limit`,
`worker_exit`, `timeout`, `invalid_ipc`, `synthesis_failure`, `audio_limit`, `cancelled`,
`queue_full`, `unavailable` and `restart_limit`. Synthesis/warm-up failures return safe
503 detail plus diagnostic metadata and `X-Voice-Error-Category`. Cancellation remains 409.
`last_stop` distinguishes deliberate idle/memory/cancellation cleanup from observed exit.
Negative exit codes identify signals, **not proof of OOM**. Historical diagnostics may
remain after recovery; current `ready`, `error` and `memory_admitted` describe current state.
No transcript, raw audio, exception string or request contents enter these diagnostics.

Review found a concrete lifecycle issue: any admission failure previously stopped the
worker and hid the cause. Low-memory admission now still rejects synthesis, but does not
kill a healthy idle worker; a waiting queue timeout cannot kill somebody else's active
request. Idle pressure release still applies. Startup budgets count actual attempts,
not rejected admission. The worker clears unused MLX allocator cache after warm-up and
requests, retaining live model/pipeline parameters. PCM accumulation is bounded as parts
arrive. These changes do not establish the cause of the owner's earlier failure or remove
the 1024 MiB default memory floor.

### Recognition and response language

`/language hi` reaches `POST /voice/transcribe?language=hi` and Whisper's fixed `-l hi`.
Hinglish now also uses `-l hi` rather than auto. No translation flag is supplied. Endpoint
metadata identifies `requested_language`, `language_source` and script validation. For a
forced language, Whisper's reported language is **selected**, not independent detection.

The installed Whisper.cpp is 1.9.6. JSON metadata identifies multilingual Base, vocabulary
51865. The 147,951,465-byte model's SHA-256 matches the published local-model artifact:
`60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe`.
[Published model pointer](https://huggingface.co/ggerganov/whisper.cpp/raw/main/ggml-base.bin),
[Whisper.cpp 1.9.6 CLI source](https://github.com/ggml-org/whisper.cpp/blob/v1.9.6/examples/cli/cli.cpp).

Silent synthetic Hindi tests reproduced Roman Hindi or unsupported-script output even
with `-l hi`. CPU, disabled flash attention and greedy decoding did not fix the samples.
A neutral Devanagari prompt still produced mixed unsupported output; a wider-beam trial
failed with a provider error whose cause was not established. These experimental settings
were **not adopted**. No model was replaced/downloaded and no dependency reinstalled.
The existing Base/runtime configuration remains unreliable for Hindi recognition.

The CLI now rejects unsupported-script transcripts, unsupported reported languages and
explicit Hindi/Hinglish transcripts lacking Devanagari before sending a chat turn. It
asks the user to re-record or type; it never transliterates, translates or invents the
intended words. The API still returns recognized text with `validation.accepted=false`
for clients that need to inspect it; clients must honor that metadata. Script checks
detect alphabets, not semantic accuracy, and a superficially valid transcript can be wrong.

`/transcript-preview on` optionally displays recognized text and language/source locally
and asks `Use this transcription? [y/N]`. Default is off (`MOSAIC_TRANSCRIPT_PREVIEW=0`).
Terminal controls are escaped. Preview creates no additional persistent log, but terminal
scrollback/screen recording can retain displayed text. Accepted turns still use normal
SQLite conversation persistence. Preview does not bypass script rejection.

Voice response instructions resolve the current setting independently of older history:
English uses natural English; Hindi uses Devanagari; Hinglish uses conversational
Devanagari Hindi mixed with English technical terms. Auto infers a supported target from
the current message using explicit language requests/script/limited Roman-Hindi markers.
Unsupported scripts are blocked before Kokoro both in the parent provider and worker.

Valid tool-free speech continues streaming. On a response-language mismatch, the unspoken
tail is withheld and one text-only rewrite is allowed, with no tools, at most 30 s and
within the existing orchestration budget. The complete rewrite is checked before speech.
Already eligible sentences are not replayed; tools and approvals are never retried. A
failed rewrite produces a fixed selected-language notice. A `voice_warning` makes the
correction visible. Original chat text stays unchanged and exactly one original turn is
stored; the correction adds no conversation messages. Deterministic denied/launch-request
notices are localized. Alphabet checks and prompts do not guarantee fluent language or
semantic equivalence of an LLM rewrite; inspect the original text when uncertain.

### VAD and metric boundaries

New defaults follow the owner's successful trial: threshold 0.010 and silence 2.0 s. Three
consecutive above-threshold 20 ms frames activate capture, reducing isolated-click starts.
Pre-roll retains onset; a 1.2 s natural pause is preserved in deterministic tests. Initial
waiting is bounded at 10 s and total capture at 30 s. Only 200 ms of trailing silence is sent
to Whisper; the full endpoint wait still affects interaction latency. Constant background
noise can still activate energy VAD; it is not a learned speech classifier. Tune per mic.
The actual `.env` is unchanged and existing overrides continue to take priority.

`time_to_first_audio_seconds` previously stayed null because `setdefault` did not replace
the initial null. It now aliases the first **device-stream playback_started** timestamp,
populated only after a successful output-stream start. It is not physical audible onset.
All following interaction offsets use the last above-threshold VAD frame when available:

- `endpoint_wait_seconds`: capture return minus last active frame; approximate software timing.
- `first_answer_token_seconds`: first visible answer token, before speech-language eligibility.
- `first_safe_token_seconds` (legacy name) and `first_segment_seconds`: first eligible speech event.
- `first_generated_audio_seconds`: first validated WAV returned by synthesis.
- `first_audio_ready_seconds`: first audio dequeued for playback.
- `playback_started_seconds` / `time_to_first_audio_seconds`: device output stream started.
- `capture_completed_to_playback_seconds`: comparable post-capture clock for older samples.
- `voice_language_repair_seconds` in LLM metrics: correction latency; backend total includes it.

These clocks differ from older post-capture-only offsets. A failed device start leaves the
playback metric null; a later failure preserves an earlier successful start. Concise
first-sentence instructions reduce avoidable segmentation wait; complete sentence/code
boundaries are retained rather than aggressively speaking incomplete or unsafe clauses.

Current component measurements and failed experiments are preserved in
[BENCHMARK_HISTORY.md](learning/BENCHMARK_HISTORY.md). A short silent mixed batch succeeded,
but Hindi recognition quality and physical/sustained acceptance remain blockers.

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
or a fixed diagnostic category (3 MB IPC cap; 2 MB validated WAV cap). Workers never echo private text.
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
MOSAIC_VAD_THRESHOLD=0.010
MOSAIC_VAD_SILENCE_SECONDS=2.0
MOSAIC_TRANSCRIPT_PREVIEW=0
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
/transcript-preview on
/transcript-preview off
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

The reliability iteration's complete deterministic suite reports 160 passed, with the real-model test skipped by
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

## Exact reliability retest sequence

Keep the backend startup command above. In a second terminal from the repository root:

```sh
set -a
source .env
set +a
export MOSAIC_VAD_THRESHOLD=0.010
export MOSAIC_VAD_SILENCE_SECONDS=2.0
export MOSAIC_TRANSCRIPT_PREVIEW=0
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

These exports affect the CLI only and do not edit `.env`. In the CLI enter one command
per line:

```text
/tts kokoro
/voice-status
/reasoning low
/voice-tools off
/transcript-preview on
/language en
/voice
/language hi
/voice
/language hinglish
/voice
/language auto
/voice
/voice-status
```

Use disposable questions, inspect/confirm each valid preview and reject inaccurate words.
Wrong-script Hindi must stop before chat; report it as recognition failure, not a successful
multilingual turn. Pause naturally within speech and confirm capture does not cut off at
the old 0.8 s threshold. Inspect populated playback metrics after successful physical output.
If a worker stops, inspect only diagnostic category/stage/exit code, memory and stop reason;
then retry `/tts kokoro` and a fresh harmless turn. Do not infer the cause from duration.

Restore `/voice-tools on` for separate typed-approval/rejection checks. Test Ctrl+C during
all stages, then a fresh turn with no stale audio. Disable preview with
`/transcript-preview off`. Repeated/sustained and hardware checks still need owner acceptance.

Optional silent existing-model experiments (no microphone/speaker or persistent chats):

```sh
backend/.venv/bin/python scripts/benchmark_neural_voice.py --llm --language-check --stress-rounds 4
```

This synthesizes 12 mixed-language segments alongside one short LLM request, with overlap
only while that request is running. It prints script counts, not transcript contents.
68.3 s of generated audio is not 68.3 s of wall-time load or a physical playback test.
