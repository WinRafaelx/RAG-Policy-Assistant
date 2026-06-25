# Threat Model

## Assets

- Synthetic policy corpus and embeddings.
- Staff questions submitted to `/ask`.
- Logs and telemetry.
- Optional provider configuration and database credentials.

## Main Risks And Controls

| Risk | Control |
| --- | --- |
| Prompt injection asks for hidden prompts or rule overrides | Regex refusal before retrieval, context-only system prompt for optional LLM generation, adversarial eval questions |
| Customer-specific account or balance lookup | Sensitive out-of-scope refusal before retrieval |
| PII in user input or generated output | Input and output redaction for emails, phones, Thai ID-like values, labeled IDs, long numbers, and card-like numbers |
| Sensitive values in logs | Structured logs use request metadata, refusal reason, chunk IDs, scores, and token counts rather than raw questions |
| Poisoned or misleading policy chunks | Synthetic corpus only for take-home; production needs source review, document signing, ingestion audit logs, and rollback |
| Dependency or model supply-chain issue | Pin dependencies, run CI, and add dependency audit before production |
| Expensive abuse of `/ask` | Add rate limiting and authentication before external deployment |

## Out Of Scope For This Take-Home

- Real bank data.
- Customer account systems.
- Authentication and authorization.
- Production secret manager integration.
