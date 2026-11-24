# Project state

## Current phase
Phase 4 — Persistent Memory, Notes and Learning is complete. Target release: `v0.4.0`; roadmap completion: 30%. Prepare `feature/phase-5-dashboard` after merging and synchronizing main; Phase 5 implementation has not started.

## Phase 4 implementation status
- Added a standard-library SQLite database with transactional `user_version` migrations, foreign keys, a serialized connection, and restrictive file/directory permissions where supported.
- Replaced in-memory conversation storage with persistent ordered messages, model selection, reset, bounded listing, and deletion. Completed turns are written atomically only after successful synchronous or streaming inference.
- Added authenticated CRUD/search endpoints for notes; subject/topic learning records with status, progress, and revision dates; and explicit curated memories with enable/disable and bounded keyword retrieval.
- Retrieved memories are separate untrusted user-context data. Conversations are never automatically promoted to memories; memory API endpoints are authenticated.
- `MOSAIC_DB_PATH` can override the default OS application-data location outside the repository. Database files and sidecars are ignored by Git.

## Verification status
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
