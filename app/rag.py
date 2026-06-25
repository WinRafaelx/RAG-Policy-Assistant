from dataclasses import dataclass
import re

from app.chunking import PolicyChunk
from app.guardrails import apply_output_guardrails, refusal_message
from app.schemas import Citation, GuardrailInfo
from app.vector_store import SearchResult, TfidfVectorStore


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[Citation]
    guardrails: GuardrailInfo
    retrieved_chunks: int


class RagService:
    def __init__(self, vector_store: TfidfVectorStore, retrieval_min_score: float) -> None:
        self._vector_store = vector_store
        self._retrieval_min_score = retrieval_min_score

    @property
    def chunks(self) -> list[PolicyChunk]:
        return self._vector_store.chunks

    def answer(self, question: str, top_k: int, redacted_input: bool) -> RagAnswer:
        results = self._vector_store.search(question, top_k)
        relevant = [result for result in results if result.score >= self._retrieval_min_score]

        if not relevant:
            return RagAnswer(
                answer=refusal_message("out_of_scope"),
                citations=[],
                guardrails=GuardrailInfo(
                    redacted_input=redacted_input,
                    redacted_output=False,
                    refused=True,
                    reason="out_of_scope",
                ),
                retrieved_chunks=0,
            )

        answer = _compose_answer(question, relevant)
        safe_answer, redacted_output = apply_output_guardrails(answer)
        citations = [
            Citation(
                document=result.chunk.document,
                chunk_id=result.chunk.chunk_id,
                section=result.chunk.section,
            )
            for result in relevant
        ]

        return RagAnswer(
            answer=safe_answer,
            citations=_dedupe_citations(citations),
            guardrails=GuardrailInfo(
                redacted_input=redacted_input,
                redacted_output=redacted_output,
                refused=False,
            ),
            retrieved_chunks=len(relevant),
        )


def _compose_answer(question: str, results: list[SearchResult]) -> str:
    best = results[0].chunk
    sentences = _rank_sentences(question, [result.chunk for result in results])
    selected = sentences[:3] if sentences else [_clean_markdown(best.text)]
    answer_body = " ".join(selected).strip()
    return f"{answer_body} Source: {best.document} ({best.section})."


def _rank_sentences(question: str, chunks: list[PolicyChunk]) -> list[str]:
    query_terms = {
        term
        for term in re.findall(r"[a-z0-9]+", question.lower())
        if len(term) > 2
    }
    scored: list[tuple[float, str]] = []

    for chunk_index, chunk in enumerate(chunks):
        cleaned = _clean_markdown(chunk.text)
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            sentence_terms = set(re.findall(r"[a-z0-9]+", sentence.lower()))
            overlap = len(query_terms & sentence_terms)
            if overlap:
                density = overlap / max(len(sentence_terms), 1)
                chunk_boost = max(0, len(chunks) - chunk_index) * 0.25
                score = overlap + density + chunk_boost
                scored.append((score, sentence))

    ranked = sorted(scored, key=lambda item: (item[0], len(item[1])), reverse=True)
    return [sentence for _, sentence in ranked]


def _clean_markdown(text: str) -> str:
    cleaned = re.sub(r"[*_`#>-]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        deduped.append(citation)
    return deduped
