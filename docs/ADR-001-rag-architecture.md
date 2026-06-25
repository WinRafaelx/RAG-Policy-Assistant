# ADR-001: RAG Architecture

## Status

Accepted.

## Context

The take-home requires a small policy assistant that can run on a clean machine, answer from synthetic policy documents, cite sources, and avoid reliance on private cloud keys.

## Decision

Use FastAPI for the HTTP API, section-aware Markdown chunking, E5-compatible embeddings, PostgreSQL with pgvector for the production-style vector store, and a deterministic extractive generator as the default answer path. Keep TF-IDF retrieval as a local fallback for fast tests and offline debugging.

## Rationale

- pgvector keeps chunk text, metadata, and embeddings in one operational datastore.
- `intfloat/multilingual-e5-base` is retrieval-oriented and supports future Thai/English work.
- Deterministic generation makes the take-home reproducible when Azure OpenAI or other provider keys are unavailable.
- Optional Ollama support demonstrates the provider boundary without requiring secrets.

## Consequences

- The default answer path is more conservative than a hosted LLM and may sound less natural.
- Production deployment should add managed secrets, identity-aware authentication, distributed rate limiting, and a monitored LLM provider.
- Retrieval quality must be protected by the eval harness because corpus changes can alter relevance.
