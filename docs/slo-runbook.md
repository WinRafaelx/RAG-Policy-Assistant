# SLO And Runbook

## Service Targets

- Availability: `/health` returns `200` when the API can load the configured retrieval backend.
- Latency: local deterministic `/ask` responses should usually complete under 500 ms after startup in TF-IDF mode.
- Quality: eval gate should pass at least 90% grounded answers, 90% expected citation hits, 80% expected term hits, and 100% adversarial refusals.
- Safety: no raw PII should appear in answers after output guardrails.

## Common Operations

### Start Locally With Docker

```bash
docker compose up --build
```

### Run Tests

```bash
pytest --cov=app --cov-report=term-missing --cov-fail-under=80
python scripts/run_evaluation.py
```

### Check Metrics

```bash
curl http://127.0.0.1:8000/metrics
```

### Rebuild The pgvector Index

```bash
docker compose down -v
docker compose up --build
```

### Investigate Poor Answers

1. Check the response `telemetry.request_id`.
2. Find the matching structured log entry.
3. Review `retrieval_scores` and `citation_chunk_ids`.
4. Run `python scripts/run_evaluation.py`.
5. If a corpus change caused the issue, inspect chunking and expected source coverage.

### Investigate Refusals

1. Check `guardrails.reason`.
2. Confirm whether the request matches prompt injection, sensitive customer data, policy bypass, or low retrieval confidence.
3. Add a regression test if the refusal was incorrect.

### Investigate Traffic Spikes

1. Check `/metrics` request and refusal counts.
2. Review structured logs by `request_id`, backend, and refusal reason.
3. If local IP-based in-memory rate limiting is insufficient, move enforcement to authenticated identity plus an API gateway or shared store.

## References

- See [ADR-001: RAG Architecture](ADR-001-rag-architecture.md) for core pipeline and retrieval setup.
- See [ADR-002: Security Guardrail Layer](ADR-002-security-guardrail-layer.md) for detail on safety filters and injection protections.
- See [Threat Model](threat-model.md) for mapping security risks to pipeline controls.

