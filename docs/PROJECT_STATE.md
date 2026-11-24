# Project state

## Current phase
Phase 3 — Safe Tool Execution and Interactive CLI is complete. Phase 4 — Persistent Memory is next and has not started.

## Phase 3 implementation
- Registered read-only system monitoring, explicitly rooted filesystem reads, and allowlisted macOS application launching.
- Tool calls use strict schemas, default-deny permission checks, bounded execution/results, authenticated local endpoints, one-time argument-bound approvals, and content-free bounded audit records.
- Ollama structured calls are collected across streamed chunks and passed through the same validated executor. Model prose is never executable.
- The interactive CLI supports streaming, conversations, approval prompts, and the documented slash commands.

## Phase 3 verification
- User reports successful manual verification of authenticated tool calls, battery and RAM monitoring, authorized file reads, app launch after explicit approval, rejection handling, and denial of a non-allowlisted application.
- Deterministic backend tests verify unauthenticated/out-of-root reads, `..` traversal, symlink escapes, sensitive paths, and bounded file access; these do not depend on LLM behavior.
- Streaming regression tests verify tool calls arriving before the final Ollama chunk are retained and repeated final snapshots do not duplicate a call.
- Live localhost checks previously passed for seven read-only system tools and a streamed CLI chat using local Ollama.
- Automated suite: `backend/.venv/bin/python -m pytest -q` — 42 passed, with one Starlette/httpx deprecation warning.
- Compile check: `backend/.venv/bin/python -m compileall -q backend/app scripts` — passed. `git diff --check` — passed.

## Security and platform notes
- Filesystem access remains default-deny. Configure only narrow roots in ignored `.env`; no writes or deletes are registered.
- On macOS, `/tmp` commonly resolves to `/private/tmp`. A `/tmp/...` spelling may be rejected if the allowed root is configured as `/private/tmp/...`; configure and request paths using their canonical spelling. Do not weaken canonical-path or no-follow checks.
- Application launch remains fixed to installed allowlisted apps and requires a separate user approval each time.
- Conversations and audit history are in memory and are discarded when the backend restarts.

## Phase 4
Create `feature/phase-4-persistent-memory` from the synchronized `main` branch after Phase 3 is merged and tagged. Do not implement Phase 4 as part of this closeout.
