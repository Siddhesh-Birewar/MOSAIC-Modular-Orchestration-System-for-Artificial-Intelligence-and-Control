# Engineering instructions

- Keep MOSAIC local-first, modular, typed, and a modular monolith. Keep the backend independent of UI frameworks.
- Prefer Python standard library and existing dependencies; avoid cloud services, paid APIs, microservices, and premature features.
- Bind development services to localhost. Do not add unrestricted shell execution. Future tools require validation and explicit permission checks.
- Never commit credentials, private data, local databases, or `.env` files. Do not put prompts or personal data in logs.
- Do not download large models without explicit user approval.
- Preserve existing work, add focused tests for behavior, and update `docs/PROJECT_STATE.md` when implementation status changes.
- Use type hints, clear interfaces, and focused changes. Stop at the requested roadmap phase.
- Expose operating-system capabilities only through registered tools and `ToolExecutor`. Never pass arbitrary model text to a shell or executable.
- Keep filesystem authorization empty unless `MOSAIC_ALLOWED_ROOTS` explicitly lists narrow roots. Never grant the home directory or MOSAIC repository by default.
- Keep `MOSAIC_API_TOKEN` out of prompts, responses, logs, audit records, and Git. Application launches require a fresh user approval for each request.

## Permanent learning documentation

- MOSAIC is also the owner's long-term learning project. During every development phase, maintain `docs/learning/` in simple, technically accurate English, with links to actual source files, classes and functions.
- Keep `LEARNING_ROADMAP.md`, `DEVELOPMENT_JOURNAL.md`, `ARCHITECTURE_DECISIONS.md`, `TECHNOLOGY_REGISTRY.md`, `COMMAND_REFERENCE.md`, `ERRORS_AND_SOLUTIONS.md`, `BENCHMARK_HISTORY.md`, `CONCEPT_GLOSSARY.md`, `INSTAGRAM_CONTENT_IDEAS.md`, and the relevant `phases/` guide current as work progresses.
- Each phase guide must cover the 20 topics defined in `docs/learning/README.md`, including chronological implementation, alternatives/trade-offs, tests, security, actual measurements, Git evidence, rebuilding exercises and educational content ideas.
- Label verified historical facts, user-reported observations, reconstructed explanations and unmeasured/pending results separately. Cite repository revisions, tests or existing records; never invent past decisions, errors, experiments or benchmarks.
- Before milestone completion, verify learning-document coverage, source links/symbols, command context, measurement provenance, privacy and accurate phase status. Update learning records alongside implementation, not only at closeout. Never include credentials, private conversations, personal data or secrets.

## Mandatory Git and GitHub milestone workflow

After completing each development phase, coding agents must:

1. Run all relevant automated tests and verify that the phase acceptance criteria pass.
2. Obtain user confirmation for any outstanding manual verification before treating the phase as complete.
3. Update `docs/PROJECT_STATE.md`, `CHANGELOG.md`, `README.md`, and other relevant documentation with the actual implementation and verification status. Include and verify the learning records required above before completing the milestone.
4. Review `git status` and the full diff. Ensure credentials, API tokens, personal data, local databases, virtual environments, model weights, audit logs, `.env` files, and other sensitive configuration are not tracked.
5. Create a concise conventional commit for the completed phase.
6. Push the completed feature branch to the configured MOSAIC GitHub repository. This workflow authorizes routine milestone pushes; do not ask for repeated approval.
7. Merge the verified feature branch into `main` through a pull request or a safe fast-forward/merge. Respect branch protection and required checks; never bypass them.
8. Create and push an annotated milestone version tag after the merge. Verify the remote contains the expected commit and tag.
9. Create a new feature branch before beginning the next phase.

If manual verification is still outstanding, push the branch as work in progress but do not merge it or create a completion tag. Never force-push or overwrite unrelated changes. Do not merge when tests fail or a critical security issue is unresolved. If authentication, conflicts, or repository protections block progress, report the issue and do not attempt destructive recovery. Respect any approval requirements enforced by the execution environment.
