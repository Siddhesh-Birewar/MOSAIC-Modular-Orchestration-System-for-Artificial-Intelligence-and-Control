# Phase 6 — Local neural voice intelligence (active)

**Status:** implementation published on `feature/phase-6-voice-intelligence`, draft PR #4.
Manual application acceptance pending; **no merge or v0.6.0**. Latest stable milestone
remains v0.4.0 / 30%. Phase 5 dashboard/humanoid is deferred; Phase 7 has not started.
This guide began 2026-11-26 and must be updated with subsequent work/acceptance evidence.

**Evidence:** `d8d3e46`, `ae5cf72`, `fd37407`, `a77185c`, current source/tests,
[VOICE.md](../../VOICE.md), recorded silent experiments and owner-provided preliminary
measurements. Reasons/comparisons are reconstructed explanations unless recorded there.

## 1. Problem

Text interaction needs a local voice path with usable latency. Loading TTS for every
sentence wastes initialization time. Speaking raw streamed text can accidentally expose
reasoning or announce an action before permission/execution succeeds.

The reliability follow-up also addresses wrong-script recognition, older history biasing the response language, hidden worker failure causes and missing first-audio metrics. The existing Base/runtime still fails synthetic Hindi; no accurate-recognition claim is made.

## 2. Why necessary

Natural spoken interaction must combine speech recognition, model reasoning, safe tools,
synthesis and playback without abandoning authentication or privacy. Persistent model
reuse and bounded streaming make resource use controllable on shared CPU/GPU memory.

## 3. Prerequisites

Earlier phases; PCM/WAV, sample rate, RMS/VAD, STT/TTS, phonemes, subprocesses, pipes,
async tasks versus threads, queue backpressure, cancellation, cache state, RTF and latency
clock boundaries. Understand that generated WAV availability is not audible sound onset.

## 4. Technologies

Whisper.cpp multilingual Base; optional sounddevice/PortAudio; existing macOS native TTS;
isolated Python 3.12.16 with MLX Audio 0.6.8, MLX 0.32.5 and Misaki 0.9.4; cached Kokoro assets;
existing FastAPI/HTTPX/Ollama/SQLite. English af_bella, Hindi/Hinglish hf_alpha.
No cloud speech API, frontend package or new model download was introduced.

## 5. Selection rationale

**Recorded:** reuse installed/cached local components. Keep MLX in its working environment
instead of mixing backend dependencies. A persistent child reuses model and initialized
language pipelines; private pipes avoid an extra unauthenticated service. Explicit native
fallback is visible rather than silently changing voice quality. Half-duplex is the
reliable default, with typed tool approval unchanged.

## 6. Alternatives and trade-offs

**Reconstructed:** in-process MLX simplifies IPC but couples Python/dependencies; per-call
children repeatedly pay startup. A separate TTS HTTP server adds a security/lifecycle
boundary. Native TTS needs no neural assets but sounds different. Full-duplex requires
echo/feedback handling not implemented here. Automatic reasoning/model switches can be
unreliable; explicit supported reasoning levels were selected. These are not claims that
all alternatives were benchmarked.

## 7. Architecture and flow

Explicit mic capture → energy VAD → bounded WAV → authenticated transcription → Whisper
child → existing authenticated conversation stream → eligible `speech_segment` → spoken
normalization/language route → private persistent Kokoro worker → WAV → ordered playback.

Tools-on waits for final completed orchestration/persistence before speech. Explicit
tools-off mode emits safe eligible sentence segments while the LLM continues. A text
queue of 3 and audio queue of 2 limit look-ahead; synthesis/playback overlap where permitted.
Raw `token` or hidden thinking events never enter the synthesis path.

## 8. Algorithms and mathematics

- RMS = sqrt(mean(sample²)); energy threshold plus silence bounds utterances. It detects
  energy, not semantic speech. Mono 16 kHz int16 uses about 32 KB/s plus WAV header.
- `Segmenter` tracks fences/inline code/brackets and sentence boundaries, protects
  decimals/abbreviations/URLs, handles Hindi danda, and creates bounded word chunks.
- `normalize_speech` changes only the spoken copy. Code/JSON receive notices; stored
  answer text stays intact. One logical sentence retains its route across chunks.
- RTF = synthesis seconds / audio seconds. Cold/warm pipeline initialization changes
  request latency; queueing and model generation add more than raw synthesis time.
- Worker inference is serialized with bounded admission, stage timeout, at most 3 startup
  attempts per 60 s, idle/memory release and per-model process lock. Available-memory
  admission is a heuristic, not a future memory guarantee.

## 9. Chronological implementation

**Commit facts:** `d8d3e46` added native preview/VAD/APIs/CLI; 78 tests recorded.
`ae5cf72` added persistent neural worker, safe segment streaming, controls, resource
management and regression coverage. Silent HTTP experiments exposed cancellation races;
socket shutdown and remembered cancellation were added. `fd37407` fixed per-sentence
language stability. `a77185c` recorded real benchmarks/acceptance limits. The journal and
error record distinguish these facts from reconstructed explanations of internal steps.
The earlier learning-record addition changed no runtime behavior.

Current verified sequence: trace CLI/API/Whisper language arguments; verify existing model hash/metadata; reproduce script failures; compare CPU/no-flash/greedy/neutral-prompt settings; adopt none without evidence; fix lifecycle/metric bugs; add gates, bounded correction and VAD tests; run two mixed synthesis batches and live response-language probes. No model/dependency replacement or frontend work occurred.

## 10. Important source

- [audio.py](../../../backend/app/voice/audio.py): bounded audio validation/conversion.
- [providers.py](../../../backend/app/voice/providers.py): `WhisperCpp`, `MacOSTTS`,
  `run_local` and speech protocols.
- [neural.py](../../../backend/app/voice/neural.py): `cached_model`, `KokoroWorker._start`,
  `request`, `_idle`, `close`, `VoiceEngine.synthesize`.
- [neural_worker.py](../../../backend/app/voice/neural_worker.py): `validate_request`, `main`;
  one loaded model, offline generation and private protocol.
- [text.py](../../../backend/app/voice/text.py): `normalize_speech`, `language_for`,
  `SpeechSegment`, `Segmenter.feed_segments`.
- [voice API](../../../backend/app/api/voice.py): `_connected`, `cancel`, `warmup`, `synthesize`.
- [intelligence.py](../../../backend/app/api/intelligence.py): `stream_chat` speech eligibility.
- [voice.py](../../../scripts/voice.py): `AudioDevice.record/play`, `VoiceSession._reply/once`.
- [chat.py](../../../scripts/chat.py): `MosaicCLI._voice_command/send_message` and SSE.

New source: [diagnostics.py](../../../backend/app/voice/diagnostics.py), `VoiceDiagnosticError`; [language.py](../../../backend/app/voice/language.py), `script_counts`, `language_issue`, `resolve_language`, `voice_instruction`; [response.py](../../../backend/app/voice/response.py), `repair_response`. New regression file: [test_voice_reliability.py](../../../backend/tests/test_voice_reliability.py).

## 11. Communication and state

CLI uses loopback authenticated HTTP; SSE speech events have ordered sequence numbers,
language and safety mode. `X-Voice-Session` binds provider tasks to a UUID. Cancelled IDs
are remembered for 60 s, at most 512 IDs, so late registration cannot escape cancellation.

Backend → neural Python child uses bounded JSONL stdin/stdout and matching IDs. The child
receives a controlled environment without API tokens, redirects library output away from
the protocol and denies network connections. Audio returns in-memory WAV/base64.
Voice states include idle/listening/transcribing/thinking/speaking/cancelling/error.
Content-free playback/amplitude events support a later client; phoneme/viseme alignment
is explicitly unsupported. No humanoid implementation is present.

## 12. Commands and purpose

Use existing environments. From backend/:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

From root, export trusted `.env` and run the CLI as shown in
[command reference](../COMMAND_REFERENCE.md). `/tts kokoro` warms the worker;
`/voice-status` inspects readiness; `/language auto`, `/speed 1`, `/reasoning low`
choose explicit settings. `/voice-tools off` permits tool-free streaming; `/voice-tools on`
restores action orchestration. `/voice` captures one utterance; `/voice on` repeats;
Ctrl+C interrupts. `/mic` lists devices; `/tts macos` explicitly selects native speech.

Use `/transcript-preview on` for an optional local recognized-text/language display and confirmation, off by default. Hindi/Hinglish both force `-l hi`; preview does not bypass invalid-script rejection. The exact capture overrides and mixed benchmark commands are in [command reference](../COMMAND_REFERENCE.md).

## 13. Errors and solutions

The cached snapshot lacked unrelated files; required local assets are validated without
runtime downloads. BF16 repository name actually had F32 weight metadata; files were
preserved and dtypes exposed. Hindi upstream warnings motivated bounded segments, with
remaining pronunciation limits documented. Cancellation needed own-socket shutdown before
cross-thread response close and a remembered-UUID gate for late synthesis. An idle-task
cancellation race needed cancellation-safe gathering. Full explanations and test pointers:
[error record](../ERRORS_AND_SOLUTIONS.md).

The reliability review found generic handling killed healthy workers on rejected admission, Hinglish used auto, and `setdefault` preserved a null first-audio field. Fixed these without removing memory limits. Wrong-script Base recognition persisted across decoder/backend trials and is rejected before chat; the original intermittent worker failure remains unconfirmed. [Error history](../ERRORS_AND_SOLUTIONS.md) separates proven causes from unknowns.

## 14. Actual experiments

**Recorded silent real component run:** initialization with warm-up 2.677 s; warm short
English/Hindi 0.130/0.171 s; synthetic Whisper first/repeat 0.331/0.229 s. Concurrent 4.7 s audio
chunks generated in 0.596–0.875 s, RTF 0.127–0.186. GPT-OSS 22.45 tokens/s alone vs 14.54
concurrently in short cache-biased samples; system swap increased.

**Warm real HTTP probe:** first token 1.998 s, sentence 2.941 s, generated audio 4.074 s,
chat complete 4.323 s, generation complete 4.945 s. Synthesis overlapped chat; physical
audible timing was not measured. Warm-up-disabled first English took 2.976 s versus
repeat 0.143 s. Silent cancellation joined threads in 0.050 s and subsequent chat succeeded.

Conditions, units, owner-reported preliminary results, memory counters and caveats are
in [benchmark history](../BENCHMARK_HISTORY.md). Concurrent <0.5 s TTS target was missed;
ideal <3 s audible response and sustained acceptance remain unverified.

Current silent repeats each generated 12 mixed segments / 68.3 s in one worker without failure. The final run had fully overlapping first-six TTS times 0.568–0.728 s / RTF 0.1081–0.1364, and English STT 0.330/0.229 s. Later TTS outlasted the short LLM request; this is not 68.3 s of sustained wall-time load. Forced-hi/auto recognition still failed script checks. Live response-layer hi/en/hinglish probes passed after fake Urdu history with no repair/tools. See [full results and failed trials](../BENCHMARK_HISTORY.md).

## 15. Security

Voice routes require auth; clients accept loopback backend URLs. Fixed trusted executable
paths/arguments, no shell, no implicit downloads. Worker request/reply/queue/time bounds
prevent uncontrolled work; only its own child is reaped. No token in worker environment,
prompts, speech or logs. Temporary mic WAVs are private and cleaned; generated speech
stays in memory by default. Swap/abnormal termination may leave traces; cleanup is not
secure erasure. Original conversation text follows existing SQLite persistence.

Tools-on excludes provisional text and speaks deterministic noncompletion notices for
failed/denied actions. App launch success means a launch request was sent, not verified
GUI opening. Spoken commands cannot approve actions; typed per-request consent remains.

Optional preview escapes terminal controls and creates no extra log; scrollback can retain it. Script mismatch stops recognition before chat. Response correction runs once without tools or history writes; already eligible speech is not replayed. Diagnostics contain only fixed categories/stages/numeric data. Alphabet validation cannot prove meaning or rewrite equivalence.

## 16. Testing

**Earlier learning-documentation run:** 116 deterministic tests passed, one optional
integration skipped, one existing Starlette/httpx warning. **Previously executed and
recorded in a77185c:** real cached-model integration: 1 passed, same PID reused offline for
English/Hindi, proper shutdown. It was not rerun for this prose-only update.

[test_neural_voice.py](../../../backend/tests/test_neural_voice.py) covers normalization,
language/segmentation, bounded IPC, reuse/warm-up/queue/restart/idle/memory/fallback,
speech safety, playback ordering/cancellation and late-registration cancellation.
[test_voice.py](../../../backend/tests/test_voice.py) covers audio/providers/API/capture.
Earlier persistence, auth and tool boundary suites remain included. Mocks cannot verify
physical sound or pronunciation; use the [manual checklist](../../VOICE.md).

Current reliability suite: **160 passed, one optional integration skipped**, one existing warning. Separate real cached-model test: **1 passed**. New tests cover safe diagnostic categories, healthy-worker preservation, language forwarding, preview/rejection, history-language override, bounded repair/no action replay, VAD pauses/noise/caps and first-playback metrics. They do not establish physical audio quality.

## 17. Git and milestones

Branch `feature/phase-6-voice-intelligence`; earlier neural-upgrade evidence commit `a77185c`.
[PR #4](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/4)
is open/draft. Commits above are published work-in-progress, not a released phase. No
v0.6.0 tag or merge before owner acceptance. Stable metadata remains 0.4.0. Future changes
must follow the unchanged milestone gates plus learning-document verification.

This follow-up continues from learning commit `5a0a74e` on the same branch/draft PR. Publication is work in progress; no merge, completion tag or roadmap increment is authorized by these tests alone.

## 18. Limitations and outstanding acceptance

Physical mic/playback/continuous use, multilingual listening quality, typed tool scenarios,
interruption across actual devices, fallback/crash/idle recovery and sustained memory/heat
need owner acceptance. Hindi truncation/phonemizer heuristics can still fail. Tools-on
waits longer by design; tool-free speech already played cannot be retracted on a later
failure. No acoustic barge-in, full-duplex, wake word, echo cancellation or aligned mouth
timings. The measured concurrent workload missed one latency goal and increased swap.

The existing verified Base artifact/runtime produces Roman or unsupported-script Hindi even with forced hi. CPU/no-flash/greedy/neutral-prompt trials did not establish a fix. Recognition quality remains a manual acceptance blocker; safe rejection and typed input are the available paths. Two short synthesis batches do not diagnose the earlier worker stop. VAD hangover costs latency, and energy alone still admits sustained background noise.

## 19. Rebuilding exercises

Use a fake synthesizer in a separate scratch project: split incremental text without
breaking decimals/code, preserve one language route per sentence, feed bounded queues
and assert audio ordering. Inject cancellation before registration and during synthesis;
assert nothing stale plays next turn. Build a JSONL echo worker with exact schemas and
size limits before loading any real model. Recompute RTF from the recorded measurements.
Do not download models, change production allowlists or open microphones automatically.

Rebuild the null-metric bug with a dictionary and `setdefault`. Simulate a memory rejection separately from a process crash and a cancelled queued waiter; prove the active worker survives rejected admission. Feed Roman/unsupported-script Hindi to a gate and show no chat write occurs. Add one tool-free output correction and assert one tool execution and one original turn only.

## 20. Educational content

Teach persistent workers, backpressure, Hindi segmentation, safety-delayed speech or
“first WAV is not first audible sound.” Show real numbers with methodology and missed
targets. Explain BF16-name/F32-metadata as a reproducibility lesson. Use synthetic demos
and label Phase 6 as pending acceptance; do not present it as a released voice assistant.

New content ideas: selected language is not detected language; script validity is not meaning; failed experiments prevent unsafe tuning; why a signal does not prove OOM; natural pauses versus endpoint latency; and why correcting an answer must not execute an action twice.
