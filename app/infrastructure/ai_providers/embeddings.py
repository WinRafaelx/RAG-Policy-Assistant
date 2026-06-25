from typing import Protocol


class EmbeddingProvider(Protocol):
    dimension: int

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        ...

    def embed_query(self, text: str) -> list[float]:
        ...


class SentenceTransformerEmbeddingProvider:
    def __init__(self, model_name: str) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        self._model_name = model_name
        model = SentenceTransformer(model_name)
        # Dynamic quantization to 8-bit integers for CPU memory and speed optimization
        self._model = torch.quantization.quantize_dynamic(
            model, {torch.nn.Linear}, dtype=torch.qint8
        )
        self.dimension = self._model.get_sentence_embedding_dimension()

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        prepared_texts = [self._prepare_passage(text) for text in texts]
        embeddings = self._model.encode(
            prepared_texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype("float32").tolist()

    def embed_query(self, text: str) -> list[float]:
        embeddings = self._model.encode(
            [self._prepare_query(text)],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.astype("float32").tolist()[0]

    def _prepare_passage(self, text: str) -> str:
        if self._uses_e5_prefixes():
            return f"passage: {text}"
        return text

    def _prepare_query(self, text: str) -> str:
        if self._uses_e5_prefixes():
            return f"query: {text}"
        return text

    def _uses_e5_prefixes(self) -> bool:
        return "e5" in self._model_name.lower()
