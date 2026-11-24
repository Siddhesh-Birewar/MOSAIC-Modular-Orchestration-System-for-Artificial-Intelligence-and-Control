# Architecture

MOSAIC starts as a local-first modular monolith. The FastAPI backend owns configuration, API boundaries, model/runtime adapters, and later domain modules for memory, notes, learning, knowledge, projects, and integrations. Typed interfaces keep those modules replaceable without adding service boundaries prematurely.

The React/TypeScript/Tailwind dashboard and Tauri shell are separate clients of the backend; no UI code belongs in backend modules. SQLite is the planned local persistence layer. Ollama is accessed through a narrow HTTP adapter so runtime details do not leak into domain logic. Plugin/MCP adapters will enter through a validated host interface. Services bind to localhost during development.

The current backend also includes a local intelligence layer: an in-memory conversation store builds a MOSAIC system prompt and bounded message context for Ollama. Conversation transcripts are isolated by UUID and discarded on restart. The Ollama adapter supports single-turn and streaming chat, loaded model discovery, unload requests, and inference metrics. A process-local lock serializes inference and unloads another loaded model before switching. No persistence, tools, voice, or frontend is implemented.

## API

- `GET /health`, `GET /health/ollama`
- `GET /models` (installed models with a `loaded` flag), `GET /models/running`
- `GET /models/{model_name}/availability`, `POST /models/{model_name}/unload`
- `POST /conversations` (optional `model`), `GET /conversations/{id}`
- `PATCH /conversations/{id}` with `{ "model": "qwen3:8b" }`
- `POST /conversations/{id}/reset`
- `POST /chat` with `{ "message": "...", "conversation_id": "...", "model": "..." }`; conversation ID and model are optional. If omitted, MOSAIC creates a conversation and uses the configured default.
- `POST /chat/stream` accepts the same body and returns SSE `start`, `token`, `done`, and `error` events. Reasoning fields are not sent to clients.

Configuration: `MOSAIC_OLLAMA_URL`, `MOSAIC_PRIMARY_MODEL`, `MOSAIC_ALLOWED_MODELS`, `MOSAIC_REQUEST_TIMEOUT`, `MOSAIC_CONTEXT_LIMIT`, `MOSAIC_KEEP_ALIVE`, `MOSAIC_SYSTEM_PROMPT`, and `MOSAIC_LOG_LEVEL`. The benchmark at `scripts/benchmark_models.py` is opt-in and sends five small prompts per selected model.
