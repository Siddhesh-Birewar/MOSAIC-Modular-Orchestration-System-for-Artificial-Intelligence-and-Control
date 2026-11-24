# Engineering instructions

- Keep MOSAIC local-first, modular, typed, and a modular monolith. Keep the backend independent of UI frameworks.
- Prefer Python standard library and existing dependencies; avoid cloud services, paid APIs, microservices, and premature features.
- Bind development services to localhost. Do not add unrestricted shell execution. Future tools require validation and explicit permission checks.
- Never commit credentials, private data, local databases, or `.env` files. Do not put prompts or personal data in logs.
- Do not download large models without explicit user approval. Do not push changes without approval.
- Preserve existing work, add focused tests for behavior, and update `docs/PROJECT_STATE.md` when implementation status changes.
- Use type hints, clear interfaces, and focused changes. Stop at the requested roadmap phase.
