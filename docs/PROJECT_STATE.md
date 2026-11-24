# Project state

## Current phase
Phase 4 — Persistent Memory, Notes and Learning is in progress on `feature/phase-4-persistent-memory`. Phase 3 is complete and tagged `v0.3.0`.

## Phase 4 implementation status
- Added a standard-library SQLite database with transactional `user_version` migrations, foreign keys, a serialized connection, and restrictive file/directory permissions where supported.
- Replaced in-memory conversation storage with persistent ordered messages, model selection, reset, bounded listing, and deletion. Completed turns are written atomically only after successful synchronous or streaming inference.
- Added authenticated CRUD/search endpoints for notes; subject/topic learning records with status, progress, and revision dates; and explicit curated memories with enable/disable and bounded keyword retrieval.
- Retrieved memories are separate untrusted user-context data. Conversations are never automatically promoted to memories; memory API endpoints are authenticated.
- `MOSAIC_DB_PATH` can override the default OS application-data location outside the repository. Database files and sidecars are ignored by Git.

## Verification status
- Existing Phase 1–3 behavior remains covered by regression tests.
- Phase 4 automated tests currently pass: 50 passed, one Starlette/httpx deprecation warning.
- Tests cover repeatable migrations, restrictive permissions, conversation persistence across app recreation, ordering/model/reset/delete, notes CRUD/search and injection-safe queries, learning progress and cascade integrity, memory enable/edit/delete/context behavior, auth, and failed/aborted turn handling.
- Compile checks and diff checks remain to be rerun after final changes.
- Manual restart/persistence verification with a user-configured database has not yet been reported; do not merge or create `v0.4.0` until the user confirms it.

## Known limitations
- SQLite has no application-level encryption at rest; protect the OS account and backups.
- Migrations are currently at schema version 1; future schema changes need additional numbered migrations.
- Keyword memory retrieval is intentionally simple; semantic retrieval belongs to Phase 7.
- There is no automatic memory extraction, vector database, UI, or cloud storage.

## Manual persistence check
Set `MOSAIC_DB_PATH` to a private local file in ignored `.env`, configure a strong `MOSAIC_API_TOKEN`, then start from `backend/` using:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

Create a conversation or note through an authenticated API call, stop the backend, restart it with the same `.env`, and retrieve the same record. Use disposable test content; do not place credentials or sensitive personal information in test records.
