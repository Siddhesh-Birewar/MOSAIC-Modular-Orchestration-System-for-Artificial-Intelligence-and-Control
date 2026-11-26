# Concept glossary

- **Modular monolith:** one deployed backend with separate internal modules.
  [main.py](../../backend/app/main.py) connects them.
- **API / HTTP:** a structured interface and request/response protocol. A route such as
  `/chat` is one entry point, not a model itself.
- **ASGI:** interface used by Uvicorn to run asynchronous FastAPI request handling.
- **Async/await:** lets a task yield while waiting for I/O. It does not automatically
  make CPU-heavy work parallel or safe to share.
- **Adapter / protocol:** code translating an external component into a narrow interface;
  [STTProvider/TTSProvider](../../backend/app/voice/providers.py) describe speech contracts.
- **Dependency injection:** supplying a dependency instead of constructing it everywhere;
  [create_app](../../backend/app/main.py) accepts test substitutes.
- **Token / context window:** model text units and the information available to inference.
  Message-count bounds in [context](../../backend/app/conversations.py) are not exact token bounds.
- **SSE:** named server-sent events over HTTP. [parse_sse](../../scripts/chat.py) reconstructs
  events; HTTP chunk boundaries are not necessarily sentence or tool-call boundaries.
- **Authentication / authorization:** proving access with a token versus deciding which
  action is allowed. A valid token alone does not authorize every filesystem path.
- **Schema validation:** checking fields/types/bounds before acting. See
  [StrictInput](../../backend/app/tools/schemas.py).
- **Prompt injection / untrusted context:** text may contain instructions that should not
  gain authority. Tool results and retrieved memories are data, not system instructions.
- **Canonical path / symlink:** the resolved path versus a filesystem reference to another
  path. [FileAccess](../../backend/app/tools/builtin/files.py) also opens without following
  symlinks; prefix text comparison alone cannot enforce a root.
- **TOCTOU:** time-of-check/time-of-use; a resource can change after validation.
  Descriptor-relative no-follow opens reduce filesystem races; they do not isolate the OS.
- **Digest / replay:** a hash binds approval to validated arguments; single-use expiry
  prevents reusing an old approval. See [ApprovalManager](../../backend/app/security/approvals.py).
- **Transaction / atomicity:** related database writes commit together or roll back.
  [append_turn](../../backend/app/conversations.py) stores user and assistant messages together.
- **Primary key / foreign key:** unique row identity and a checked relationship between
  tables. Cascading deletion removes dependent rows.
- **Migration:** a versioned schema change. [Database.migrate](../../backend/app/database.py)
  uses SQLite `user_version`; version 1 is current.
- **Parameterized SQL:** user values are bound separately from SQL instructions;
  [personal_data.py](../../backend/app/api/personal_data.py) uses `?` placeholders.
- **Keyword retrieval / RAG:** current curated memory uses lexical matching. A semantic
  document retrieval/generation system is later scope; keyword search is not embeddings.
- **PCM / sample rate:** digital amplitude samples and samples per second. Mono16k int16
  uses about 32,000 bytes/second before WAV headers.
- **RMS:** root mean square amplitude: sqrt(sum(x²)/N). Used for level/VAD events;
  [AudioDevice](../../scripts/voice.py) does not infer words from energy alone.
- **VAD / STT / TTS:** voice-activity detection, speech-to-text and text-to-speech.
  Silence detection, transcription and synthesis solve different problems.
- **Phoneme / viseme:** speech sound unit / visual mouth-shape unit. Actual aligned timings
  are unsupported and null; amplitude is not phoneme alignment.
- **IPC / JSONL:** inter-process communication / one JSON message per line. The neural
  worker uses private bounded pipes, not a new public HTTP service.
- **Backpressure:** a full bounded queue makes a producer wait or reject work instead of
  growing memory without limit. See [VoiceSession](../../scripts/voice.py).
- **Cancellation / half-duplex:** stop pending work and release resources / listen and
  speak at different times. Ctrl+C is supported; acoustic barge-in is not implemented.
- **Warm-up / RTF:** initialize lazy computation before serving / synthesis time divided
  by audio duration. Faster-than-real-time throughput can coexist with slow first audio.
- **F32 / BF16 / unified memory:** 32-bit float / 16-bit floating format / CPU and GPU share
  physical memory on this hardware. Repository names are not proof of actual tensor dtype.
- **RSS / MLX peak / swap:** process resident memory / MLX allocator peak / OS-backed memory
  moved to storage. They measure different things; see [benchmarks](BENCHMARK_HISTORY.md).
- **Regression test / integration test:** a controlled check for known behavior / a check
  involving real components. Mocked sound output cannot establish audible quality.
- **Commit / PR / annotated tag:** source snapshot / reviewable proposed merge / named
  milestone with metadata. Draft PR #4 is not a release; v0.4.0 remains latest complete.
