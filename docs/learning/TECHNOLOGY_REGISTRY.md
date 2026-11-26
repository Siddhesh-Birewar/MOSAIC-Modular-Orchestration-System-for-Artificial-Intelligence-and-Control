# Technology registry

Roles below are verified from source/configuration. Selection explanations come from
existing decisions or are reconstructed engineering explanations. Dependency ranges are
requirements, not proof of every installed version; see
[pyproject.toml](../../backend/pyproject.toml).

- **Python >=3.11:** backend and CLI language. Type hints describe interfaces; they do not
  replace runtime input validation. Standard library supplies SQLite, queues, subprocesses,
  JSON, paths, wave audio, UUIDs, locks and temporary files.
- **FastAPI >=0.115,<1:** HTTP routes/dependency injection in
  [main.py](../../backend/app/main.py). Makes API boundaries explicit; it does not make
  routes authenticated automatically.
- **Pydantic (through FastAPI):** request/tool schemas and bounds. See
  [schemas.py](../../backend/app/schemas.py) and
  [tool schemas](../../backend/app/tools/schemas.py). It checks data shape, not permission.
- **Uvicorn[standard] >=0.30,<1:** ASGI development server; `--env-file` loads local settings.
  ASGI connects asynchronous Python applications to an HTTP server. Bind to loopback.
- **HTTPX >=0.27,<1:** synchronous CLI and asynchronous Ollama HTTP streaming. Mock transports
  make protocol tests deterministic without loading a model.
- **Ollama:** local model runtime accessed through HTTP. Installed version was verified as
  0.40.16 during Phase 6 work. GPT-OSS 20B is default; Qwen3 8B is explicit optional routing.
  Neither model is bundled in Git. Thinking support is queried, not assumed.
- **psutil >=5.9,<8:** read-only CPU/RAM/disk/battery metrics and voice memory admission.
  Availability is a point-in-time observation, not reserved future memory.
- **SQLite/sqlite3:** standard-library embedded database, introduced Phase 4. Transactions,
  foreign keys and numbered schema migrations; no application-level encryption.
- **pytest >=8,<9:** deterministic tests and separately marked real-model integration.
  TestClient drives the API without starting a public service.
- **sounddevice >=0.5,<0.6 (optional voice extra):** PortAudio-backed microphone/output
  streams in [AudioDevice](../../scripts/voice.py). Needs OS permission/hardware; mocks do
  not test acoustic quality.
- **Whisper.cpp + multilingual Base:** local STT executable/weights, configured paths only.
  [WhisperCpp](../../backend/app/voice/providers.py) uses fixed arguments and private
  temporary audio. Current implementation launches it per transcription.
- **macOS say/afconvert:** installed native TTS/fallback in
  [MacOSTTS](../../backend/app/voice/providers.py). Avoids a new model; voice quality differs.
- **MLX Audio 0.6.8, MLX 0.32.5, Misaki 0.9.4:** verified existing neural environment,
  Python 3.12.16. MLX runs neural computation on Apple Silicon; MLX Audio integrates Kokoro;
  Misaki helps convert text into pronunciation units. Isolated worker avoids mixing them
  with the backend environment. These are observed versions, not backend dependencies.
- **Cached Kokoro-82M assets:** `mlx-community/Kokoro-82M-bf16`, cached revision
  `a71e4d38b236d968966a2002c4c895dbd12b1c3c`. Header contains 548 F32 tensors despite the
  repository name. English af_bella; Hindi/Hinglish hf_alpha. No conversion/download made.
- **Git/GitHub:** reproducible history, feature branches, draft PR gates and annotated
  milestones. A pushed branch does not imply its phase is accepted or released.

React/TypeScript/Tailwind/Tauri are dashboard plans/prototypes, not backend dependencies
or completed Phase 5. Vector retrieval, RAG and Phase 7 are not implemented here.


Reliability follow-up verified installed Whisper.cpp **1.9.6** and the existing Base file's
147,951,465-byte size/SHA-256 against its published pointer. The artifact is multilingual;
forced-language metadata does not prove independently detected language or correct script.
CPU/no-flash/greedy/prompt trials did not establish a reliable Hindi fix. No dependency/model
replacement was made. [Benchmark history](BENCHMARK_HISTORY.md) records the exact evidence.
The new script/diagnostic/recovery modules use only existing dependencies and stdlib.
