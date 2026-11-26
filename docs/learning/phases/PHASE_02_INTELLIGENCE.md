# Phase 2 — Intelligence engine

**Status:** complete, v0.2.0 (12%). **Historical evidence:** `58bf95f`, tagged project
state and PR #1. Reconstructed 2026-11-26. Current source includes SQLite/auth added later;
Phase 2 conversations were explicitly in-memory. Explanations/alternatives are reconstructed
unless attributed to a recorded decision.

## 1. Problem

A one-shot API cannot maintain a conversation, stream a long reply or make model use
visible. Users need isolated history and a consistent assistant identity.

## 2. Why it is necessary

Multi-turn context supports follow-up questions. Streaming reduces the wait before text
appears. Model availability, safe switching and metrics make local resource use observable.

## 3. Prerequisites

Phase 1; UUIDs, lists/dataclasses, context windows, async generators, JSONL, SSE, cancellation,
locks and tokenization. A model token is not necessarily a word or a network chunk.

## 4. Technologies

Existing FastAPI/HTTPX/Ollama/pytest; standard-library UUIDs, dataclasses and monotonic
clocks. No database or new model-training stack was added in this phase.

## 5. Selection rationale

**Recorded:** in-memory conversations postponed persistence to Phase 4; bounded prompt
context limited growth; SSE carried incremental content while hiding reasoning. One
process lock serialized model activation/unload to reduce unified-memory pressure.

## 6. Alternatives and trade-offs

**Reconstructed:** polling repeats requests and gives coarser updates; WebSockets add
bidirectional flexibility with more connection logic. Exact token budgeting is more
precise than message-count trimming but requires model-aware counting. Persistent storage
would prevent restart loss but was deliberately later scope. No alternative benchmark is
recorded.

## 7. Architecture and data flow

Request resolves conversation/model → lock protects model preparation → system prompt
plus bounded recent messages → Ollama → content events → API SSE → client. A completed
answer appends a user/assistant turn. Failed/aborted work must not become complete history.

## 8. Algorithms and mathematics

Context keeps recent messages plus the new user message; system identity is prepended
separately. The limit counts messages, not exact model tokens. Metrics convert nanoseconds
to seconds by dividing by 10^9. Generation tokens/s = output tokens / evaluation seconds;
zero/missing duration yields an unavailable rate rather than division by zero.
Time to first content chunk and total time have different clock boundaries.

## 9. Implementation chronology

**Fact:** `58bf95f` followed foundation `a79644c` and introduced the Phase 2 feature set.
**Reconstructed within-commit order:** identity/configuration, conversation lifecycle and
context, streaming adapter/SSE, model discovery/switch/unload, metrics/benchmark script,
tests and live verification. Git does not preserve a finer chronological development log.

## 10. Important code

- [prompts.py](../../../backend/app/core/prompts.py): system identity construction.
- [conversations.py](../../../backend/app/conversations.py): `ConversationStore.context`,
  `create`, `reset`, `append_turn` (today persistence-backed).
- [intelligence.py](../../../backend/app/api/intelligence.py): `_messages`, `_prepare_model`,
  `chat`, `stream_chat`, `_sse` and model endpoints.
- [ollama_client.py](../../../backend/app/models/ollama_client.py): `StreamEvent`, `stream_chat`.
- [metrics.py](../../../backend/app/models/metrics.py): `InferenceMetrics.from_ollama`.
- [benchmark_models.py](../../../scripts/benchmark_models.py): opt-in experiment.

## 11. Communication

Ollama streams newline-delimited JSON objects; the adapter yields typed events. FastAPI
translates eligible content into SSE `start`, `token`, `done` or `error`. Private reasoning
fields are excluded. The later CLI's [parse_sse](../../../scripts/chat.py) shows the client
boundary; that CLI was added in Phase 3, not Phase 2.

## 12. Commands

`git show v0.2.0:backend/app/conversations.py` reads original in-memory code without
switching/resetting your tree. Run current tests from root with
`backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q`.
`backend/.venv/bin/python scripts/benchmark_models.py --help` explains opt-in comparison
options; merely reading help does not benchmark. Exact startup is in
[command reference](../COMMAND_REFERENCE.md).

## 13. Errors and solutions

Malformed/incomplete streams and connection failures have sanitized error paths and tests.
Cancellation must close the upstream stream and release the lock, or later requests can
stall. These are source/test-backed design explanations, not additional documented past
incidents. The Phase 1 transient HTTP 500 remained unexplained.

## 14. Experiments and actual results

**Historical live sample:** GPT-OSS 20B returned 200; load 7.62 s, total 10.55 s, input
257 tokens, output 57 tokens, generation 26.38 tokens/s. Recorded at v0.2.0 project state.
The optional model-comparison benchmark was **not run**. One sample cannot establish an
average, model ranking or sustained memory behavior.

## 15. Security

Do not forward hidden reasoning or sensitive transport payloads. A system identity prompt
does not constitute an authorization mechanism. At this tag, no OS tools existed.
Today's personal/chat authentication was hardened in subsequent phases; study history
without treating older boundaries as acceptable for a new deployment.

## 16. Testing methodology

**Historical:** 22 passed, compile check passed, one existing warning. Fake clients verify
context isolation/trimming, model selection/reset, streaming failure/cancellation and
unloading only managed alternate models. Read
`test_prompt_multi_turn_context_trimming_and_conversation_isolation` and
`test_stream_cancellation_releases_response_and_model_lock` in
[test_backend.py](../../../backend/tests/test_backend.py).
Mocks establish protocol behavior, not live model response quality.

## 17. Git milestones

`58bf95f` carries annotated v0.2.0; [PR #1](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/1)
merged Phases 1–2 as `e31b51e`. Cumulative roadmap: 12%. The tag points to the feature
commit, whereas the later PR merge has its own commit.

## 18. Limitations

History vanished on restart at this phase. Message-count bounds are approximate context
control. One backend process owns the model lock; multiple workers need coordination.
Only one live model sample was recorded. Metrics do not by themselves verify answer truth.

## 19. Rebuild exercises

Create a scratch store with two UUID conversations. Add a message-count limit and verify
the histories stay separate. Write an async generator yielding three fake chunks and one
completion event. Cancel it midway and assert cleanup runs. Calculate token rate from
synthetic durations and explain which time was excluded.

## 20. Educational content

Explain streaming versus completed history, or “why stored messages differ from the prompt.”
Compare first-token and generation-rate metrics using synthetic values. Clearly label the
one historical live measurement rather than presenting it as a controlled comparison.
