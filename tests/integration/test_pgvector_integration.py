import os
from uuid import uuid4

import pytest

from app.domain.services.chunking import PolicyChunk
from app.infrastructure.databases.vector.pgvector import PgVectorStore


class FakeEmbeddingProvider:
    dimension = 768

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embedding_for(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embedding_for(text)

    def _embedding_for(self, text: str) -> list[float]:
        embedding = [0.0] * self.dimension
        lowered = text.lower()
        if "annual" in lowered or "leave" in lowered:
            embedding[0] = 1.0
        elif "usb" in lowered or "device" in lowered:
            embedding[1] = 1.0
        else:
            embedding[2] = 1.0
        return embedding


@pytest.mark.integration
def test_pgvector_store_upserts_and_searches_chunks() -> None:
    database_url = os.getenv("TTB_TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TTB_TEST_DATABASE_URL not configured")

    suffix = uuid4().hex
    chunks = [
        PolicyChunk(
            chunk_id=f"test-{suffix}:annual",
            document=f"test-{suffix}-annual.md",
            section="Annual Leave",
            text="Full-time employees receive annual leave each year.",
        ),
        PolicyChunk(
            chunk_id=f"test-{suffix}:usb",
            document=f"test-{suffix}-usb.md",
            section="IT Acceptable Use",
            text="Personal USB drives must not be connected to bank devices.",
        ),
    ]
    store = PgVectorStore(database_url, FakeEmbeddingProvider())

    try:
        assert store.upsert_chunks(chunks) == 2

        results = store.search("Can I use a USB device?", top_k=2)

        assert results
        assert results[0].chunk.chunk_id == f"test-{suffix}:usb"
        assert results[0].score > results[1].score
    finally:
        _delete_test_chunks(database_url, suffix)


def _delete_test_chunks(database_url: str, suffix: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as conn:
        conn.execute("DELETE FROM policy_chunks WHERE chunk_id LIKE %s", (f"test-{suffix}:%",))
        conn.commit()
