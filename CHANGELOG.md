# Changelog

## Unreleased
- Established the Phase 1 backend foundation, local Ollama API integration, tests, and project documentation.
- Closed Phase 1 after successful user-verified live `gpt-oss:20b` inference. The cause of the earlier transient Ollama HTTP 500 was not determined.
- Implemented Phase 2 identity prompting, in-memory conversations, SSE streaming, model selection/status/unloading, inference metrics, and an opt-in local benchmark.
- Started Phase 3 safe tools and CLI: typed permission-gated tool registry, default-deny filesystem access, explicit approval for app launches, authenticated action endpoints, bounded audit history, and terminal SSE client.
