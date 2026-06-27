import sys
import types

import numpy as np

from app.infrastructure.ai_providers.embeddings import SentenceTransformerEmbeddingProvider


class FakeSentenceTransformer:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name

    def get_sentence_embedding_dimension(self) -> int:
        return 768


def test_sentence_transformer_provider_falls_back_when_quantization_fails(monkeypatch) -> None:
    fake_torch = types.SimpleNamespace(
        nn=types.SimpleNamespace(Linear=object),
        qint8=object(),
        quantization=types.SimpleNamespace(
            quantize_dynamic=lambda model, modules, dtype: (_ for _ in ()).throw(
                RuntimeError("quantized linear prepack unavailable")
            )
        ),
    )
    fake_sentence_transformers = types.SimpleNamespace(
        SentenceTransformer=FakeSentenceTransformer,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)

    provider = SentenceTransformerEmbeddingProvider("intfloat/multilingual-e5-base")

    assert provider.dimension == 768
    assert isinstance(provider._model, FakeSentenceTransformer)


class EncodingSentenceTransformer:
    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.calls: list[dict[str, object]] = []

    def get_sentence_embedding_dimension(self) -> int:
        return 2

    def encode(self, texts, **kwargs):
        self.calls.append({"texts": texts, "kwargs": kwargs})
        return np.array([[1.0, 0.0] for _ in texts])


def test_e5_provider_prefixes_passages_and_queries_and_normalizes(monkeypatch) -> None:
    fake_torch = types.SimpleNamespace(
        nn=types.SimpleNamespace(Linear=object),
        qint8=object(),
        quantization=types.SimpleNamespace(quantize_dynamic=lambda model, modules, dtype: model),
    )
    fake_sentence_transformers = types.SimpleNamespace(
        SentenceTransformer=EncodingSentenceTransformer,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)

    provider = SentenceTransformerEmbeddingProvider("intfloat/multilingual-e5-base")
    text_embeddings = provider.embed_texts(["Annual leave policy"])
    query_embedding = provider.embed_query("How many vacation days?")

    assert text_embeddings == [[1.0, 0.0]]
    assert query_embedding == [1.0, 0.0]
    assert provider._model.calls[0]["texts"] == ["passage: Annual leave policy"]
    assert provider._model.calls[1]["texts"] == ["query: How many vacation days?"]
    assert provider._model.calls[0]["kwargs"]["normalize_embeddings"] is True
    assert provider._model.calls[0]["kwargs"]["convert_to_numpy"] is True
    assert provider._model.calls[0]["kwargs"]["show_progress_bar"] is False


def test_non_e5_provider_does_not_add_e5_prefixes(monkeypatch) -> None:
    fake_torch = types.SimpleNamespace(
        nn=types.SimpleNamespace(Linear=object),
        qint8=object(),
        quantization=types.SimpleNamespace(quantize_dynamic=lambda model, modules, dtype: model),
    )
    fake_sentence_transformers = types.SimpleNamespace(
        SentenceTransformer=EncodingSentenceTransformer,
    )
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "sentence_transformers", fake_sentence_transformers)

    provider = SentenceTransformerEmbeddingProvider("sentence-transformers/all-MiniLM-L6-v2")
    provider.embed_texts(["Annual leave policy"])
    provider.embed_query("How many vacation days?")

    assert provider._model.calls[0]["texts"] == ["Annual leave policy"]
    assert provider._model.calls[1]["texts"] == ["How many vacation days?"]
