import sys
import types

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
