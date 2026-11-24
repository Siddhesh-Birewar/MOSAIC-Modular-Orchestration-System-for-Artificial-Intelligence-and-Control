# Architecture decisions

- **Modular monolith:** one Python/FastAPI backend with clear modules avoids distributed complexity while preserving extension points.
- **Local Ollama HTTP adapter:** isolates runtime API details and keeps inference local; URL and model are configurable.
- **SQLite planned, not yet added:** suitable for local persistence, but Phase 1 has no data model or migration needs.
- **Independent frontend:** React/TypeScript and eventual Tauri client communicate through the API rather than importing backend code.
- **Permission gate before tools:** integrations must validate and authorize every action; unrestricted shell execution is excluded.
- **Environment config and private logs:** avoids hard-coded machine-specific settings and prevents user content from entering logs.
- **In-memory conversations in Phase 2:** provides multi-turn and isolated contexts without prematurely introducing persistence; SQLite remains Phase 4.
- **Bounded prompt context:** configurable message count limits prompt growth while always prepending MOSAIC system instructions.
- **SSE plus Ollama stream adapter:** forwards answer content progressively while omitting model reasoning fields; cancellation closes the HTTP stream.
- **Serialized model activation:** inference and unload operations share a process lock, and another loaded model is unloaded before switching to limit unified-memory pressure.
- **Opt-in benchmark:** the script reports timing and token metrics only; it is never invoked by startup or tests.
