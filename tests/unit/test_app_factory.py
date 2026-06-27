import pytest

from app.core.config import Settings
from app.main import build_retrieval_store, create_app


class WrongDimensionEmbeddingProvider:
    dimension = 2

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]

    def embed_query(self, text: str) -> list[float]:
        return [1.0, 0.0]


def test_pgvector_backend_requires_database_url() -> None:
    settings = Settings(retrieval_backend="pgvector", database_url=None)

    with pytest.raises(RuntimeError, match="TTB_DATABASE_URL is required"):
        build_retrieval_store(settings)


def test_pgvector_backend_rejects_embedding_dimension_mismatch() -> None:
    settings = Settings(
        retrieval_backend="pgvector",
        database_url="postgresql://example",
        embedding_dimension=768,
    )

    with pytest.raises(RuntimeError, match="Embedding model dimension 2 does not match"):
        build_retrieval_store(settings, WrongDimensionEmbeddingProvider())


def test_openapi_schema_includes_ask_request_example() -> None:
    app = create_app(
        Settings(prompt_injection_model="test-model"),
        warmup_guardrails=False,
    )

    schema = app.openapi()

    assert schema["components"]["schemas"]["AskRequest"]["example"] == {
        "question": "string",
        "top_k": 3,
        "llm_provider": None,
    }
    assert schema["paths"]["/ask"]["post"]["requestBody"]["content"]["application/json"][
        "example"
    ] == {
        "question": "string",
        "top_k": 3,
        "llm_provider": None,
    }
