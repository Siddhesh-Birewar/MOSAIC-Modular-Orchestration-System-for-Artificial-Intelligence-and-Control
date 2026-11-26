# Command reference

Commands below describe the current branch. Run from the repository root unless stated
otherwise. They are instructions for deliberate use, not a record that every command ran.
Use existing environments where available; do not reinstall packages or download weights
just to read this guide. Never paste secret-bearing output into documentation or videos.

## Setup and start

For a new backend environment only:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -e 'backend[dev]'
```

The environment isolates packages; editable installation uses the checked-out source.
Review [`.env.example`](../../.env.example) and create private `.env` locally. Keep its
token/paths out of Git. Add optional audio packages only when needed; reuse the separately
configured neural environment. See [VOICE.md](../VOICE.md) for actual voice prerequisites.

From **backend/**, load private configuration and bind only to this computer:

```sh
.venv/bin/uvicorn app.main:app --env-file ../.env --host 127.0.0.1 --port 8000
```

`app.main:app` selects the application object. The env-file path is relative to this
directory. One backend worker is required by process-local inference coordination.
`curl http://127.0.0.1:8000/health` checks backend health; it does not prove model readiness.

In a second terminal from the **repository root**:

```sh
set -a
source .env
set +a
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

`set -a` exports sourced values for the CLI's environment. Source only your trusted local
file: a shell-sourced file can execute code. Never use `cat .env` in recorded demos.

Text commands include `/help`, `/new`, `/clear`, `/model MODEL`, `/models`, `/metrics` and
`/exit`; read [MosaicCLI.command](../../scripts/chat.py) for exact argument handling.
Voice: `/tts kokoro`, `/voice-status`, `/voices`, `/mic`, `/mic INDEX`, `/language auto`,
`/language en|hi|hinglish`, `/speed 1`, `/reasoning low`, `/voice-tools off`, `/voice`,
`/voice on`, `/voice off`. Enter each separately; `|` here means choose one value.
`/voice-tools on` restores safe tool turns and typed approvals. Ctrl+C cancels active voice
work. Tool-free mode supports earlier speech but cannot execute tools.

## Verification

```sh
backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q
backend/.venv/bin/python -m compileall -q backend/app scripts
git diff --check
```

Pytest exercises behavior; compileall compiles Python to bytecode without executing
imports or proving runtime correctness. `git diff --check` catches whitespace errors. The explicit config
selects the intended test path and integration marker. For existing cached neural assets:

```sh
MOSAIC_TEST_NEURAL=1 backend/.venv/bin/python -m pytest -c backend/pyproject.toml -q -m integration
```

This loads a real model and consumes memory. It is separate from deterministic tests.
Neural-interpreter syntax check (when that configured interpreter exists):

```sh
/opt/anaconda3/envs/mosaic-voice/bin/python -m py_compile backend/app/voice/neural_worker.py
```

## Optional experiments

```sh
backend/.venv/bin/python scripts/benchmark_models.py --help
backend/.venv/bin/python scripts/benchmark_voice.py --help
backend/.venv/bin/python scripts/benchmark_neural_voice.py --llm
backend/.venv/bin/python scripts/benchmark_neural_voice.py --cold-start --skip-stt
```

`--llm` performs real concurrent inference. These experiments are opt-in and do not
measure physical audible onset. Use [benchmark history](BENCHMARK_HISTORY.md) to interpret
cache, memory and cold/warm effects before comparing numbers.

## Inspect history safely

```sh
git status --short --branch
git diff --stat
git diff
git log --oneline --decorate -12
git show v0.2.0:docs/PROJECT_STATE.md
git show v0.2.0:backend/app/conversations.py
git tag -n
git ls-remote origin refs/heads/feature/phase-6-voice-intelligence
```

These inspect work/history without resetting files. `git fetch origin` refreshes remote
references without merging. Review tracked paths with `git ls-files`; ignored files can
still be tracked if previously added. Follow [AGENTS.md](../../AGENTS.md) for commits,
pushes, merges and tags. Phase 6 must remain draft until manual acceptance.


## Voice reliability follow-up

After exporting trusted `.env` values in the CLI terminal, these override capture defaults
without editing the file:

```sh
export MOSAIC_VAD_THRESHOLD=0.010
export MOSAIC_VAD_SILENCE_SECONDS=2.0
export MOSAIC_TRANSCRIPT_PREVIEW=0
backend/.venv/bin/python scripts/chat.py --backend http://127.0.0.1:8000
```

Use `/transcript-preview on` for local recognized-text display and confirmation; turn it
off with `/transcript-preview off`. Invalid scripts remain rejected even with preview.
`/language hi` and `/language hinglish` both force Whisper hi; `/language auto` detects.
Preview is terminal-visible and may remain in scrollback, but creates no additional log.

```sh
backend/.venv/bin/python scripts/benchmark_neural_voice.py --llm --language-check --stress-rounds 4
```

This uses cached synthetic speech and existing Base, prints script counts without transcript
contents, and runs 12 mixed TTS requests with partial short-LLM overlap. It does not open
hardware, test full wall-time playback or establish accuracy. See [VOICE.md](../VOICE.md)
for the exact manual sequence, metric clocks and safe diagnostic fields to report.
