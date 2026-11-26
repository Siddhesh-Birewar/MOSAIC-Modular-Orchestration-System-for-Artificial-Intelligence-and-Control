# Learning roadmap

Study in dependency order. The checkpoints below are study goals, not new product phases.
Use disposable synthetic examples; never export your real database into a tutorial.

1. **Python and HTTP foundations.** Learn modules, type hints, dataclasses, exceptions,
   async/await, JSON, request/response and status codes. Read
   [Phase 1](phases/PHASE_01_FOUNDATION.md), then trace `/health` through
   [health.py](../../backend/app/api/health.py). Checkpoint: explain why a running API
   does not prove Ollama can perform inference.
2. **State and streaming.** Learn UUIDs, context windows, async iterators, SSE and locks.
   Read [Phase 2](phases/PHASE_02_INTELLIGENCE.md),
   [OllamaClient.stream_chat](../../backend/app/models/ollama_client.py) and
   [stream_chat](../../backend/app/api/intelligence.py). Checkpoint: draw the difference
   between stored history and the bounded prompt sent to the model.
3. **Trust boundaries.** Learn authentication, authorization, schema validation, symlinks,
   approval replay and time-of-check/time-of-use risks. Read
   [Phase 3](phases/PHASE_03_SAFE_TOOLS.md) and
   [ToolExecutor.invoke](../../backend/app/tools/executor.py). Checkpoint: prove an
   outside-root read is rejected using a deterministic test, without asking an LLM.
4. **Durable state.** Learn SQL, transactions, primary/foreign keys, migrations, parameter
   binding and concurrency. Read [Phase 4](phases/PHASE_04_PERSISTENCE.md) and
   [Database.transaction](../../backend/app/database.py). Checkpoint: store one synthetic
   note, restart an isolated test app and retrieve the same ID and timestamps.
5. **Audio and concurrent pipelines.** Learn PCM, sample rates, RMS, VAD, STT/TTS,
   subprocess pipes, queues, cancellation and measurement. Read
   [Phase 6](phases/PHASE_06_VOICE.md). Checkpoint: explain why first generated audio is
   different from sound reaching a listener, and why tools-on speech waits longer.
6. **Teach from evidence.** Choose an idea from [the content list](INSTAGRAM_CONTENT_IDEAS.md),
   reproduce it in a disposable environment and name its limitations. Explain it aloud
   without reading the implementation. Then change one assumption and predict the result.

For each module: read its tests first, trace one successful path, trace one failure,
rebuild a smaller version in a separate scratch project, then compare. Do not remove
production permission checks to simplify an exercise. Keep exercises out of the active
feature branch unless separately requested.

The [product roadmap](../ROADMAP.md) remains authoritative for development scope.
Phase 5 is deferred. Phase 6 implementation is present but awaits manual acceptance;
studying it does not close it or start Phase 7.


Phase 6 reliability study checkpoint: trace one rejected transcript from
[language_issue](../../backend/app/voice/language.py) through the CLI before chat. Explain
why selecting hi differs from detecting hi, and why script correctness is not meaning
correctness. Then trace a response-only repair and prove it cannot repeat a tool action.
Finally explain the difference between memory rejection, process exit and intentional
cleanup using [VoiceDiagnosticError](../../backend/app/voice/diagnostics.py), without guessing OOM.
