# Architecture

MOSAIC starts as a local-first modular monolith. The FastAPI backend owns configuration, API boundaries, model/runtime adapters, and later domain modules for memory, notes, learning, knowledge, projects, and integrations. Typed interfaces keep those modules replaceable without adding service boundaries prematurely.

The React/TypeScript/Tailwind dashboard and Tauri shell are separate clients of the backend; no UI code belongs in backend modules. SQLite is the planned local persistence layer. Ollama is accessed through a narrow HTTP adapter so runtime details do not leak into domain logic. Plugin/MCP adapters will enter through a validated host interface. Services bind to localhost during development.

Phase 1 implements only health, model discovery, and a single-turn chat boundary. It has no persistence, tools, or frontend.
