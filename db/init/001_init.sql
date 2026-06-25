CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS policy_chunks (
    id BIGSERIAL PRIMARY KEY,
    chunk_id TEXT NOT NULL UNIQUE,
    document TEXT NOT NULL,
    section TEXT NOT NULL,
    text TEXT NOT NULL,
    embedding vector(768) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS policy_chunks_document_idx
ON policy_chunks (document);

CREATE INDEX IF NOT EXISTS policy_chunks_embedding_hnsw_idx
ON policy_chunks
USING hnsw (embedding vector_cosine_ops);
