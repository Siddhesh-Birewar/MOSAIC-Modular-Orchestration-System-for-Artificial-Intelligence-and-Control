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
- **Bearer token for local actions:** authenticated action endpoints avoid treating loopback binding as authorization. Tools are omitted from model requests unless a valid CLI token is present; the token never enters model context.
- **No filesystem roots by default:** explicit narrow roots are required. Descriptor-based no-follow opens, sensitive-name denial, regular-file checks, and size limits provide defense in depth.
- **Application approval every time:** launches remain fixed to known application paths and cannot run until a short-lived, one-use, argument-bound user approval is consumed.
- **Bounded in-memory audit:** audit events contain outcome metadata only and use a fixed-size ring; durable audit storage requires a later privacy and retention decision.

- **Phase 5 deferred, Phase 6 next:** preserve phase numbering and frontend prototypes while completing backend voice first. Stable release remains 0.4.0 pending voice manual acceptance.
- **Local speech adapters:** Whisper.cpp for existing approved multilingual weights; installed macOS voices provide an initial TTS adapter without speech model downloads. Kokoro/IndicF5 evaluation is in VOICE.md.
- **Half-duplex voice and explicit activation:** capture never overlaps playback; `/voice on` explicitly enables repeated listening. Ctrl+C is the supported interruption path. All voice text passes through the existing authenticated conversation/tool pipeline and typed approval.
