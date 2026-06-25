# SLO And Runbook

## Service Targets

- Availability: `/health` returns `200` when the API can load the configured retrieval backend.
- Latency: local deterministic `/ask` responses should usually complete under 500 ms after startup in TF-IDF mode.
- Quality: eval gate should pass at least 9/10 grounded answers, 9/10 expected citation hits, 8/10 expected term hits, and 3/3 adversarial refusals.
- Safety: no raw PII should appear in answers after output guardrails.

## Common Operations

### Start Locally With Docker

```bash
docker compose up --build
```

### Run Tests

```bash
pytest
python scripts/eval.py
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
4. Run `python scripts/eval.py`.
5. If a corpus change caused the issue, inspect chunking and expected source coverage.

### Investigate Refusals

1. Check `guardrails.reason`.
2. Confirm whether the request matches prompt injection, sensitive customer data, policy bypass, or low retrieval confidence.
3. Add a regression test if the refusal was incorrect.
