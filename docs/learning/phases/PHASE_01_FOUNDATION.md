# Phase 1 — Project foundation

**Status:** complete, v0.1.0 (5%). **Historical evidence:** `a79644c`, tagged
`docs/PROJECT_STATE.md`, and merged PR #1. This guide was reconstructed on 2026-11-26.
Reasons, comparisons and exercises below are teaching explanations unless identified as
recorded decisions. Current code includes later phases; inspect v0.1.0 for the original.

## 1. Problem

Before an assistant can remember or act, it needs a reliable way to receive a request,
connect to a local model runtime and return an understandable response or error.

## 2. Why it is necessary

A small backend separates AI orchestration from future interfaces. A terminal, dashboard
or other client can use the same API without importing model implementation code.
Local processing is an explicit project requirement.

## 3. Prerequisites

Learn Python functions/modules, dictionaries, type hints, exceptions and virtual
environments. Then learn HTTP methods/status codes, JSON, async/await and environment
variables. An HTTP server and an AI inference runtime are separate programs.

## 4. Technologies

Python, FastAPI, Pydantic schemas, Uvicorn, HTTPX, local Ollama and pytest. Configuration
and logging use the standard library. See the [registry](../TECHNOLOGY_REGISTRY.md).

## 5. Why these were selected

**Recorded:** a modular monolith and narrow Ollama HTTP adapter keep deployment simple
and inference local. **Reconstructed:** FastAPI exposes typed request boundaries; HTTPX
supports async I/O and mocked responses; pytest makes failures repeatable.

## 6. Alternatives and trade-offs

**Reconstructed comparison:** direct model-library integration would couple backend
dependencies to inference. A cloud API adds external processing/cost. Flask could serve
HTTP but has a different async/schema workflow. Separate services add operations before
they are needed. These are comparisons, not documented Phase 1 trials.

## 7. Architecture and data flow

Client sends JSON → FastAPI validates → route calls Ollama adapter → local Ollama performs
inference → adapter validates response → API returns answer. Health routes check the
backend and runtime separately. No database, tools or voice existed at this tag.

## 8. Algorithms and mathematics

There is no new ML training algorithm in this phase. MOSAIC calls an existing model.
The important algorithm is controlled error classification: distinguish connection,
timeout, invalid payload and inference failures, then return a sanitized API response.
Async waiting saves blocking time; it does not reduce the model's computation.

## 9. Implementation chronology

**Commit-level fact:** `a79644c` added the foundation and Phase 1 closeout record after
the initial README commit `2e0b272`. **Reconstructed build order within that commit:**
set up package/configuration, construct app and health routes, write Ollama adapter,
add one-turn chat/schema, add mocked tests, verify localhost integration, update docs.
The exact edit-by-edit order inside that commit is not preserved.

## 10. Important code

- [main.py](../../../backend/app/main.py): `create_app` wires dependencies and lifecycle.
- [config.py](../../../backend/app/core/config.py): `Settings.from_env` reads configuration.
- [health.py](../../../backend/app/api/health.py): `health`, `ollama_health`, `models`.
- [ollama_client.py](../../../backend/app/models/ollama_client.py): `OllamaClient._request`,
  `list_models`, `chat` and typed errors.
- [schemas.py](../../../backend/app/schemas.py): request/response contracts, expanded later.
- [logging.py](../../../backend/app/core/logging.py): content-free service logging.

## 11. Component communication

Routes call Python objects inside the backend; only the Ollama adapter crosses a local
HTTP boundary. Clients use HTTP and receive JSON. Dependency injection lets tests replace
Ollama without opening a model process. Today's auth/persistence/voice paths came later.

## 12. Commands and purpose

From root, `git show v0.1.0:backend/app/main.py` shows the actual original app.
For today's startup use [command reference](../COMMAND_REFERENCE.md); from backend/:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

`curl http://127.0.0.1:8000/health` checks service health. `--env-file ../.env` loads
private configuration. Current protected routes require authentication even though the
original foundation did not yet implement the later action/personal-data boundaries.

## 13. Errors, root causes and solutions

**Historical:** an earlier Ollama HTTP 500 occurred. Its cause was not identified; later
successful live inference does not prove a specific remedy. Mocked client tests verify
connection, timeout and malformed-response handling. Never document an invented fix.

## 14. Performance experiments

**Historical verification:** Uvicorn localhost health returned 200; TestClient health,
Ollama health and model discovery returned 200. The owner verified GPT-OSS live chat.
No controlled latency, throughput or memory benchmark is recorded for Phase 1.

## 15. Security

Bind to loopback, keep configuration private and exclude prompts/responses from logs.
No shell/action endpoint was provided. Localhost is a network boundary, not proof of
authorization; later phases added bearer protection. No weights or secrets belong in Git.

## 16. Testing

**Tagged historical result:** 10 passed, one Starlette/httpx warning. Mock HTTP responses
test protocol/error handling; backend tests check contracts and validation. These checks
do not prove arbitrary generated answers are correct. Current regression tests live in
[test_backend.py](../../../backend/tests/test_backend.py) and
[test_ollama_client.py](../../../backend/tests/test_ollama_client.py).

## 17. Git and milestones

Implementation/tag: `a79644c` / annotated v0.1.0. Phases 1 and 2 were later merged
together through [PR #1](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/1)
as `e31b51e`. Do not say a separate Phase 1 PR existed. Cumulative roadmap: 5%.

## 18. Limitations

At the tag: one-turn inference, no durable memory, tools, UI or voice. Live success was
one installed model, not an evaluation of all installed models. The earlier 500's cause
remained unknown. Later source expands these capabilities; do not project it backward.

## 19. Rebuild exercises

In a separate scratch project, implement `/health`, inject a fake Ollama client and return
one synthetic answer. Add a timeout and malformed-JSON test. Explain why HTTP 200 health
cannot guarantee model availability. Compare your adapter with the tagged implementation;
do not change the active branch or expose a service beyond loopback.

## 20. Educational content

Make a short explanation of “backend versus model runtime,” or demonstrate three health
checks that establish different facts. Show fake data and error categories; never record
your environment file. More ideas: [content list](../INSTAGRAM_CONTENT_IDEAS.md).
