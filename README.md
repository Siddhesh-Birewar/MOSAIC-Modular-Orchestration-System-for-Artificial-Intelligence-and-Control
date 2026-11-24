# MOSAIC

Modular Orchestration System for Artificial Intelligence and Control.

A local-first personal AI assistant.

Development status: Phase 3 — safe tools and terminal CLI in progress.

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

The API exposes health and model discovery endpoints, in-memory conversation management,
`POST /chat`, and `POST /chat/stream` (SSE). See `docs/ARCHITECTURE.md` for route and
configuration details. Conversations are lost when the backend restarts; SQLite belongs
to Phase 4.

## Interactive CLI and safe tools

Create `.env` from `.env.example`, set `MOSAIC_API_TOKEN` to a locally generated random
value of at least 32 characters, and start the backend with `--env-file ../.env` from
`backend/`. The token is required for tool invocation, approvals, permission inspection,
audit history, and for model-selected tools through the CLI. Keep the token only in local
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
