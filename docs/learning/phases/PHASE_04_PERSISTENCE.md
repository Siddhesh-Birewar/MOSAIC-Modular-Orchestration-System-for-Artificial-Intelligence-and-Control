# Phase 4 — Persistent memory, notes and learning

**Status:** complete, v0.4.0 (30%). **Historical evidence:** `93c7807`, `0f5f961`,
`fd37903`, current/tagged project state and PR #3. Reconstructed 2026-11-26.
Reasons/alternatives below are teaching explanations grounded in source, not invented
past experiments. Manual results are owner-confirmed, not newly repeated here.

## 1. Problem

In-memory conversations disappear on restart. The assistant also needs explicit places
for notes, study progress and facts the user deliberately chooses to remember.

## 2. Why it is necessary

Durable records make the assistant useful beyond one process session. Stable IDs and
timestamps allow later retrieval/editing. Explicit curation separates a saved memory
from an ordinary conversation message; this phase does not train model weights.

## 3. Prerequisites

Earlier phases; SQL CRUD, primary/foreign keys, transactions, parameter binding, schema
migrations, file permissions, thread locks, UTC timestamps and persistence testing.

## 4. Technologies

Standard-library SQLite/sqlite3, UUIDs, filesystem permissions and thread RLock. Existing
FastAPI/Pydantic routes and pytest are reused. No vector database, ORM, cloud storage or
embedding model is required.

## 5. Why selected

**Source/PR evidence:** an embedded database keeps data local and deployment small.
Transactions protect multi-row updates; foreign keys preserve relationships; a serialized
connection gives a clear process-local access rule. Keyword memory retrieval is bounded
and easy to inspect. These explain implementation choices without claiming a formal
database-comparison experiment occurred.

## 6. Alternatives and trade-offs

**Reconstructed:** JSON files need custom atomic update/query logic. A database server
adds setup and operations. An ORM can simplify complex models but adds a dependency for
this small schema. Semantic retrieval can match meaning beyond words but needs extra
models/indexing; it remains Phase 7 scope. Unencrypted SQLite is easy to operate but
requires protecting the OS account and backups.

## 7. Architecture and data flow

Authenticated client → validated route → parameterized SQL in `Database.transaction` →
SQLite → structured response. Chat loads a conversation and bounded matching enabled
memories; memories are labeled untrusted data in model context. After successful inference,
one transaction appends both user and assistant messages. Failed/aborted turns do not
persist incomplete pairs. Reset/delete/model mutation coordinate with inference.

## 8. Algorithms and mathematics

Schema migration checks `PRAGMA user_version` and applies version 1 transactionally.
Messages use a per-conversation increasing sequence to preserve order. Foreign keys
with cascade prevent orphan topics/messages. Required fields and progress 0–100 are
validated; progress is user data, not an automatically calculated mastery score.
`retrieve_memories` extracts terms, matches enabled rows using parameterized `LIKE`
conditions, orders by importance/update time and limits results. It is lexical matching,
not cosine similarity or learning. SQL placeholders separate data from SQL instructions.

## 9. Implementation chronology

**Git facts:** `93c7807` introduced database/storage and personal APIs. `0f5f961` fixed
privacy/error and reset/queued-context issues, recorded manual confirmation and finalized
version 0.4.0. **Reconstructed inside implementation:** define schema/migrations, adapt
conversation store, add notes/learning/memory routes, connect retrieval, test restarts,
review privacy/concurrency, close out docs. No finer historical edit sequence is asserted.

## 10. Important files and symbols

- [database.py](../../../backend/app/database.py): `default_database_path`, `Database`,
  `transaction`, `migrate`, `close`.
- [conversations.py](../../../backend/app/conversations.py): `ConversationStore.get`,
  `append_turn`, `reset`, `list`, `delete`.
- [personal_data.py](../../../backend/app/api/personal_data.py): `NoteInput`, `TopicPatch`,
  `MemoryInput`, CRUD endpoints, `_terms` and `retrieve_memories`.
- [intelligence.py](../../../backend/app/api/intelligence.py): `_messages`, `chat`,
  `stream_chat`, reset/delete lock boundaries and queued context refresh.
- [main.py](../../../backend/app/main.py): database lifecycle and sanitized validation/errors.
- [test_persistence.py](../../../backend/tests/test_persistence.py): restart/constraints/privacy tests.

## 11. Component communication

No database server network hop exists: Python calls SQLite in-process. Conversations
and personal-data routes share the database wrapper. API responses use IDs/timestamps;
the LLM only receives selected prompt context, not a raw database connection or API token.
Completed text messages persist, while raw voice audio added later does not.

## 12. Terminal commands

`MOSAIC_DB_PATH` optionally chooses a private location; default is OS application data
outside Git. Keep settings in ignored `.env`. From backend/:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

From root, isolate persistence tests:

```sh
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q backend/tests/test_persistence.py
git show v0.4.0:backend/app/database.py
```

Use synthetic note data for a restart exercise. Do not dump the real database or put
tokens on recorded command lines. Back up only while stopped or via SQLite's backup API.

## 13. Errors and solutions

**Recorded closeout fixes:** URL search terms could reach transport/access logs;
validation errors could echo private input; integrity errors/null updates needed safe
handling. Logs/input echoes were suppressed and conflicts sanitized. Reset races required
shared inference locking plus refreshed queued context. See
[error record](../ERRORS_AND_SOLUTIONS.md) and the named regression tests.

## 14. Performance experiments

No controlled database throughput/search latency benchmark is recorded. Restart tests
establish persistence correctness, not speed. Bounded API listings and memory retrieval
limit output/work but do not guarantee query latency for arbitrary database sizes.

## 15. Security

All personal routes and chat require the configured bearer token. The database directory
uses restrictive permissions when created and its file is restricted where supported;
symlink/special-file configuration is rejected. SQLite is **not encrypted at rest**.
Queries bind user values. Memories are explicit opt-in records and untrusted context,
never automatically extracted from conversations. Keep DB/sidecars/backups/private data
out of Git. One backend worker is required; process-local locks do not coordinate workers.

## 16. Testing and manual verification

**Historical:** 53 tests, compile and diff checks passed. Tests recreate apps over one
temporary database, verify repeatable migration/permissions, ordered histories, reset,
notes CRUD/search, SQL injection resistance, learning constraints/cascade, disabled memory,
failed/aborted turns, sanitized errors and in-flight reset behavior.

**Owner confirmed:** bearer auth/401, note creation/201, same note ID/content/timestamps
after restart, ordered user/assistant history, curated memory persistence/recall in a fresh
conversation, subject/topic creation, invalid-subject/404 and persisted status/60% progress.
The actual verification text/value is intentionally omitted from learning records.

## 17. Git milestones

`93c7807` → closeout `0f5f961` → [PR #3](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/3)
merge `fd37903` → annotated v0.4.0. Package/API version 0.4.0, cumulative roadmap 30%.
This remains the last completed milestone while Phase 6 acceptance is pending.

## 18. Remaining limitations

Unencrypted storage; schema version 1 needs explicit future migrations; keyword-only
retrieval; no automatic memory extraction, semantic retrieval, UI or cloud synchronization.
Disabling a memory cannot retract context already sent to an in-flight model request.
Large-scale query behavior has not been benchmarked. Single backend worker is required.

## 19. Independent rebuilding exercises

In a separate project, create subjects/topics with a foreign key and progress constraint.
Store one fake note, close/reopen the DB and assert ID/timestamps match. Insert a complete
two-message turn transactionally, inject a failure between writes and verify rollback.
Try SQL-looking text as a note title with placeholders; show it remains ordinary data.
Implement a tiny keyword retrieval function and explain what synonyms it misses.

## 20. Educational content

Teach “saved memory is not model training,” demonstrate a synthetic restart, or explain
why a reset needs concurrency coordination. Include the unencrypted-storage limitation
and use an isolated disposable database rather than screenshots of real records.
