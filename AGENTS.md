# Engineering instructions

- Keep MOSAIC local-first, modular, typed, and a modular monolith. Keep the backend independent of UI frameworks.
- Prefer Python standard library and existing dependencies; avoid cloud services, paid APIs, microservices, and premature features.
- Bind development services to localhost. Do not add unrestricted shell execution. Future tools require validation and explicit permission checks.
- Never commit credentials, private data, local databases, or `.env` files. Do not put prompts or personal data in logs.
- Do not download large models without explicit user approval.
- Preserve existing work, add focused tests for behavior, and update `docs/PROJECT_STATE.md` when implementation status changes.
- Use type hints, clear interfaces, and focused changes. Stop at the requested roadmap phase.

## Mandatory Git and GitHub milestone workflow

After completing each development phase, coding agents must:

1. Run all relevant automated tests and verify that the phase acceptance criteria pass.
2. Obtain user confirmation for any outstanding manual verification before treating the phase as complete.
3. Update `docs/PROJECT_STATE.md`, `CHANGELOG.md`, `README.md`, and other relevant documentation with the actual implementation and verification status.
4. Review `git status` and the full diff. Ensure credentials, API tokens, personal data, local databases, virtual environments, model weights, audit logs, `.env` files, and other sensitive configuration are not tracked.
5. Create a concise conventional commit for the completed phase.
6. Push the completed feature branch to the configured MOSAIC GitHub repository. This workflow authorizes routine milestone pushes; do not ask for repeated approval.
7. Merge the verified feature branch into `main` through a pull request or a safe fast-forward/merge. Respect branch protection and required checks; never bypass them.
8. Create and push an annotated milestone version tag after the merge. Verify the remote contains the expected commit and tag.
9. Create a new feature branch before beginning the next phase.

If manual verification is still outstanding, push the branch as work in progress but do not merge it or create a completion tag. Never force-push or overwrite unrelated changes. Do not merge when tests fail or a critical security issue is unresolved. If authentication, conflicts, or repository protections block progress, report the issue and do not attempt destructive recovery. Respect any approval requirements enforced by the execution environment.
