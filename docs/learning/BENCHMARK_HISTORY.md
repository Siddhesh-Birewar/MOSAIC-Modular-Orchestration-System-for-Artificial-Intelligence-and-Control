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

## Phase 6 reliability investigation — 2026-11-26

**Owner-reported manual evidence:** automatic-language concurrent worker stopped after
11.175 s generated audio; sequential 42.35 s and English-concurrent 54.35 s succeeded;
recovery succeeded. Root cause unconfirmed. Reported STT 0.464 s, warm LLM 19.504 tokens/s,
concurrent RTF 0.108 and playback start 6.235 s; an earlier shorter turn started playback
at 2.614 s but later failed. Sample inputs/clock boundaries are not fully recorded, so
these are not controlled comparisons or stable acceptance guarantees.

**Current silent mixed-language experiment, first run:**
`scripts/benchmark_neural_voice.py --llm --language-check --stress-rounds 4`.
Four cycles of English/Hindi/Hinglish generated 12 segments / 68.3 s of audio with one
worker and no error. Entire generation series took seconds, not 68.3 s wall-time. Worker
init 3.001 s; short warm TTS 0.128/0.170/0.138 s; English synthetic STT 0.313/0.233 s.
Mixed requests 0.272–0.765 s, RTF 0.0565–0.1307. GPT-OSS 26.758 tokens/s alone versus
14.998 during the mixed batch. First-token 7.353 s included 6.393 s load in the first run;
concurrent first-token 1.266 s was warm. Swap 4,852,678,656→5,926,551,552 bytes;
available memory 15,414,689,792→2,109,652,992 bytes. Peak MLX 2,074,070,674 bytes.
These figures do not prove the earlier worker failure is fixed.

**Repeat after adding warm-up cache release:** init 3.482 s; warm TTS
0.130/0.175/0.141 s; English synthetic STT 0.330/0.229 s. Again 12 mixed segments / 68.3 s,
same retained worker, no failure. All-request range 0.277–0.728 s, RTF 0.0563–0.1364.
The first six requests, fully overlapping the short LLM run, took 0.568–0.728 s,
RTF 0.1081–0.1364; later requests outlasted the LLM and must not all be called concurrent.
LLM alone 26.197 tokens/s versus 14.916 with TTS; first token 8.273 s included 7.359 s load,
versus 1.093 s warm during concurrency. Available memory 17,745,215,488→2,583,855,104 bytes;
swap 5,511,512,064→5,477,957,632 bytes. MLX peak 2,074,070,674 bytes; final reported active
MLX 328,955,344 bytes. Short-run cache/order/other-process effects remain confounders.
The different swap direction is not proof of a cache-release improvement.

**Existing Whisper Base investigation:** installed whisper-cli 1.9.6; model JSON reports
multilingual Base, 51865 vocabulary, ftype 1. Local 147,951,465-byte file SHA-256 matches
[the published artifact pointer](https://huggingface.co/ggerganov/whisper.cpp/raw/main/ggml-base.bin):
`60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe`.
No replacement was downloaded. Forced Hindi and auto both returned unsupported-script
text while reporting hi (first run 0.339/0.379 s; repeat 0.324/0.378 s).

Two known synthetic Hindi samples then tested decoder/backend variants:

- Short greeting: default GPU 0.450 s, CPU 0.982 s, no flash 0.670 s, greedy 0.284 s.
  All returned Roman text rather than Devanagari.
- Technical Hindi sentence: default 0.396 s, CPU 1.616 s, no flash 0.498 s, greedy 0.306 s.
  All returned unsupported-script text (37–38 unsupported letters, zero Devanagari).
- An earlier neutral Devanagari prompt trial produced 38 Latin, 4 Devanagari and 2 unsupported
  letters; it still failed validation. A wider beam 10/best-of 10 trial returned a provider
  error; its cause/exit code were not captured. Neither setting was adopted.

These results establish failure on the named synthetic samples, not a word-error-rate
study, a diagnosis of all Base models, or proof that a particular larger model will solve
the issue. Script counts do not measure meaning. No personal microphone sample or raw
recognized text is retained here. New gates reject the failures rather than invent a fix.

**Live response-layer probe:** real local GPT-OSS with an in-memory test database, fake
prior Urdu history and tools off. Explicit hi/en/hinglish each produced 2 eligible segments,
0 repairs, 0 tool calls and exactly one stored turn. Script counts respectively:
120 Devanagari/0 Latin; 154 Latin/0 Devanagari; 99 Devanagari/22 Latin; unsupported 0 for all.
HTTP request wall-times 5.238/2.348/4.321 s, including generation; no audio hardware was used.
This verifies response routing on these samples, not recognition or pronunciation quality.

**Current deterministic and integration evidence:** 160 tests pass with real-model test
skipped by default; the explicit cached-model test passes separately. VAD tests retain
a 1.2 s pause and low-amplitude speech, reject isolated spikes, cap initial wait 10 s and
capture 30 s. A successful playback-start event replaces the initial null metric. These
are simulated-device correctness checks, not physical audible benchmarks. No physical
playback-start value or sustained thermal result was measured in this update.
