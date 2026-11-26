# Phase 3 — Safe tool execution and interactive CLI

**Status:** complete, v0.3.0 (20%). **Historical evidence:** `eda3d14`, `687feb0`,
tagged project state and PR #2. Reconstructed 2026-11-26. Teaching rationale/comparisons
are reconstructed unless already recorded in the decision log.

## 1. Problem

An LLM's text cannot safely be treated as a command. Reading a file or launching an app
needs a deterministic boundary independent of what the model says.

## 2. Why it is necessary

Useful local assistance needs narrowly defined OS capabilities and visible consent.
Typed tools make inputs, outputs, risk and permissions inspectable. A terminal client
lets the owner test orchestration and approve specific actions before a dashboard exists.

## 3. Prerequisites

Phases 1–2; schemas, authentication/authorization, filesystem roots and symlinks, file
descriptors, async timeouts, hashes, expiring state, SSE and mock-based security tests.

## 4. Technologies

Pydantic strict schemas, standard-library filesystem/process APIs, psutil monitoring,
fixed macOS `/usr/bin/open`, HTTPX CLI and Ollama structured tool calls. No shell execution
framework or cloud service is introduced.

## 5. Selection rationale

**Recorded:** default-deny permissions, no default allowed roots, fresh app-launch
approval, bounded content-free audit and one executor for all tools. Fixed arguments
avoid interpreting generated text as shell syntax. psutil exposes read-only system facts.

## 6. Alternatives and trade-offs

**Reconstructed:** arbitrary shell tools are flexible but expose uncontrolled authority.
Prose-based parsing is ambiguous; structured calls still need schema validation. Blanket
approval is simpler but loses per-request consent. A full OS sandbox is stronger isolation
but not what these application checks provide. The audit ring deliberately loses history
on restart to avoid silently creating durable sensitive records.

## 7. Architecture and flow

Authenticated request/model structured call → registry → strict input validation →
permission decision → approval if required → bounded execution → output validation/size
cap → content-free audit → untrusted result supplied to model → final answer.
An approval request is a pending state, not execution success.

## 8. Algorithms and mathematics

Approvals bind conversation ID, tool ID and a digest of validated arguments; expire after
90 seconds and are consumed once. A digest checks identity, not user intent by itself.
File paths are checked against explicit roots and opened component-by-component with
no-follow behavior. Sensitive names, special files and oversized content are denied.
Streaming calls are accumulated across chunks; known index/ID fragments merge, repeated
snapshots do not duplicate values. Output and iteration/time budgets bound work.

## 9. Chronological implementation

**Git facts:** `eda3d14` added registry, permissions, approvals, tools, orchestration and
CLI. `687feb0` fixed streamed call retention and added deterministic security verification
before merge. **Reconstructed within the first commit:** define contracts, implement
executor/policy, add bounded tools/APIs, connect streaming and CLI, add tests/docs. No
finer edit chronology is asserted.

## 10. Important code

- [base.py](../../../backend/app/tools/base.py): `Tool`, `ToolContext`, risk/manifest contract.
- [registry.py](../../../backend/app/tools/registry.py): `ToolRegistry` rejects duplicate IDs.
- [executor.py](../../../backend/app/tools/executor.py): `ToolExecutor.invoke` is the boundary.
- [permissions.py](../../../backend/app/security/permissions.py): `PermissionManager.evaluate`.
- [approvals.py](../../../backend/app/security/approvals.py): `ApprovalManager.create/consume`.
- [files.py](../../../backend/app/tools/builtin/files.py): `FileAccess` checks/opens/reads.
- [applications.py](../../../backend/app/tools/builtin/applications.py): `LaunchApplicationTool`.
- [tools.py](../../../backend/app/api/tools.py): `require_local_token`, invocation/decision API.
- [chat.py](../../../scripts/chat.py): `MosaicCLI.send_message`, `_handle_approval`, `parse_sse`.

## 11. Communication

The model proposes structured tool calls over Ollama streaming. FastAPI invokes Python
tool objects; direct API calls use the same executor. The CLI receives an approval event,
asks the human and sends a separate authenticated decision. The model has neither token
nor approval API access in its prompt. Tool results are labeled untrusted model context.

## 12. Commands

Start backend and CLI with [the exact env-file commands](../COMMAND_REFERENCE.md).
`/help`, `/models`, `/model MODEL`, `/new`, `/clear`, `/status`, `/metrics`, `/exit`
control the text client. From root, run targeted checks:

```sh
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q backend/tests/test_tools.py backend/tests/test_ollama_client.py
```

For authorized scratch paths on macOS, `pwd -P` reveals canonical spelling. Do not
configure the repository or entire home as an allowed root to simplify a demo.

## 13. Errors and solutions

**Historical fix:** calls in earlier Ollama chunks could be lost by final-chunk-only
handling; `687feb0` accumulates them and merges identified fragments. Tests cover early
calls, repeated final snapshots and distinct calls. **Documented limitation:** `/tmp`
may fail where canonical `/private/tmp` works; use canonical paths, preserving no-follow
checks. See [error record](../ERRORS_AND_SOLUTIONS.md).

## 14. Performance evidence

Tagged state records live checks for seven read-only system tools and streamed CLI chat.
These establish functionality, not controlled latency. No tool performance benchmark is
recorded. Bounds include 256 KB text reads, 2,000 inspected directory entries and 32 KB
tool results. Limits are security/resource policy, not measured speed claims.

## 15. Security

Bearer authentication is separate from permission/approval. Unauthorized/out-of-root,
`..`, symlink, sensitive and special-file attempts must fail deterministically. No write,
delete or arbitrary command tool exists. Fixed installed app allowlist plus fresh approval
is required per launch. Audit excludes raw arguments/file content and has bounded capacity.
These checks are not equivalent to restricting a compromised backend's OS permissions.

## 16. Testing

**Historical closeout:** 42 passed; compile and diff checks passed. Owner confirmed tool
auth, battery/RAM, allowed file read, approved launch, rejection and non-allowlisted denial.
`test_file_read_api_enforces_root_traversal_and_symlink_boundaries` in
[test_tools.py](../../../backend/tests/test_tools.py) uses temporary paths and direct API
calls, not LLM refusals. Approval expiry/replay/argument-change and fixed launch arguments
are tested with mocks. [Stream tests](../../../backend/tests/test_ollama_client.py) verify
call retention independently of inference.

## 17. Git milestones

Feature `eda3d14` → closeout `687feb0` → [PR #2](https://github.com/Siddhesh-Birewar/MOSAIC-Modular-Orchestration-System-for-Artificial-Intelligence-and-Control/pull/2)
merge `459ae9c`, annotated v0.3.0. Cumulative roadmap 20%. Manual evidence was accepted
before the milestone; this does not pre-approve future app launches.

## 18. Limitations

At this tag conversations and audit were volatile. Tools are intentionally read-only
except approved app launching; no filesystem writes. Canonical-path spelling may surprise
users. The model may fail to choose a tool; backend authorization remains deterministic.

## 19. Rebuild exercises

Build a fake read-only tool with a strict integer input and bounded output. Reject unknown
fields. Use temporary directories to test allowed reads, traversal and symlink escape.
Implement one-use argument-bound approvals for a mocked action; change one argument and
show rejection. Never launch a real application or weaken roots for this exercise.

## 20. Educational content

Teach “the model proposes, the executor authorizes,” show a deterministic traversal test,
or illustrate why an old approval cannot be replayed. Use synthetic paths and mocked
actions; never show a token, actual file contents or personal audit history.
