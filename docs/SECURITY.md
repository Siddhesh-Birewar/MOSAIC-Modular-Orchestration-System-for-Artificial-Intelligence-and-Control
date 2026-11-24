# Security

- Keep data and inference local wherever practical. Development API binds to loopback only.
- Never commit `.env`, credentials, personal data, or local databases. `.env.example` contains placeholders only.
- Do not log prompts, responses, document contents, credentials, or personal identifiers. Current logs record only service events.
- No shell or arbitrary code execution is provided. Every call passes through the registered tool executor, strict schema validation, default-deny permission checks, approval verification when required, bounded execution, output validation, and audit recording.
- System monitoring is explicitly read-only. Filesystem access is default-deny and requires explicit `MOSAIC_ALLOWED_ROOTS`; each path is checked canonically and opened component-by-component without following symlinks. Special files and sensitive names are denied. Reads are UTF-8 text only, max 256 KB; directory listing and filename search inspect at most 2,000 entries; tool results max 32 KB. No writes, deletes, moves, or renames are registered.
- Application launches use a fixed name-to-path allowlist, verify that the app exists, and require a fresh user approval per launch. The launcher uses fixed `/usr/bin/open` arguments and never invokes a shell.
- Tool invocation, approval, permission inspection, and audit endpoints require a locally configured bearer token of at least 32 characters. Model-selected tools are disabled unless the streaming request carries that token. The token is never placed in model context or audit records. The AI cannot call the approval endpoint or access the token.
- Approvals expire after 90 seconds, bind to conversation/tool/validated-argument digest, are single-use, and are revalidated before execution. Rejections and mismatches prevent execution.
- Audit events are structured, content-free, and bounded in memory (default 500 entries); they disappear on restart. They exclude raw arguments and file contents.
- Tool result text is untrusted and explicitly marked in the model context. Structured Ollama tool calls are the only accepted model tool requests; arbitrary prose is never interpreted as a command.
- These application checks are not equivalent to full operating-system sandbox isolation. A compromised backend process still has the permissions of its user account.
- Do not download large models without explicit user approval. Keep permissions visible and revocable through configuration and the authenticated API.
- Protect local data with least-privilege file access; document encryption and backup choices before persisting sensitive data.
