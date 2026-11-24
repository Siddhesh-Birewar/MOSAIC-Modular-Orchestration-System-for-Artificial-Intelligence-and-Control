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

The API exposes `GET /health`, `GET /health/ollama`, `GET /models`, and `POST /chat`.
Run checks from the `backend/` directory with `pytest`.
