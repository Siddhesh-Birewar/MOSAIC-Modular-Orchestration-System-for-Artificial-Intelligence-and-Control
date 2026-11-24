# Architecture decisions

- **Modular monolith:** one Python/FastAPI backend with clear modules avoids distributed complexity while preserving extension points.
- **Local Ollama HTTP adapter:** isolates runtime API details and keeps inference local; URL and model are configurable.
- **SQLite planned, not yet added:** suitable for local persistence, but Phase 1 has no data model or migration needs.
- **Independent frontend:** React/TypeScript and eventual Tauri client communicate through the API rather than importing backend code.
- **Permission gate before tools:** integrations must validate and authorize every action; unrestricted shell execution is excluded.
- **Environment config and private logs:** avoids hard-coded machine-specific settings and prevents user content from entering logs.
