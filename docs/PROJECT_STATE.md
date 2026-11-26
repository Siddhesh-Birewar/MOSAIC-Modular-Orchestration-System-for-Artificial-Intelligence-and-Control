# Project state

## Current phase
Phase 6 — Local Voice Intelligence is active on `feature/phase-6-voice-intelligence`.
Phase 5 dashboard/humanoid is officially deferred; original numbering is retained.
Phase 4 is complete at annotated `v0.4.0` / merge `fd37903`; the last verified cumulative
roadmap milestone remains 30%. No Phase 5 work is removed or changed.

## Phase 6 neural upgrade — application acceptance pending
- Continued from clean synchronized preview commit d8d3e46 on the same branch/PR #4; baseline 78 tests passed.
- Verified existing isolated Python 3.12.16 neural environment (mlx-audio 0.6.8, mlx 0.32.5, misaki 0.9.4), Whisper executable/Base files and cached Kokoro assets. No dependencies reinstalled or weights downloaded. Actual cached tensor header is F32 despite the repository BF16 label; runtime dtype reporting is included.
- Implemented one offline persistent Kokoro worker, reused model/language pipelines, configurable warm-up, bounded private IPC/queues, process lock, timeout/cancellation/reaping, bounded restart attempts, idle/memory-aware release and explicit labeled macOS fallback.
- Added speech normalization, response-aware English/Hindi/Hinglish routing and bounded Hindi segmentation. Two bounded client stages overlap synthesis/playback with tool-free LLM generation. Tool-enabled turns buffer until completed orchestration; denied/failed tools receive deterministic spoken noncompletion notices.
- Added explicit language/provider/speed/reasoning/tool-mode CLI controls. The installed Ollama 0.40.16 advertises GPT-OSS low/medium/high; requests are validated before sending think. GPT-OSS remains the default; no heuristic automatic model/reasoning switch.
- Extended content-free playback/state/cancellation events and recovery. Half-duplex capture and typed approvals are preserved. No frontend, humanoid, acoustic barge-in or fabricated alignment.
- Automated suite: 116 passed, one real-model integration skipped by default (executed separately and passed), one existing Starlette/httpx deprecation warning. Compile/diff checks passed at the last run; rerun after final edits.
- Real offline warm neural generation reused one PID: short requests 0.130–0.171 s; synthetic Whisper first/repeat 0.331/0.229 s. Worker initialization with warm-up 2.677 s.
- Concurrent TTS 0.596–0.875 s (misses <0.5 s goal); RTF 0.127–0.186. GPT-OSS 22.45 tokens/s alone vs 14.54 with TTS in a short cache-biased experiment. System swap increased; MLX allocation is not total memory.
- Real tool-free HTTP pipeline: first token 1.998 s, first segment 2.941 s, first generated audio 4.074 s, chat complete 4.323 s, total generation 4.945 s. Generated audio overlapped chat; audible latency remains unmeasured and the three-second goal is not established.
- Warm-up-disabled experiment: init 0.587 s, first English 2.976 s, first Hindi 0.468 s, repeated English 0.143 s. See [VOICE.md](VOICE.md) for full methodology/limits and user-provided earlier component measurements context.
- User reported high-quality standalone Bella and successful initial Hindi/Hinglish samples. Integrated microphone/playback/continuous/tool-safety, recovery, and sustained resource acceptance remain pending. No microphone capture or actual application launch was performed by automated checks.
- Real HTTP injected cancellation recovered in 0.050 s with zero remaining voice threads; a subsequent chat completed. Physical playback/microphone interruption still needs manual acceptance.
- Stable API/package metadata remains 0.4.0. Do not merge or tag v0.6.0 until user acceptance. Phase 5 remains deferred and Phase 7 is not started.

## Phase 4 implementation status
- Added a standard-library SQLite database with transactional `user_version` migrations, foreign keys, a serialized connection, and restrictive file/directory permissions where supported.
- Replaced in-memory conversation storage with persistent ordered messages, model selection, reset, bounded listing, and deletion. Completed turns are written atomically only after successful synchronous or streaming inference.
- Added authenticated CRUD/search endpoints for notes; subject/topic learning records with status, progress, and revision dates; and explicit curated memories with enable/disable and bounded keyword retrieval.
- Retrieved memories are separate untrusted user-context data. Conversations are never automatically promoted to memories; memory API endpoints are authenticated.
- `MOSAIC_DB_PATH` can override the default OS application-data location outside the repository. Database files and sidecars are ignored by Git.

## Phase 4 verification history
- Existing Phase 1–3 behavior remains covered by regression tests.
- Phase 4 closeout tests: 53 passed, one Starlette/httpx deprecation warning.
- Tests cover repeatable migrations, restrictive permissions, conversation persistence across app recreation, ordering/model/reset/delete, notes CRUD/search and injection-safe queries, learning progress and cascade integrity, memory enable/edit/delete/context behavior, auth, and failed/aborted turn handling.
- Full suite, compile checks and `git diff --check` passed during closeout.
- User confirmed MacBook manual verification: bearer authentication works; unauthenticated personal APIs return 401; note creation returns 201; the original note retains its UUID, content and timestamps after a full backend restart.
- Conversation user/assistant ordering, curated memory, and learning topic status with 60% progress survived restart. A fresh conversation recalled a fictional verification value from saved memory without the value appearing in that conversation's user input. Subject/topic creation works and invalid subject IDs return 404.
- Closeout regression tests cover URL-log privacy, validation response privacy, safe learning-update errors, and conversation reset/queued-context synchronization. No real verification content or tokens were added to the repository.

## Known limitations
- SQLite has no application-level encryption at rest; protect the OS account and backups.
- Migrations are currently at schema version 1; future schema changes need additional numbered migrations.
- Keyword memory retrieval is intentionally simple; semantic retrieval belongs to Phase 7.
- There is no automatic memory extraction, vector database, UI, or cloud storage.
- Use one backend worker; inference and conversation mutations use a process-local lock.
- A memory change affects subsequent retrieval; it cannot retract information already sent to an in-flight model request.

## Manual persistence check
Set `MOSAIC_DB_PATH` to a private local file in ignored `.env`, configure a strong `MOSAIC_API_TOKEN`, then start from `backend/` using:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

Create a conversation or note through an authenticated API call, stop the backend, restart it with the same `.env`, and retrieve the same record. Use disposable test content; do not place credentials or sensitive personal information in test records.
