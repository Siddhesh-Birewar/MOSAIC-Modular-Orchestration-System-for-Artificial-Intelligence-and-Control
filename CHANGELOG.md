# Changelog

## v0.4.0 — Phase 4
- Completed local SQLite conversations, notes, learning subjects/topics, and explicitly curated memories. Personal APIs require bearer authentication.
- User verified restart persistence for notes (UUID/content/timestamps), ordered conversation history, curated memory recall in a fresh conversation, and learning status/progress. Verified 401, 201 and invalid-subject 404 responses.
- Suppressed transport/access URL logs and validation input echoes; sanitized integrity conflicts and rejected null required learning fields.
- Serialized conversation reset/delete with inference and refreshed queued context to prevent stale history and writes after reset.
- 53 automated tests, compile and diff checks passed. Updated package and API versions to 0.4.0.
- Known limitations: unencrypted SQLite, keyword-only memory retrieval, single backend worker.

## Earlier milestones
- Established the Phase 1 backend foundation, local Ollama API integration, tests, and project documentation.
- Closed Phase 1 after successful user-verified live `gpt-oss:20b` inference. The cause of the earlier transient Ollama HTTP 500 was not determined.
- Implemented Phase 2 identity prompting, in-memory conversations, SSE streaming, model selection/status/unloading, inference metrics, and an opt-in local benchmark.
- Completed Phase 3 safe tools and CLI: typed permission-gated tools, default-deny filesystem access, explicit app-launch approval, authenticated action endpoints, bounded audit history, Ollama streamed tool-call aggregation, and terminal SSE client. Manual checks and deterministic security tests passed.
