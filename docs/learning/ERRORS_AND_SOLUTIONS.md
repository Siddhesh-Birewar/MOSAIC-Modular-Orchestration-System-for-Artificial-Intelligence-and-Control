# Errors and solutions

This is an evidence-backed troubleshooting record, not a list of imagined incidents.
Historical entries are supported by tagged project state, PR descriptions and named fixes.
Explanations marked reconstructed describe why code works, not a witnessed old failure.

## Earlier Ollama HTTP 500 — cause unknown (Phase 1)

**Historical fact:** v0.1.0 project state records an earlier HTTP 500 followed by successful
user-verified GPT-OSS inference. **Root cause and specific fix: unknown.** Do not claim
restarting, changing a model or changing a timeout solved it. Current
[OllamaClient._request](../../backend/app/models/ollama_client.py) classifies transport,
timeout, malformed response and inference failures without returning private payloads.

## Tool calls dropped across chunks (Phase 3)

**Historical fact:** `687feb0`/PR #2 changed collection so calls arriving before `done`
are retained. Looking only at the final chunk loses earlier structured data. The client
now accumulates content/calls and merges identified fragments/snapshots by index or ID.
Calls without either remain separate; arbitrary prose is never parsed into execution.
Read [_merge_tool_value](../../backend/app/models/ollama_client.py) and
`test_stream_preserves_tool_calls_across_chunks_without_duplicates` in
[test_ollama_client.py](../../backend/tests/test_ollama_client.py).

## macOS /tmp spelling rejected (Phase 3 platform limitation)

**Documented behavior:** `/tmp` often resolves to `/private/tmp`. Mixing an alias with
a canonical allowlisted root can fail. Use `pwd -P` in a deliberately authorized scratch
directory and use that canonical spelling consistently. Do not disable no-follow checks
or broaden allowed roots. This is a documented boundary, not a security test failure.
See [FileAccess](../../backend/app/tools/builtin/files.py).

## Private error/log data and reset races (Phase 4)

**Historical fact:** `0f5f961`/PR #3 hardened URL access/transport logs, validation input
echoes and integrity errors. Search terms in URLs and invalid bodies can contain private
content even when the response fails. Current
[main.py](../../backend/app/main.py) suppresses those logs and sanitizes responses.

The same fix serialized reset/delete/model mutation with inference and refreshed queued
context. Otherwise an in-flight or queued turn could use stale pre-reset history or write
after reset. Read the lock boundaries in [intelligence.py](../../backend/app/api/intelligence.py)
and `test_reset_waits_for_inflight_turn_and_queued_chat_reads_latest_context` in
[test_persistence.py](../../backend/tests/test_persistence.py). No private failing input
is preserved in this record.

## Cached snapshot incomplete, required assets present (Phase 6)

**Recorded experiment:** whole-repository offline snapshot resolution failed because the
cached snapshot lacked 66 other files. Required weights/config/selected voices existed.
[cached_model](../../backend/app/voice/neural.py) validates the needed local files instead
of downloading the rest. Missing required files still fail closed; offline checks are not
removed. The BF16 repository label also differed from F32 weight metadata; report actual
loaded dtypes rather than silently converting shared assets.

## Hindi long text and unstable chunk routing (Phase 6)

**User-reported upstream warnings:** long-text truncation/chunking, mixed phonemes and
word counts. Short bounded segmentation mitigates these; it cannot promise perfect
pronunciation. **Verified fix `fd37407`:** route a logical sentence once before bounded
splitting, so an English-only chunk inside Hindi does not flip voices. Read
[Segmenter.feed_segments](../../backend/app/voice/text.py) and
`test_chunks_of_one_mixed_sentence_keep_the_same_voice_language` in
[test_neural_voice.py](../../backend/tests/test_neural_voice.py).

## Cancellation races (Phase 6, recorded silent HTTP experiments)

Closing a response from another thread left a blocked HTTP receive until keepalive
expired. [VoiceSession._reply](../../scripts/voice.py) now shuts down its own active
transport socket before closing, drains queues and refuses a new turn while old threads
are still releasing. Follow-up silent probe: 0.050 s join, zero remaining voice threads,
subsequent chat succeeded. This did not measure physical playback interruption.

A cancel could also arrive before synthesis registered its task. The API now remembers
cancelled session UUIDs for 60 seconds, bounded to 512, rejecting late work with 409.
Regression: `test_cancellation_before_synthesis_registration_prevents_late_work` in
[test_neural_voice.py](../../backend/tests/test_neural_voice.py).

Worker close also handles an idle task cancelled before it starts via cancellation-safe
gathering. Mock lifecycle tests cover orderly cleanup. Do not kill unrelated processes as
a workaround for a stuck adapter.

## Existing test warning (current)

The suite emits a Starlette/httpx deprecation warning. Tests pass; this warning is not
a benchmark or a claimed regression fix. Dependency maintenance should be evaluated
separately, without unrelated upgrades during phase documentation work.
