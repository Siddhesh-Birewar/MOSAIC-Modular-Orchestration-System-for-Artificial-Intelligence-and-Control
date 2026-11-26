# Learn MOSAIC

MOSAIC is both a local AI assistant and a project you can study and rebuild. Start with
[the learning roadmap](LEARNING_ROADMAP.md), then read a phase guide with the code open.
You do not need to understand every library before beginning.

## Evidence and honesty

This directory was first reconstructed on **2026-11-26**, during Phase 6. It is not a
diary written during Phases 1–4. Historical evidence comes from tagged source,
`docs/PROJECT_STATE.md` at each tag, commit diffs and PRs #1–4. Current source references
describe the Phase 6 branch; use `git show TAG:path` when studying an older implementation.
For example, today's conversation store uses SQLite; Phase 2 used memory only.

Labels used throughout:

- **Historical fact:** supported by a named commit, tag, test record or merged PR.
- **User-reported:** a manual observation recorded by the owner; not an automated rerun.
- **Reconstructed explanation:** a teaching explanation inferred from source behavior.
  It is not a claim about what the developer thought or tried at that time.
- **Current verification:** a check actually executed during this documentation update.
- **Pending / not measured:** evidence is absent or acceptance is outstanding.

Do not treat test counts as coverage percentages. A mocked test verifies controlled
behavior; it does not establish model accuracy, audible quality or hardware performance.
Benchmark numbers are samples with conditions, not promises.

## Records

- [Learning roadmap](LEARNING_ROADMAP.md): study order and exercises.
- [Development journal](DEVELOPMENT_JOURNAL.md): evidence-backed chronology.
- [Architecture decisions](ARCHITECTURE_DECISIONS.md): reasons and trade-offs.
- [Technology registry](TECHNOLOGY_REGISTRY.md): each dependency's role.
- [Command reference](COMMAND_REFERENCE.md): commands, directories and effects.
- [Errors and solutions](ERRORS_AND_SOLUTIONS.md): diagnosed defects and unknown causes.
- [Benchmark history](BENCHMARK_HISTORY.md): measured results and missing measurements.
- [Concept glossary](CONCEPT_GLOSSARY.md): terms connected to the implementation.
- [Instagram content ideas](INSTAGRAM_CONTENT_IDEAS.md): accurate teaching/demo prompts.

## Phase guides and status

- [Phase 1: foundation](phases/PHASE_01_FOUNDATION.md) — complete, v0.1.0, 5% roadmap.
- [Phase 2: intelligence](phases/PHASE_02_INTELLIGENCE.md) — complete, v0.2.0, 12%.
- [Phase 3: safe tools](phases/PHASE_03_SAFE_TOOLS.md) — complete, v0.3.0, 20%.
- [Phase 4: persistence](phases/PHASE_04_PERSISTENCE.md) — complete, v0.4.0, 30%.
- Phase 5 dashboard/humanoid — deferred; no completion claimed.
- [Phase 6: voice](phases/PHASE_06_VOICE.md) — active draft PR #4; manual acceptance pending.

Latest completed cumulative milestone remains **30%**. Phase 7 has not started.

## Required phase coverage and review

Every guide uses these 20 numbered subjects: problem, necessity, prerequisites,
technologies, selection rationale, alternatives/trade-offs, architecture/data flow,
algorithms/mathematics, chronological implementation, important code, communication,
commands, errors/root causes/solutions, performance experiments, security, testing,
Git milestones, limitations, rebuilding exercises, and educational content.

Before a milestone, check all 20 subjects, verify local links and named symbols against
the intended revision, verify command working directories, and attach evidence to test
and performance claims. Review for secrets/private content. Keep incomplete acceptance
items visible. Learning documentation supplements the existing milestone workflow;
it never authorizes a merge or changes phase completion by itself.


The Phase 6 reliability follow-up adds measured failed Hindi-recognition trials, safe
structured diagnostics, bounded response-only correction, VAD/metric explanations and
new rebuilding exercises. The original intermittent worker stop remains unconfirmed;
Hindi recognition accuracy and physical/sustained use still block acceptance.
