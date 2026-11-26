# Project state

## Current phase
Phase 6 — Local Voice Intelligence is active on `feature/phase-6-voice-intelligence`.
Phase 5 dashboard/humanoid is officially deferred; original numbering is retained.
Phase 4 is complete at annotated `v0.4.0` / merge `fd37903`; the last verified cumulative
roadmap milestone remains 30%. No Phase 5 work is removed or changed.

## Phase 6 implementation and verification
- Baseline: clean Phase 5 branch at main `fd37903`; remote main and annotated v0.4.0 verified. Existing 53 tests passed before implementation; Phase 6 branch created from synchronized main.
- Added validated PCM audio, local Whisper.cpp adapter, provider-independent STT/TTS protocols, installed macOS speech adapter, authenticated speech APIs and cancelable local subprocess cleanup.
- Added explicit push-to-talk/continuous CLI modes, configurable energy VAD and mic, existing chat/memory/tool-approval integration, sentence playback and content-free voice events. Microphone capture closes during replies.
- Installed the optional sounddevice dependency successfully on macOS ARM64. No microphone capture or application launching was performed during development checks.
- Live localhost API checks passed: unauthenticated voice status 401, authenticated status 200, native synthesis 200 with no-store WAV, malformed audio 422. No audio playback or microphone capture was involved.
- Native English WAV generation smoke passed. Benchmark: 1.763 s to generated audio; 3.299 s audio; 64,012,288-byte sampled process-tree peak RSS (excludes Ollama and OS speech daemons). Real STT/full-pipeline latency is unmeasured because no local whisper-cli/weights were configured.
- Full automated suite: 78 passed (one existing Starlette/httpx deprecation warning); compile and diff checks passed. Voice tests use mocked hardware/providers. English/Hindi/Hinglish recognition quality and TTS naturalness remain unverified; provider locale metadata does not establish tested support.
- Keep stable API/package metadata at 0.4.0 pending verification; intended voice tag is v0.6.0 with no implied Phase 5 completion. Do not merge/tag until manual checks in [VOICE.md](VOICE.md) are confirmed.
- Speech weights have not been downloaded. Configure an existing approved multilingual model or obtain explicit approval for the selected download before attempting live transcription.

## Phase 4 implementation status
- Added a standard-library SQLite database with transactional `user_version` migrations, foreign keys, a serialized connection, and restrictive file/directory permissions where supported.
- Replaced in-memory conversation storage with persistent ordered messages, model selection, reset, bounded listing, and deletion. Completed turns are written atomically only after successful synchronous or streaming inference.
- Added authenticated CRUD/search endpoints for notes; subject/topic learning records with status, progress, and revision dates; and explicit curated memories with enable/disable and bounded keyword retrieval.
- Retrieved memories are separate untrusted user-context data. Conversations are never automatically promoted to memories; memory API endpoints are authenticated.
- `MOSAIC_DB_PATH` can override the default OS application-data location outside the repository. Database files and sidecars are ignored by Git.

## Phase 4 verification history
- Existing Phase 1–3 behavior remains covered by regression tests.
- Phase 4 automated tests currently pass: 53 passed, one Starlette/httpx deprecation warning.
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
