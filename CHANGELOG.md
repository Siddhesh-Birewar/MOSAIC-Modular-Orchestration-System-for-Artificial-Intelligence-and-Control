# Changelog

## Unreleased — Phase 6 neural upgrade
- Added persistent offline MLX Kokoro worker using the existing isolated neural environment and cached assets, with warm-up, bounded IPC/queues/restarts, cancellation, retention, readiness/dtype/resource reporting and explicit native fallback.
- Added spoken normalization, English/Hindi/Hinglish routing, bounded segmentation and ordered streaming synthesis/playback. Tool-enabled speech remains buffered until completed orchestration; failed actions receive deterministic noncompletion notices.
- Added language/provider/speed/reasoning/tool-mode CLI controls, UUID-scoped cancellation, validated installed Ollama thinking levels and real-model benchmark tooling. Preserve original transcripts and typed approvals.
- 116 deterministic tests plus one explicit real-model integration test pass. Component and real HTTP experiments confirm streaming overlap but concurrent synthesis and first-generated-audio targets are not universally met; audible/continuous/sustained-load acceptance remains pending.

## Earlier Phase 6 preview
- Deferred Phase 5 dashboard/humanoid and retained phase numbering for backend-first development.
- Added authenticated local speech APIs, Whisper.cpp and installed macOS TTS adapters, bounded PCM validation, cancellation, temporary-file cleanup, and optional sounddevice capture/playback.
- Added explicit voice CLI modes, energy VAD, state/amplitude/playback events, sentence synthesis, and an opt-in benchmark script. Existing persistence and typed tool approval paths are reused.
- Voice quality/end-to-end hardware verification is pending; stable metadata remains 0.4.0. Do not merge/tag Phase 6 until user confirmation.


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
