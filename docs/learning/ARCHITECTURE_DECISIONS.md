# Architecture decisions for learners

This explains the decisions in [DECISIONS.md](../DECISIONS.md) and the source.
**Recorded** means an existing decision/PR states it. Alternatives below are
**reconstructed comparisons**, unless explicitly described as evaluated; they are not
claims that every alternative was experimentally tried.

## One modular backend (recorded, Phase 1)

[create_app](../../backend/app/main.py) assembles configuration, routes and adapters in
one process. Modules keep responsibilities separate without network services for every
feature. Microservices would add deployment, authentication and failure modes before
there is evidence they are needed. Trade-off: a backend crash affects all its modules.

## Adapter around local inference (recorded, Phases 1–2)

[OllamaClient](../../backend/app/models/ollama_client.py) owns HTTP details and translates
failures into typed exceptions. Routes need not know Ollama's wire format. Direct calls
scattered through routes would be shorter initially but harder to mock and change.
Local inference avoids an external processing dependency; it still consumes local memory.

## SSE and bounded context (recorded, Phase 2)

SSE carries named events over one HTTP response. It fits incremental server-to-client
answers; WebSockets would support bidirectional messaging but need more lifecycle logic.
[ConversationStore.context](../../backend/app/conversations.py) bounds message count,
not exact tokens. A fixed count is simple but does not guarantee a fixed memory/token cost.

## Executor as the action boundary (recorded, Phase 3)

[ToolExecutor](../../backend/app/tools/executor.py) validates and authorizes model-selected
and direct API calls alike. Model prose cannot become a command. Launch approvals are
short-lived, argument-bound and single-use. A permanent blanket approval would reduce
friction but lose per-action consent. OS process permissions still limit the strength of
this application boundary; it is not a full operating-system sandbox.

## SQLite and explicit memory (source/PR evidence, Phase 4)

[Database](../../backend/app/database.py) supplies one serialized connection, transactions
and schema versioning. SQLite removes the need for a database server. JSON files would
need custom atomic updates and relationships; a server database adds operations.
Keyword retrieval in [retrieve_memories](../../backend/app/api/personal_data.py) is small
and inspectable; embeddings add models/indexes and belong to later scope. Curated memory
requires an explicit API write rather than automatically promoting conversations.
SQLite is unencrypted; a thread lock does not coordinate multiple backend processes.

## Persistent isolated neural worker (recorded, active Phase 6)

[KokoroWorker](../../backend/app/voice/neural.py) keeps the existing MLX environment
separate from backend dependencies. One child reuses model/pipelines over bounded private
JSONL pipes. A process per sentence repeats startup; an HTTP TTS service needs a new
authenticated boundary. Trade-offs: IPC validation, restart and cancellation complexity.
The worker is an adapter within the monolith, not a separately deployed microservice.

## Two explicit speech safety modes (recorded, active Phase 6)

[stream_chat](../../backend/app/api/intelligence.py) emits tool-free segments during
generation only when tools are explicitly disabled. Tools-on waits for completed
orchestration. This costs latency but prevents a provisional model preface from sounding
like an executed action. Clients consume `speech_segment`, never raw token events.

## Preserve measured reality (recorded, active Phase 6)

The cached repository's BF16 name conflicts with its F32 tensor header. Preserve shared
assets and report dtypes rather than silently converting. Explicit reasoning levels are
validated against installed Ollama metadata; no unreliable automatic classifier was added.
Half-duplex capture avoids feedback while full-duplex/echo cancellation remains absent.
