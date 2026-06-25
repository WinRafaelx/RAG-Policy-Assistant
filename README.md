# ttb Policy Assistant

Production-style take-home implementation of a small Retrieval-Augmented Generation service for synthetic bank policy questions.

## Scope

The exam brief referenced a provided synthetic policy corpus and evaluation set, but those files were not included in the folder. I created an obviously synthetic corpus in `policies/` and a reproducible evaluation set in `data/eval/`. No real customer, employee, bank-confidential data, or secrets are used.

The implementation is English-first because the brief did not explicitly require Thai-language support. The API and file handling are UTF-8 safe, so Thai input will not break request validation or JSON responses. A production Thai deployment would need Thai policy documents, Thai/English evals, multilingual retrieval evaluation, and Thai-specific PII review.

## Architecture

```text
Markdown policies
  -> section-aware chunking
  -> pure-Python TF-IDF vector store
  -> top-k retrieval
  -> deterministic grounded answer synthesis
  -> citations, guardrails, telemetry
  -> FastAPI POST /ask
```

The default mode is local and deterministic. It does not require OpenAI, Azure OpenAI, Azure AI Search, FAISS, or pgvector. This keeps the submission runnable on a clean machine without sharing private API keys.

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

Ask a question:

```bash
curl -X POST http://127.0.0.1:8000/ask ^
  -H "Content-Type: application/json" ^
  -d "{\"question\":\"How many annual leave days do full-time employees receive?\",\"top_k\":3}"
```

## Tests

```bash
pytest
```

The tests cover:

- Markdown chunking and metadata
- PII redaction
- prompt-injection refusal
- out-of-scope sensitive-data refusal
- `/ask` integration behavior
- request validation

## Evaluation Harness

```bash
python scripts/eval.py
```

The harness runs 10 grounded questions and 3 adversarial questions, then prints answer, citation, expected-term, and refusal counts. It is intentionally simple and reproducible rather than model-judge based.

## Docker

```bash
docker build -t ttb-policy-assistant .
docker run --rm -p 8000:8000 ttb-policy-assistant
```

## API

`POST /ask`

Request:

```json
{
  "question": "Can employees connect personal USB drives to bank devices?",
  "top_k": 3
}
```

Response:

```json
{
  "success": true,
  "answer": "...",
  "citations": [
    {
      "document": "policy_07_it_acceptable_use.md",
      "chunk_id": "policy_07_it_acceptable_use.md:004",
      "section": "4. External Storage and Media Restrictions"
    }
  ],
  "guardrails": {
    "redacted_input": false,
    "redacted_output": false,
    "refused": false,
    "reason": null
  },
  "telemetry": {
    "request_id": "...",
    "latency_ms": 1,
    "input_tokens": 9,
    "output_tokens": 44,
    "retrieved_chunks": 3
  }
}
```

## Guardrails

Implemented guardrails:

- Redacts common emails, Thai-style phone numbers, and long account-like numbers.
- Refuses prompt-injection requests such as revealing hidden/system prompts.
- Refuses customer-specific account or balance questions.
- Refuses requests to bypass approval or policy controls.
- Refuses when retrieval confidence is below the configured threshold.
- Logs redacted request metadata rather than raw sensitive values.

## Observability

The service writes structured JSON logs for refusals and completed requests, including:

- request ID
- latency
- estimated input/output token counts
- retrieved chunk count
- refusal status and reason

## Secrets and AI Providers

No API keys are required. No secrets are committed.

Optional provider variables are documented in `.env.example` for future use only:

```text
OPENAI_API_KEY
AZURE_OPENAI_API_KEY
AZURE_OPENAI_ENDPOINT
AZURE_OPENAI_DEPLOYMENT
```

If real LLM generation were added, the retrieval and guardrail layers would remain outside the model call, and the model would receive only redacted input plus retrieved policy context.

## Trade-Offs

- Used TF-IDF retrieval instead of Azure AI Search, pgvector, or FAISS to keep setup reliable and local.
- Used deterministic answer synthesis instead of external LLM calls so the project can be evaluated without private keys.
- Implemented a lightweight eval harness with citation and term checks instead of an LLM judge.
- Kept Thai support to UTF-8 compatibility only because full bilingual retrieval was not required by the brief.

## What I Would Do With More Time

- Add Azure AI Search or pgvector indexing behind the same retrieval interface.
- Add optional OpenAI/Azure OpenAI answer generation with strict context-only prompting.
- Add Thai and bilingual corpora, Thai PII patterns, and multilingual embedding evaluation.
- Add CI with tests, coverage, linting, and dependency audit.
- Add an ADR, threat model, SLOs, and operational runbook.
- Add request rate limiting and authentication for a deployed internal service.

## AI-Assisted Development Disclosure

AI assistance was used to help plan the implementation, draft synthetic evaluation questions, and scaffold code and documentation. All content is synthetic and reviewed for the take-home scope. No real secrets or confidential bank data were shared.
"# RAG-Policy-Assistant" 
