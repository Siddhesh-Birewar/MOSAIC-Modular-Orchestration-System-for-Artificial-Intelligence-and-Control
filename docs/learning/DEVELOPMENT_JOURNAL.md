# Development journal

Entries before 2026-11-26 are reconstructed from Git and recorded verification, not
contemporaneous notes. Commit dates establish order between commits, not the exact
sequence of edits inside a commit. No private conversation text is reproduced here.

## 2026-11-24 — Phases 1 and 2 (historical)

- `a79644c` introduced the foundation; v0.1.0 records 10 tests and user-confirmed live
  GPT-OSS inference. An earlier HTTP 500 remained unexplained.
- `58bf95f` introduced identity, in-memory conversations, SSE, model management and metrics;
  v0.2.0 records 22 tests and one live sample. The comparison benchmark was not run.
- [PR #1](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/1)
  merged both phases as `e31b51e`. Tags point to their feature commits.

## 2026-11-24 — Phase 3 (historical)

- `eda3d14` added safe tools/CLI; `687feb0` fixed streamed call retention and added boundary
  verification. Tagged project state records 42 tests, compile/diff checks and user-confirmed
  approvals/rejections. [PR #2](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/2)
  merged as `459ae9c`; annotated v0.3.0 points there.

## 2026-11-24 — Phase 4 (historical)

- `93c7807` added SQLite persistence; `0f5f961` hardened privacy and conversation reset races.
- Closeout recorded 53 tests and owner-confirmed restart persistence/authentication.
  [PR #3](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/3)
  merged as `fd37903`; v0.4.0 marks 30%. Details are in the phase guide.

## 2026-11-26 — Phase 6 (historical implementation evidence)

- `d8d3e46` added local voice preview; 78 tests were recorded. Phase 5 was deferred.
- `ae5cf72` added the persistent neural worker and safe streaming pipeline; `fd37407`
  preserved one language route across bounded chunks of a mixed sentence.
- `a77185c` recorded benchmarks and acceptance limits: 116 deterministic tests and one
  separate real-model test passed. Silent experiments exposed/fixed transport cancellation
  and cancellation-before-registration races. See [error history](ERRORS_AND_SOLUTIONS.md).
- PR #4 is draft. Generated-audio timing and sustained resource behavior do not establish
  physical audible latency or full application acceptance.

## 2026-11-26 — Learning records (current update)

- Inspected tagged project states, commit history, current source/tests and PR #1–4 metadata.
  Reconstructed Phases 1–4 and documented active Phase 6 with explicit evidence labels.
- Added permanent AGENTS.md learning requirements and learning verification to the existing
  documentation step. No milestone gate was removed.
- Reran the complete deterministic suite: **116 passed, 1 optional integration skipped**,
  one existing Starlette/httpx warning. Backend/scripts and neural-worker compile checks
  and `git diff --check` passed. All 15 learning documents were checked: 5 phase guides
  each cover 20 subjects; 147 local links across the learning guides and linked entry
  documents resolved; named regression-test references and 35 linked code-symbol references
  exist. Tracked credential-pattern/artifact and learning private-path scans passed;
  manual review excluded private verification content. No new performance measurement
  is claimed.
- No runtime or frontend change was needed for this documentation addition. Phase 6 remains
  ready for the manual checklist in [VOICE.md](../VOICE.md), not complete. Continue recording
  implementation changes, failed checks and accepted manual results here as they occur.


## 2026-11-26 — Voice reliability follow-up (current verification)

- Started from clean synchronized `5a0a74e` on the same Phase 6 branch/draft PR #4.
  Read policy, project state, voice guide, providers, worker, streaming and tests.
- Traced hi to Whisper's `-l hi`; Hinglish incorrectly used auto and now uses hi.
  Verified multilingual Base metadata/checksum. Synthetic Hindi still failed script checks;
  CPU/no-flash/greedy and a neutral prompt did not establish a fix. A wider-beam trial
  failed without a diagnosed cause. Adopted none of these tunings; no model was downloaded.
- Added rejection before chat plus disabled-by-default local preview/confirmation rather
  than silently changing recognized meaning. Hindi accuracy remains an acceptance blocker.
- Found generic exception handling hid worker causes and stopped healthy workers after
  rejected admission. Added safe categories/stages/numeric counters, retained-worker
  protection on admission/queued timeout and bounded PCM/cache cleanup. Kept memory limits.
  The owner's intermittent failure remains unconfirmed.
- Added current-turn language instructions and one bounded tools-disabled rewrite of the
  unspoken tail. Tests prove actions/history are not repeated. Live hi/en/hinglish after
  fake Urdu history each produced two correct-script segments without repair/tool calls.
- Adopted the owner's VAD 0.010 / 2.0 s defaults with sustained onset, bounded waits and
  trailing-silence trimming. Actual `.env` unchanged. Fixed null first-audio metrics and
  separated VAD-end/capture/visible-token/eligible-speech/generated-audio/playback clocks.
- Two silent mixed batches each generated 12 segments / 68.3 s audio in seconds of wall
  time, with one worker and no failure. Only the beginning overlaps the short LLM request.
  [Benchmark history](BENCHMARK_HISTORY.md) preserves both runs, failed trials and limits.
- Two initial test failures were test-assumption errors: a fake child marked dead before
  admission correctly restarted, and VAD onset pre-roll made expected duration 1.96 s,
  rather than 1.8 s. Fixed the fixture to exit during a request and corrected the duration;
  neither establishes a cause for the owner's crash.
- Final suite: 160 passed, one optional integration skipped; separate real cached-model
  integration: 1 passed. One existing Starlette/httpx warning remains. No frontend,
  Phase 7, dependency installation, release merge or milestone tag was introduced.
- Positive memory-floor validation prevents zero/negative configuration from disabling
  admission. Shutdown reaps a child that exits between the return-code check and kill.
  Compile/whitespace, 167 local links, 42 linked code symbols and five 20-topic phase-guide
  checks passed. Credential-pattern/tracked-artifact and private-path review passed;
  no credentials, personal transcripts, recordings, databases or models were added to Git.
