# Changelog

## Unreleased
- Started Phase 4 SQLite persistence for conversations, notes, learning subjects/topics, and explicitly curated long-term memories. Personal data APIs now require bearer authentication.
- Established the Phase 1 backend foundation, local Ollama API integration, tests, and project documentation.
- Closed Phase 1 after successful user-verified live `gpt-oss:20b` inference. The cause of the earlier transient Ollama HTTP 500 was not determined.
- Implemented Phase 2 identity prompting, in-memory conversations, SSE streaming, model selection/status/unloading, inference metrics, and an opt-in local benchmark.
- Completed Phase 3 safe tools and CLI: typed permission-gated tools, default-deny filesystem access, explicit app-launch approval, authenticated action endpoints, bounded audit history, Ollama streamed tool-call aggregation, and terminal SSE client. Manual checks and deterministic security tests passed.
