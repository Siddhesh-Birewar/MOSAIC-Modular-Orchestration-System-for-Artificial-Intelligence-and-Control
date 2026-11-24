# MOSAIC

Modular Orchestration System for Artificial Intelligence and Control.

A local-first personal AI assistant.

Development status: Phase 1 — Project foundation.

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
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

The API exposes health and model discovery endpoints, in-memory conversation management,
`POST /chat`, and `POST /chat/stream` (SSE). See `docs/ARCHITECTURE.md` for route and
configuration details. Conversations are lost when the backend restarts; SQLite belongs
to Phase 4.

Run checks from the `backend/` directory with `pytest`. To deliberately compare the
installed models, start the API and run `python scripts/benchmark_models.py` from the
repository root. This makes ten model inferences by default and is not run automatically;
use `--model qwen3:8b` to limit the run.
