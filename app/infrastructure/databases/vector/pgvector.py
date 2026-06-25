from collections.abc import Sequence
from pathlib import Path
import time

from app.domain.services.chunking import PolicyChunk, load_policy_chunks
from app.infrastructure.ai_providers.embeddings import EmbeddingProvider
from app.infrastructure.databases.vector.base import SearchResult


SCHEMA_SQL = """
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
"""


class PgVectorStore:
    def __init__(
        self,
        database_url: str,
        embedding_provider: EmbeddingProvider,
        connect_retries: int = 20,
        retry_seconds: float = 1.0,
    ) -> None:
        self._database_url = database_url
        self._embedding_provider = embedding_provider
        self._connect_retries = connect_retries
        self._retry_seconds = retry_seconds
        self._ensure_schema()

    @property
    def chunks(self) -> list[PolicyChunk]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT chunk_id, document, section, text
                FROM policy_chunks
                ORDER BY document, chunk_id
                """
            ).fetchall()
        return [
            PolicyChunk(
                chunk_id=row["chunk_id"],
                document=row["document"],
                section=row["section"],
                text=row["text"],
            )
            for row in rows
        ]

    def count_chunks(self) -> int:
        with self._connect() as conn:
            row = conn.execute("SELECT COUNT(*) AS count FROM policy_chunks").fetchone()
            return _read_count(row)

    def count_documents(self) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(DISTINCT document) AS count FROM policy_chunks"
            ).fetchone()
            return _read_count(row)

    def bootstrap_if_empty(self, policies_dir: Path) -> int:
        if self.count_chunks() > 0:
            return 0
        chunks = load_policy_chunks(policies_dir)
        return self.upsert_chunks(chunks)

    def upsert_chunks(self, chunks: Sequence[PolicyChunk]) -> int:
        if not chunks:
            return 0

        texts = [chunk.text for chunk in chunks]
        embeddings = self._embedding_provider.embed_texts(texts)
        if any(len(embedding) != self._embedding_provider.dimension for embedding in embeddings):
            raise ValueError("Embedding dimension mismatch")

        rows = [
            (
                chunk.chunk_id,
                chunk.document,
                chunk.section,
                chunk.text,
                self._to_numpy_vector(embedding),
            )
            for chunk, embedding in zip(chunks, embeddings)
        ]

        with self._connect() as conn:
            with conn.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO policy_chunks (chunk_id, document, section, text, embedding)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        document = EXCLUDED.document,
                        section = EXCLUDED.section,
                        text = EXCLUDED.text,
                        embedding = EXCLUDED.embedding,
                        updated_at = now()
                    """,
                    rows,
                )
            conn.commit()
        return len(rows)

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        embedding = self._to_numpy_vector(self._embedding_provider.embed_query(query))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT
                    chunk_id,
                    document,
                    section,
                    text,
                    1 - (embedding <=> %s) AS score
                FROM policy_chunks
                ORDER BY embedding <=> %s
                LIMIT %s
                """,
                (embedding, embedding, top_k),
            ).fetchall()

        return [
            SearchResult(
                chunk=PolicyChunk(
                    chunk_id=row["chunk_id"],
                    document=row["document"],
                    section=row["section"],
                    text=row["text"],
                ),
                score=float(row["score"]),
            )
            for row in rows
        ]

    def _ensure_schema(self) -> None:
        with self._connect(register_vectors=False) as conn:
            conn.execute(SCHEMA_SQL)
            conn.commit()

    def _connect(self, register_vectors: bool = True):
        import psycopg
        from pgvector.psycopg import register_vector
        from psycopg.rows import dict_row

        last_error: Exception | None = None
        for _ in range(self._connect_retries):
            try:
                conn = psycopg.connect(self._database_url, row_factory=dict_row)
                if register_vectors:
                    register_vector(conn)
                return conn
            except Exception as error:
                last_error = error
                time.sleep(self._retry_seconds)
        raise RuntimeError("Could not connect to pgvector database") from last_error

    def _to_numpy_vector(self, embedding: list[float]):
        import numpy as np

        return np.array(embedding, dtype=np.float32)


def _read_count(row) -> int:
    if isinstance(row, dict):
        return int(row["count"])
    return int(row[0])
