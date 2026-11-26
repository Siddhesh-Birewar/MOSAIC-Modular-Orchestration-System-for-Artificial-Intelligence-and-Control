# Security

- Keep data and inference local wherever practical. Development API binds to loopback only.
- Never commit `.env`, credentials, personal data, or local databases. `.env.example` contains placeholders only.
- Do not log prompts, responses, document contents, credentials, or personal identifiers. Current logs record only service events.
- No shell or arbitrary code execution is provided. Every call passes through the registered tool executor, strict schema validation, default-deny permission checks, approval verification when required, bounded execution, output validation, and audit recording.
- System monitoring is explicitly read-only. Filesystem access is default-deny and requires explicit `MOSAIC_ALLOWED_ROOTS`; each path is checked canonically and opened component-by-component without following symlinks. Special files and sensitive names are denied. Reads are UTF-8 text only, max 256 KB; directory listing and filename search inspect at most 2,000 entries; tool results max 32 KB. No writes, deletes, moves, or renames are registered.
- On macOS, `/tmp` commonly resolves to `/private/tmp`. A path spelled under `/tmp` may not match an allowlisted canonical path under `/private/tmp`; configure and use the canonical spelling (for example, check with `pwd -P`). This path-resolution behavior is intentional; do not weaken canonical or no-follow checks to accept alternate spellings.
- Application launches use a fixed name-to-path allowlist, verify that the app exists, and require a fresh user approval per launch. The launcher uses fixed `/usr/bin/open` arguments and never invokes a shell.
- Tool invocation, approval, permission inspection, and audit endpoints require a locally configured bearer token of at least 32 characters. Model-selected tools are disabled unless the streaming request carries that token. The token is never placed in model context or audit records. The AI cannot call the approval endpoint or access the token.
- Approvals expire after 90 seconds, bind to conversation/tool/validated-argument digest, are single-use, and are revalidated before execution. Rejections and mismatches prevent execution.
- Audit events are structured, content-free, and bounded in memory (default 500 entries); they disappear on restart. They exclude raw arguments and file contents.
- Tool result text is untrusted and explicitly marked in the model context. Structured Ollama tool calls are the only accepted model tool requests; arbitrary prose is never interpreted as a command.
- Streamed Ollama assistant content and tool calls are accumulated across chunks; partial calls are merged only when Ollama supplies a matching call index or ID. The assembled structured call is still schema-validated before execution, and reasoning fields remain private.
- These application checks are not equivalent to full operating-system sandbox isolation. A compromised backend process still has the permissions of its user account.
- Do not download large models without explicit user approval. Keep permissions visible and revocable through configuration and the authenticated API.
- Protect local data with least-privilege file access; document encryption and backup choices before persisting sensitive data.
- Phase 4's SQLite database contains personal conversations, notes, learning records, and curated memories. It defaults outside the repository, uses restrictive permissions where supported, and never stores API tokens. Backups must receive the same protection; stop the application or use SQLite's backup API for consistent copies. Database encryption at rest is not currently provided.
- Conversation, chat, notes, learning, and memory endpoints require the configured bearer token. Memories are created only through explicit user-facing API requests; retrieval is bounded and labeled untrusted context. Conversation logs are not automatically promoted into memory.

- Phase 4 closeout verified authentication, restart persistence, curated memory recall, learning integrity, and safe reset behavior. Transport/access URL logging is disabled and validation responses omit submitted input. SQLite integrity conflicts return a generic 409 response. The API/package release version is 0.4.0.

- Phase 6 speech endpoints require bearer authentication. Voice clients accept only loopback
  backend URLs. Audio requests are capped at 2 MB/30 seconds, mono 16 kHz 16-bit PCM; speech
  text is capped at 1,000 characters per API call. Replies are capped to 12,000 spoken characters.
- Recording is opt-in, continuous capture requires `/voice on`, and the microphone closes
  while thinking/speaking. Ctrl+C cancels active work and returns to text. Speech never bypasses
  tool policy: application launches still need a typed user approval through the existing API.
- Raw microphone data lives in client memory and briefly in a private provider temporary
  directory; cleanup runs on success/failure/cancellation. No audio is stored in SQLite. OS
  caches/swap and abnormal process termination may leave traces; deletion is not secure erasure.
- Speech executables/model paths come only from local trusted configuration, never requests
  or model output. Fixed arguments use no shell; TTS text uses stdin. Temporary results and
  provider errors are sanitized; personal audio/text is not logged. No models download on startup.

- Neural voice upgrade: private worker pipes use bounded validated messages and matching IDs. The neural process inherits no API tokens, denies network connections, and uses verified local assets. Model/voice paths are trusted configuration, not request arguments. No shell execution is introduced. Library/native stdout/stderr is suppressed to avoid private text leakage.
- Neural synthesis is serialized with bounded admission, restart/time limits, cancellation/reaping and idle/memory-aware release. A per-model user lock prevents duplicate workers; no unrelated user processes are terminated. Native fallback must be explicitly enabled and is visibly labeled.
- Speech events are separate from text tokens. Tool-enabled turns speak only the final completed iteration; failed/denied tools use deterministic noncompletion speech. Explicit tool-free streaming disables actual tools. Hidden reasoning, provisional tool prefatory text and raw tool JSON are excluded from speech.
- Voice script mismatches cannot silently become model input: the CLI rejects invalid recognition before chat. Optional preview/confirmation is local and off by default; terminal scrollback can retain its text. API clients receive validation metadata and must honor it. Accepted messages retain the existing SQLite policy; no additional transcript log is introduced.
- Response-language recovery uses at most one bounded tools-disabled rewrite of unspoken text. It never invokes tools/approval decisions again or writes another conversation turn. Original text stays unchanged; rewrite fluency/factual equivalence is not guaranteed by alphabet checks. Unsupported scripts are denied in the neural provider and worker.
- Neural diagnostics expose fixed categories/stages and numeric counters only, never provider exception text, request fields, audio or credentials. Deliberate cleanup reason is separate from observed exit codes. A signal alone cannot prove an OOM. Memory admission limits remain enabled; a rejected queued request cannot terminate another request's worker.
- Authenticated UUID-scoped voice cancellation stops only matching provider operations. Mic capture remains half-duplex and explicitly activated. OS swap may contain traces; IPC/audio cleanup is not secure erasure. MLX allocation, RSS and system memory pressure measure different things.
