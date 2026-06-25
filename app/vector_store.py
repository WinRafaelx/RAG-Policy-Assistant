from collections import Counter
from dataclasses import dataclass
import math
import re

from app.chunking import PolicyChunk


TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")
STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "before",
    "by",
    "for",
    "from",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
    "when",
    "where",
    "who",
    "with",
}


@dataclass(frozen=True)
class SearchResult:
    chunk: PolicyChunk
    score: float


class TfidfVectorStore:
    def __init__(self, chunks: list[PolicyChunk]) -> None:
        self._chunks = chunks
        self._doc_vectors: list[dict[str, float]] = []
        self._doc_norms: list[float] = []
        self._idf = self._build_idf(chunks)
        for chunk in chunks:
            vector = self._vectorize(chunk.text)
            self._doc_vectors.append(vector)
            self._doc_norms.append(_norm(vector))

    @property
    def chunks(self) -> list[PolicyChunk]:
        return list(self._chunks)

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        query_vector = self._vectorize(query)
        query_norm = _norm(query_vector)
        if query_norm == 0:
            return []

        results: list[SearchResult] = []
        for index, doc_vector in enumerate(self._doc_vectors):
            score = _cosine(query_vector, query_norm, doc_vector, self._doc_norms[index])
            if score > 0:
                results.append(SearchResult(self._chunks[index], score))

        return sorted(results, key=lambda item: item.score, reverse=True)[:top_k]

    def _build_idf(self, chunks: list[PolicyChunk]) -> dict[str, float]:
        document_frequency: Counter[str] = Counter()
        for chunk in chunks:
            document_frequency.update(set(tokenize(chunk.text)))

        total = max(len(chunks), 1)
        return {
            term: math.log((1 + total) / (1 + frequency)) + 1
            for term, frequency in document_frequency.items()
        }

    def _vectorize(self, text: str) -> dict[str, float]:
        tokens = tokenize(text)
        counts = Counter(tokens)
        if not counts:
            return {}
        total = sum(counts.values())
        return {
            term: (count / total) * self._idf.get(term, 1.0)
            for term, count in counts.items()
        }


def tokenize(text: str) -> list[str]:
    return [
        token.lower()
        for token in TOKEN_PATTERN.findall(text)
        if token.lower() not in STOP_WORDS and len(token) > 1
    ]


def _norm(vector: dict[str, float]) -> float:
    return math.sqrt(sum(value * value for value in vector.values()))


def _cosine(
    left: dict[str, float],
    left_norm: float,
    right: dict[str, float],
    right_norm: float,
) -> float:
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = sum(value * right.get(term, 0.0) for term, value in left.items())
    return dot / (left_norm * right_norm)
