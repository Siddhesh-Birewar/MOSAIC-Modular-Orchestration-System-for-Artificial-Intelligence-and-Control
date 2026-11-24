# Project state

## Current phase
Phase 2 — Intelligence engine: implementation complete. Phase 1 is closed.

## Completed tasks
- Created `feature/project-foundation` and initial repository structure.
- Added localhost FastAPI health, Ollama health, model discovery, and one-turn chat endpoints.
- Added environment configuration, content-free JSON logs, and mocked backend/client tests.
- Verified local Ollama health and model discovery through the backend. Installed models: `gpt-oss:20b`, `nomic-embed-text:latest`, `glm-ocr:latest`, and `qwen3:8b`.
- User manually verified a successful live `POST /chat` request using `gpt-oss:20b`.
- Added a configurable MOSAIC identity prompt, bounded multi-turn conversations, conversation reset/model selection, and independent UUID contexts.
- Added Ollama SSE streaming with private reasoning fields excluded, interruption/cancellation cleanup, metrics, and sanitized errors.
- Added loaded-model status, availability checks, safe unload/switch behavior, and an opt-in benchmark script.

## Pending tasks
- None for the requested Phase 2 scope. Phase 3 tool execution is not started.

## Known issues
- Conversations are in-memory and are discarded when the backend restarts; SQLite persistence is Phase 4.
- Inference and model changes are serialized within one backend process. Multiple backend workers would need shared coordination.
- One installed-model live inference was run with `gpt-oss:20b`; the opt-in comparison benchmark was not run.
- An earlier Ollama HTTP 500 occurred, but its cause was not identified.
- Frontend, voice, and tool execution are not implemented.

## Test results
`cd backend && .venv/bin/python -m pytest`: 22 passed (one Starlette/httpx deprecation warning).
`python -m compileall -q app ../scripts/benchmark_models.py`: passed.
Live Uvicorn check on `127.0.0.1:8766`: `/health` 200, `/health/ollama` 200, `POST /chat` 200 using `gpt-oss:20b`. Response: `MOSAIC phase two ready`. Metrics: load 7.62 s, total 10.55 s, input 257 tokens, output 57 tokens, 26.38 tokens/s. Benchmark not run.

## Exact next development steps
1. Start the API using the README instructions.
2. Verify `POST /conversations`, multi-turn `POST /chat`, and `POST /chat/stream` manually as needed.
3. Begin Phase 3 only when tool execution is requested and its permission boundary is designed.
