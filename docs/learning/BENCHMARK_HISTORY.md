# Benchmark history

Each entry states provenance and conditions. These records were consolidated 2026-11-26.
No new benchmark was run for the documentation-only update. Missing audio/hardware timing
is deliberately left unmeasured. Test runtimes are not application benchmarks.

## Definitions

- Token generation rate = output tokens / evaluation seconds; Ollama durations arrive
  in nanoseconds and are divided by 1,000,000,000. See
  [InferenceMetrics.from_ollama](../../backend/app/models/metrics.py).
- Real-time factor (RTF) = generation seconds / generated audio seconds. RTF below 1
  means faster than playback; it says nothing by itself about startup latency.
- Cold/warm must name what is cold: model process, language pipeline, model residency
  or OS cache. A repeated executable call is not necessarily a resident model.
- First token, complete sentence, generated WAV, device-stream start and physical audible
  onset are separate timestamps. Never substitute one for another.

## Phases 1–4

**Phase 1:** tagged state documents health/model checks and successful live inference;
no latency or throughput measurement is recorded.

**Phase 2 historical live sample:** v0.2.0 `docs/PROJECT_STATE.md` reports GPT-OSS 20B
load 7.62 s, total 10.55 s, input 257 tokens, output 57 tokens, 26.38 tokens/s. This is
one request, not an average, p95 or controlled model comparison. The opt-in
[model benchmark](../../scripts/benchmark_models.py) was explicitly **not run**.

**Phase 3:** deterministic boundaries and live system tool checks are recorded; no
controlled tool latency benchmark is recorded. **Phase 4:** restart correctness is
verified; no database/search performance benchmark is recorded. Do not invent either.

## Phase 6 owner-provided preliminary component samples

Source: the Phase 6 neural-upgrade request. These were manually measured outside the
integrated acceptance workflow; exact prompts/raw traces are not committed here.

- Whisper multilingual Base warm short English: about 0.46–0.52 s.
- Kokoro standalone: load 0.501 s; first cold synthesis 2.114 s; warm first audio
  0.167–0.210 s; mean warm synthesis about 0.189 s; mean RTF about 0.058;
  MLX peak 1385.14 MiB.
- Concurrent component sample: cold first audio 6.694 s; warm first audio
  0.378–0.408 s; mean warm first audio 0.387 s; mean warm synthesis 0.401 s;
  mean RTF 0.136; MLX peak 1160.07 MiB.
- Bella naturalness 9/10 was a subjective owner rating, not an objective audio metric.

The repository label says BF16; later header inspection found F32 tensors. Preserve
that distinction when discussing these measurements. Different inputs/cache conditions
prevent treating the preliminary and integrated numbers as a controlled speedup.

## Phase 6 implementation measurements recorded in a77185c

Target: owner-specified M4 MacBook Air, 24 GB unified memory. Existing neural Python
3.12.16 / MLX Audio 0.6.8 / MLX 0.32.5 / Misaki 0.9.4; cached Kokoro assets, af_bella and
hf_alpha. Local Ollama 0.40.16 with GPT-OSS 20B. Synthetic content, silent generation,
no microphone or physical speaker. Source: [VOICE.md](../VOICE.md).

**Persistent-worker component run:** warm-up enabled, both languages initialized.
Worker init 2.677 s, load-function wall time 0.024 s (lazy/cached work excluded from
that function's interval). Warm English/Hindi/English synthesis 0.130/0.171/0.139 s;
RTF 0.059–0.067. Same worker PID reused. Synthetic Whisper first/repeat 0.331/0.229 s;
each call still starts whisper-cli.

**Concurrent short experiment:** six 4.7-second audio segments took
0.875/0.643/0.619/0.625/0.596/0.627 s to generate; RTF 0.127–0.186. GPT-OSS alone
22.45 tokens/s versus 14.54 concurrently. Cold first token 13.522 s included
12.325 s model load; concurrent warm first token 1.098 s. Order/cache bias means this
does not prove a concurrent latency benefit or a sustained throughput ratio.

System available memory: 13,685,293,056 → 3,487,318,016 bytes. Swap used:
5,131,927,552 → 6,574,505,984 bytes. Concurrent MLX peak: 1,701,601,240 bytes.
Other processes influence system counters. RSS, MLX allocation and system pressure
are distinct; do not add them or interpret one as total unified memory use.

**Separate warm tool-free real HTTP probe:** first answer token 1.998 s, first complete
segment 2.941 s, first generated audio 4.074 s, chat complete 4.323 s, all audio generated
4.945 s. Two audio segments; synthesis overlapped generation. Actual audible latency
was unmeasured; 4.074 s generated audio does not establish the ideal <3 s audible target.

**Warm-up disabled:** init 0.587 s; load-function 0.140 s; first English 2.976 s;
first Hindi pipeline 0.468 s; repeated English 0.143 s. Lower initialization moves work
into the first request. It does not remove that work.

**Cancellation/recovery:** injected KeyboardInterrupt at fake playback entry in a real
HTTP pipeline. After fixes, threads joined in 0.050 s, none remained, later chat succeeded.
This tests transport recovery, not acoustic interruption or sound-device response.

## Targets and next evidence

Warm short STT <1 s and standalone TTS <0.5 s were met in the named samples.
Concurrent TTS <0.5 s was not met; concurrent RTF <0.2 was met for these short samples.
Actual first-audible timing, sustained swap/thermal behavior, continuous use and physical
interruption still require manual acceptance. No p95, quality score or long-run stability
result is claimed.

Reproduction commands and resource effects: [command reference](COMMAND_REFERENCE.md).
For future runs record revision, hardware/runtime/model/dtype, input length/language,
warm-up/cache state, load conditions, clock boundaries, units, sample count and failures.
Use synthetic content; retain aggregate results only. Do not overwrite older results.
