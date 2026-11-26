# Instagram content ideas

These are proposed educational pieces, not published posts or measured audience results.
Explain one concept per piece, show synthetic examples, and cite the source revision.
Review terminal screens for tokens, private paths, messages and database content before
recording. Do not show `.env`, personal chat history, recordings or audit records.

1. **A health check is not an AI test.** Trace `/health`, Ollama health and one mocked chat.
   Hook: “Which of these three checks actually runs inference?”
   [Phase 1 code](../../backend/app/api/health.py).
2. **Why an AI assistant has modules.** Walk from route to Ollama adapter. Show how a fake
   dependency lets a test run without a model. Avoid claiming this requires microservices.
3. **Streaming is more than printing tokens.** Animate JSONL → StreamEvent → SSE → CLI.
   Distinguish network chunks, tokens and sentences. [Phase 2 guide](phases/PHASE_02_INTELLIGENCE.md).
4. **Memory before a database.** Compare `git show v0.2.0:backend/app/conversations.py`
   with today's store. Explain context limits versus persistent history.
5. **The model proposes; the executor decides.** Demonstrate a fake tool with invalid
   arguments and a denied action. [ToolExecutor](../../backend/app/tools/executor.py).
6. **Why localhost still needs authentication.** Use controlled tests to contrast 401
   with a permitted request. Never display an actual token or teach bypassing policy.
7. **A path that looks safe may escape.** Use temporary directories/symlinks in tests to
   explain traversal and canonical paths. Keep security checks enabled.
8. **One approval cannot become permanent permission.** Explain expiry, argument digest
   and replay rejection with [approval tests](../../backend/tests/test_tools.py).
9. **Your note survives a restart: how?** Rebuild a tiny synthetic SQLite transaction.
   Explain stable IDs, timestamps and foreign keys. State that storage is unencrypted.
10. **Database memory is not model training.** Show explicit curated memory → keyword
    retrieval → untrusted prompt context. No weights change and no semantic search claim.
11. **Why I keep a speech model alive.** Contrast repeated startup work with a persistent
    worker conceptually; show actual measured cold/warm results with their conditions.
12. **An audio benchmark trap.** Compare first generated WAV with physical audible onset.
    Show [recorded values](BENCHMARK_HISTORY.md); mark audible timing “not measured.”
13. **Why my assistant sometimes waits before speaking.** Explain tools-on final speech
    versus explicit tool-free streaming. Demonstrate mocked rejection, not a real app launch.
14. **Hindi and English in one sentence.** Explain routing once per logical sentence before
    chunking. Include pronunciation/truncation limits; do not claim perfect multilingual AI.
15. **What RTF 0.2 actually means.** Compute generation/audio duration, then explain why
    it cannot promise a sub-three-second first response.
16. **A model named BF16 with F32 weights.** Explain metadata inspection and why a label
    is not proof of runtime precision. Do not silently convert shared cached models.
17. **The cancellation bug hiding behind a button.** Draw blocked receive → socket shutdown
    → queue cleanup. Separate the silent 0.050 s recovery probe from physical interruption.
18. **What a test result does not prove.** Use 116 deterministic tests, a separate real-model
    test and pending manual acceptance to explain three different kinds of evidence.

Before publication, reproduce the example, check the current symbol names and milestone
status, show units/sample limits for every performance claim, and disclose reconstructed
explanations. Phase 5 is deferred and Phase 6 is still under acceptance; neither is a
completed showcase release.
