import os
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.core.config import Settings
from app.domain.services.chunking import PolicyChunk
from app.domain.services.guardrails import (
    GuardrailService,
    RegexPiiRedactor,
    RuleBasedPromptInjectionDetector,
)
from app.infrastructure.databases.vector.pgvector import PgVectorStore
from app.main import create_app


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


class UniqueMarkerEmbeddingProvider:
    dimension = 768

    def __init__(self, marker: str) -> None:
        self._marker = marker.lower()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [self._embedding_for(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embedding_for(text)

    def _embedding_for(self, text: str) -> list[float]:
        embedding = [0.0] * self.dimension
        lowered = text.lower()
        if self._marker in lowered:
            embedding[0] = 1.0
        elif "usb" in lowered or "device" in lowered:
            embedding[1] = 1.0
        else:
            embedding[2] = 1.0
        return embedding


@pytest.mark.integration
def test_pgvector_store_upserts_and_searches_chunks() -> None:
    database_url = _require_test_database_url()

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


@pytest.mark.integration
def test_ask_api_uses_pgvector_retrieval_backend() -> None:
    database_url = _require_test_database_url()

    suffix = uuid4().hex
    marker = f"marker-{suffix}"
    chunks = [
        PolicyChunk(
            chunk_id=f"test-{suffix}:annual",
            document=f"test-{suffix}-annual.md",
            section="Annual Leave",
            text=(
                f"Full-time employees receive 22 business days of annual leave each year. "
                f"Reference marker: {marker}."
            ),
        ),
        PolicyChunk(
            chunk_id=f"test-{suffix}:usb",
            document=f"test-{suffix}-usb.md",
            section="IT Acceptable Use",
            text="Personal USB drives must not be connected to bank devices.",
        ),
    ]
    store = PgVectorStore(database_url, UniqueMarkerEmbeddingProvider(marker))

    try:
        assert store.upsert_chunks(chunks) == 2
        app = create_app(
            Settings(
                retrieval_backend="pgvector",
                database_url=database_url,
                prompt_injection_model="test-model",
            ),
            retrieval_store=store,
            guardrail_service_override=GuardrailService(
                RegexPiiRedactor(),
                RuleBasedPromptInjectionDetector(),
                0.75,
            ),
            warmup_guardrails=False,
        )
        app.state.services.guardrails_ready = True
        client = TestClient(app)

        health = client.get("/health")
        assert health.status_code == 200
        assert health.json()["retrieval_backend"] == "pgvector"

        answer = client.post(
            "/ask",
            json={
                "question": f"How many annual leave days do employees receive for {marker}?",
                "top_k": 1,
            },
        )

        assert answer.status_code == 200
        body = answer.json()
        assert body["success"] is True
        assert body["guardrails"]["refused"] is False
        assert "22 business days" in body["answer"]
        assert body["citations"][0]["chunk_id"] == f"test-{suffix}:annual"
    finally:
        _delete_test_chunks(database_url, suffix)


def _delete_test_chunks(database_url: str, suffix: str) -> None:
    import psycopg

    with psycopg.connect(database_url) as conn:
        conn.execute("DELETE FROM policy_chunks WHERE chunk_id LIKE %s", (f"test-{suffix}:%",))
        conn.commit()


def _require_test_database_url() -> str:
    database_url = os.getenv("TTB_TEST_DATABASE_URL")
    if database_url:
        return database_url
    if os.getenv("GITHUB_ACTIONS"):
        pytest.fail("TTB_TEST_DATABASE_URL must be configured in CI")
    pytest.skip("TTB_TEST_DATABASE_URL not configured")
