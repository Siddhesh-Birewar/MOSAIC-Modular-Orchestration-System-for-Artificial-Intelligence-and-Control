# MOSAIC

Modular Orchestration System for Artificial Intelligence and Control.

A local-first personal AI assistant.

Development status: Phase 6 local voice intelligence in progress. Phase 5 dashboard/humanoid is deferred. Latest stable milestone: v0.4.0 (30%).

## Learn the codebase

The [learning documentation](docs/learning/README.md) provides a study roadmap,
evidence-backed guides to Phases 1–4 and active Phase 6, source/function references,
commands, troubleshooting, benchmark history, rebuilding exercises and educational
content ideas. Historical facts and reconstructed explanations are labeled separately.
These records are maintained during every future development phase and verified at
milestone closeout. They do not change pending acceptance or release status.

## Backend quick start

From the repository root, create an isolated environment and install the backend:

```sh
python3 -m venv backend/.venv
source backend/.venv/bin/activate
python -m pip install -e 'backend[dev]'
```

Copy `.env.example` to `.env` to override local Ollama settings. Then run the API:

```sh
cd backend
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

If the backend virtual environment is active, `uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000` is equivalent. In either case, run from `backend/` so `--env-file ../.env` resolves to the repository-root configuration.

The API exposes health and model discovery endpoints, persistent conversation management,
`POST /chat`, and `POST /chat/stream` (SSE). See `docs/ARCHITECTURE.md` for route and
configuration details. Set `MOSAIC_API_TOKEN` in `.env` before using personal or chat
endpoints; those routes require bearer authentication.

## Local persistence

Phase 4 stores conversations, notes, learning records, and curated memories in SQLite.
`MOSAIC_DB_PATH` optionally selects the database file. The default is outside the
repository: `~/Library/Application Support/MOSAIC/mosaic.sqlite3` on macOS,
`~/.local/share/MOSAIC/mosaic.sqlite3` on Linux, and `%LOCALAPPDATA%/MOSAIC/mosaic.sqlite3`
on Windows. The database directory and file use restrictive permissions where supported;
SQLite foreign keys and transactional versioned migrations are enabled. `.gitignore`
excludes database files and SQLite sidecars.

Back up the database only while MOSAIC is stopped, or use SQLite's online backup API; do
not copy a live database file without accounting for journal state. The database contains
personal conversation and note content, so protect backups like the original. Verify
restart persistence locally by creating a conversation or note, stopping the backend,
restarting it with the same `MOSAIC_DB_PATH`, and fetching that record using the bearer
token. Do not use real personal content in automated tests.

Manual verification on macOS confirmed bearer authentication (unauthenticated personal
requests return 401), note creation (201), stable note UUID/content/timestamps after restart,
ordered conversation history after restart, curated memory recall in a fresh conversation,
and learning topic status/progress persistence. Invalid subject IDs return 404.
Phase 4 closed with 53 passing tests. SQLite remains unencrypted at rest; memory retrieval uses
keywords only. Run one backend worker: inference and conversation mutations share a
process-local lock. Access logging is suppressed to keep personal URL search terms out of logs.

## Interactive CLI and safe tools

Create `.env` from `.env.example`, set `MOSAIC_API_TOKEN` to a locally generated random
value of at least 32 characters, and start the backend with `--env-file ../.env` from
`backend/`. The token is required for conversations, chat, notes, learning, memories, tool
invocation, approvals, permission inspection, and audit history. The CLI supplies it to
personal routes and model-selected tools. Keep the token only in local
configuration; it is never included in prompts or logs.

Generate a token locally with `python -c 'import secrets; print(secrets.token_urlsafe(32))'`
and place it in the ignored `.env` file. Export `.env` values in the shell before starting
the CLI:

```sh
set -a
source .env
set +a
```

Filesystem tools are disabled until `MOSAIC_ALLOWED_ROOTS` names specific directories.
Do not use the whole home folder or this repository as a default. Values are separated by
the platform path separator. On macOS, `/tmp` commonly resolves to `/private/tmp`; use the
canonical path (for example, inspect it with `pwd -P`) consistently in both the allowed
root and tool request. MOSAIC may reject a `/tmp/...` spelling when the configured root
is `/private/tmp/...`; do not disable canonical-path or no-follow checks to work around
this. Reads are UTF-8 text only, bounded to 256 KB; directory listings and searches inspect
at most 2,000 entries, and tool results are capped at 32 KB. No write or delete operation exists. Application launches are
allowlisted and require a separate CLI approval each time.

Run the terminal client from the repository root:

```sh
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

The CLI supports `/help`, `/new`, `/clear`, `/models`, `/model MODEL`, `/status`,
`/metrics`, and `/exit`. The model can use registered structured tools only when the CLI
provides the local bearer token. Prose is never parsed as an executable command.

Run checks from the `backend/` directory with `.venv/bin/python -m pytest`. To deliberately compare the
installed models, start the API and run `python scripts/benchmark_models.py` from the
repository root. This makes ten model inferences by default and is not run automatically;
use `--model qwen3:8b` to limit the run.

## Neural voice CLI (Phase 6 draft)

Phase 5 dashboard/humanoid remains deferred. The existing isolated `mosaic-voice` environment
runs a persistent offline Kokoro worker; backend dependencies remain isolated. English uses
af_bella; Hindi/Hinglish use hf_alpha. Installed macOS TTS remains explicitly selectable.
Do not reinstall packages or download the already cached model unnecessarily. The cached
repository name includes BF16 but its weight header is F32; status reports runtime dtypes.

See [docs/VOICE.md](docs/VOICE.md) for verified environments, cache resolution, IPC/lifecycle
limits, exact configuration, benchmarks and manual acceptance. Start the backend using the
existing command above (`--env-file ../.env`), export `.env` locally and run:

```sh
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

Use `/tts kokoro` to warm the engine, `/voice-status`, `/voices`, `/mic [INDEX]`, `/voice`,
`/voice on`, `/voice off`, `/language auto|en|hi|hinglish`, `/speed 0.5–2`,
`/reasoning default|low|medium|high`, `/voice-tools on|off`, and `/tts macos`.
`/transcript-preview on|off` optionally displays recognized text locally and asks for
confirmation; it is off by default and creates no additional persistent log. Hindi and
Hinglish force Whisper's Hindi argument. Wrong/unsupported scripts stop before chat;
the existing Base/runtime still failed synthetic Hindi quality checks. Explicit response
language settings override old conversation preferences; one bounded tool-free correction
may repair unspoken response text without repeating actions or adding history turns.
Ctrl+C interrupts; the microphone closes during responses. Tools stay on by default and
speech waits for completed orchestration. Explicit tools-off mode streams eligible speech
segments while the model generates; synthesis/playback queues are bounded and ordered.
Existing text commands, persisted history and typed approvals are preserved.

The reliability update passes 160 deterministic tests; the separately identified real-model
integration also passes. Worker failures now expose safe categories/stages/exit codes or
memory counters while retaining memory limits. New VAD defaults are 0.010 / 2.0 seconds;
existing `.env` overrides are preserved. First-audio metrics now follow actual output-stream
start rather than staying null. See the voice guide for clock boundaries and retest commands.

Earlier short warm neural synthesis measured 0.130–0.171 s;
concurrent synthesis measured 0.596–0.875 s. The earlier live HTTP probe reached generated audio in
4.074 s, which misses the ideal three-second target even before playback. Actual audible
latency and sustained concurrency require manual acceptance. No acoustic barge-in or
phoneme/viseme alignment is claimed. The PR stays draft and stable release stays v0.4.0.
