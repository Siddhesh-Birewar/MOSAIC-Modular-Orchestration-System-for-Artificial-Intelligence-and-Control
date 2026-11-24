# Architecture

MOSAIC starts as a local-first modular monolith. The FastAPI backend owns configuration, API boundaries, model/runtime adapters, and later domain modules for memory, notes, learning, knowledge, projects, and integrations. Typed interfaces keep those modules replaceable without adding service boundaries prematurely.

The React/TypeScript/Tailwind dashboard and Tauri shell are separate clients of the backend; no UI code belongs in backend modules. SQLite is the planned local persistence layer. Ollama is accessed through a narrow HTTP adapter so runtime details do not leak into domain logic. Plugin/MCP adapters will enter through a validated host interface. Services bind to localhost during development.

The backend includes a local intelligence layer, a typed tool host, and a SQLite persistence layer. Conversations are UUID-isolated with ordered messages and bounded context. The database uses versioned `user_version` migrations, foreign keys, transactions, a single serialized connection, and restrictive local file permissions. The Ollama adapter supports streaming structured function calls. Tool calls pass through registry lookup, strict input validation, default-deny permission evaluation, approval verification, bounded execution, output validation, and content-free audit recording. Tools are enabled for model-selected calls only on authenticated requests. Notes, learning topics, and curated memories use separate tables and authenticated APIs. Memory retrieval is bounded and keyword-based; memory is never inferred or saved automatically. The process-local inference lock serializes model use. Voice and frontend are not implemented.

## API

- `GET /health`, `GET /health/ollama`
- `GET /models` (installed models with a `loaded` flag), `GET /models/running`
- `GET /models/{model_name}/availability`, `POST /models/{model_name}/unload`
- `POST /conversations` (optional `model`), `GET /conversations/{id}`, `GET /conversations?limit=50&offset=0`, `DELETE /conversations/{id}`
- `PATCH /conversations/{id}` with `{ "model": "qwen3:8b" }`
- `POST /conversations/{id}/reset`
- `POST /chat` with `{ "message": "...", "conversation_id": "...", "model": "..." }`; conversation ID and model are optional. If omitted, MOSAIC creates a conversation and uses the configured default.
- `POST /chat/stream` accepts the same body and returns SSE `start`, `token`, `done`, and `error` events. Reasoning fields are not sent to clients.
- `GET /tools` lists registered capabilities and input schemas.
- `POST /tools/invoke` invokes a validated tool; bearer authentication is required. Approval-required actions return a short-lived approval ID without executing.
- `GET /approvals`, `POST /approvals/{id}/decision`, `GET /permissions`, and `GET /audit` require bearer authentication.
- Conversation, chat, note, learning, and memory endpoints require the configured bearer token.
- Notes: `POST/GET /notes`, `GET/PUT/DELETE /notes/{id}`; `GET /notes?q=...` performs bounded keyword search.
- Learning: CRUD for `/learning/subjects` and `/learning/subjects/{id}/topics`; topics support status, progress (0–100), and revision date.
- Curated memory: `POST/GET /memories`, `GET/PUT/DELETE /memories/{id}`, and `GET /memories/search?q=...`.

Built-ins: `system_cpu_usage`, `system_memory`, `system_battery`, `system_disk`, `system_macos_version`, `system_uptime`, `system_ollama_models`, `filesystem_list_directory`, `filesystem_search_filenames`, `filesystem_read_text_file`, `filesystem_file_metadata`, and `applications_launch`.

Configuration: `MOSAIC_DB_PATH` optionally selects the SQLite file; the default is an OS application-data directory outside the repository. Other settings include `MOSAIC_OLLAMA_URL`, `MOSAIC_PRIMARY_MODEL`, `MOSAIC_ALLOWED_MODELS`, `MOSAIC_REQUEST_TIMEOUT`, `MOSAIC_CONTEXT_LIMIT`, `MOSAIC_KEEP_ALIVE`, `MOSAIC_SYSTEM_PROMPT`, `MOSAIC_API_TOKEN`, `MOSAIC_ALLOWED_ROOTS`, `MOSAIC_ALLOWED_APPLICATIONS`, audit capacity, and tool limits. The benchmark at `scripts/benchmark_models.py` is opt-in and sends five small prompts per selected model.

The CLI at `scripts/chat.py` uses only the FastAPI API. It handles SSE incrementally and sends the token only in the authorization header when responding to approval requests. The Ollama adapter accumulates assistant content and structured tool calls across streamed chunks, merging partial calls with matching Ollama call indices or IDs; calls lacking either are retained as separate entries. Reasoning fields are excluded. Each assembled call still undergoes schema validation. If the model does not return Ollama's structured `tool_calls` field, MOSAIC does not infer or execute a tool from prose.
