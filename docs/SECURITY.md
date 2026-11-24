# Security

- Keep data and inference local wherever practical. Development API binds to loopback only.
- Never commit `.env`, credentials, personal data, or local databases. `.env.example` contains placeholders only.
- Do not log prompts, responses, document contents, credentials, or personal identifiers. Current logs record only service events.
- No shell or arbitrary code execution is provided. Any future tool call must be schema-validated, permission-checked, and limited to the approved action before execution.
- Ask before downloading large models or pushing code. Keep permissions visible and revocable in the future dashboard.
- Protect local data with least-privilege file access; document encryption and backup choices before persisting sensitive data.
