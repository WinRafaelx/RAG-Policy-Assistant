from dataclasses import dataclass
from typing import Protocol

from app.chunking import PolicyChunk


@dataclass(frozen=True)
class SearchResult:
    chunk: PolicyChunk
    score: float


class RetrievalStore(Protocol):
    @property
    def chunks(self) -> list[PolicyChunk]:
        ...

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        ...
