# Project state

## Current phase
Phase 3 — safe tool execution and interactive CLI is implemented and under verification. Phase 3 is **not complete**. Phase 1 and Phase 2 are complete.

## Completed phases
- Phase 1: local FastAPI foundation, configuration, health/model endpoints, and initial tests. User manually verified a live chat request.
- Phase 2: bounded conversations, model selection, streaming, metrics, safe model management, and benchmark utility. Automated and live checks passed.

## Phase 3 implementation status
- Added registered system, filesystem, and application tools, typed permission policy, authenticated tool/approval/audit APIs, one-time argument-bound approvals, and bounded content-free audit history.
- Filesystem access defaults to no roots. Configured roots use canonical and descriptor checks, reject symlink traversal and sensitive paths, and enforce file/result bounds. There are no filesystem write or delete tools.
- Application launch is allowlisted and requires explicit approval for every request. No application was launched during development verification.
- Added structured Ollama tool-call handling with validated schemas, authenticated tool-enabled streaming, bounded tool orchestration, and untrusted-result handling.
- Added `scripts/chat.py` with conversation management, streaming, approval prompts, and the documented CLI commands.
- Updated `AGENTS.md`, README, architecture, security, decisions, roadmap, and changelog for the new phase and permanent Git/GitHub milestone workflow.

## Verification completed
- Automated tests: `cd backend && .venv/bin/python -m pytest -q` — 38 passed; one Starlette/httpx deprecation warning.
- `backend/.venv/bin/python -m compileall -q backend/app scripts` — passed.
- `git diff --check` — passed at the last test run; rerun after documentation edits.
- Live localhost API check: seven read-only tools (CPU, memory, battery, disk, macOS version, uptime, and Ollama models) returned HTTP 200. No personal files or applications were accessed/launched.
- Live CLI check through the backend virtual environment completed successfully and streamed a response from local `gpt-oss:20b`. The first attempt with system Python lacked `httpx`; rerunning with the project environment passed.

## Manual verification still required
Before Phase 3 can be marked complete, the user must perform and report these checks:
1. Set a strong `MOSAIC_API_TOKEN` (at least 32 characters) and a narrow temporary `MOSAIC_ALLOWED_ROOTS` directory in local `.env`; keep both out of Git.
2. Verify the CLI/model can read a harmless file inside that root and that a path outside the root is denied.
3. Choose an installed app from `MOSAIC_ALLOWED_APPLICATIONS`; request its launch through MOSAIC and reject the first approval, confirming it does not launch.
4. Make a separate request and approve once, confirming only the selected allowlisted app launches.
5. Report the results so acceptance can be reviewed. Until then, keep this as a work-in-progress feature branch; do not merge or create a Phase 3 milestone tag.

## Known limitations
- Conversations and audit events are in memory and disappear when the backend restarts; persistent storage is a later phase.
- Inference and model changes are serialized within one backend process.
- `psutil` may report unavailable values when the operating system denies access; that should be surfaced as unavailable rather than treated as an authorization bypass.
- Manual filesystem boundary and application approval checks above remain outstanding.

## Branch and next step
- Phase 3 branch: `feature/phase-3-safe-tools`.
- Push the reviewed implementation as work in progress and open a draft PR. Do not merge or tag until the manual checks above are confirmed and all acceptance criteria pass.
- After Phase 3 closeout, create a new feature branch before starting Phase 4.
