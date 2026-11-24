# Proposed plugin interface

Plugins are a future extension point; no plugin loader is implemented. A plugin should declare a stable identifier, version, display name, required capabilities, and typed input/output schemas. The host validates manifests and requests, checks user-granted permissions for each invocation, applies time/resource limits, and records a content-free audit event.

Plugins must not receive ambient filesystem, network, or shell access. Capabilities are explicit, narrow, and revocable. MCP integrations use the same host permission boundary as native adapters. Errors are typed and must not expose secrets. Compatibility/versioning, packaging, and process isolation require a later design decision before implementation.
