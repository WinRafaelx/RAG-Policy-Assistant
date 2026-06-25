from dataclasses import dataclass
import re

from app.chunking import PolicyChunk
from app.generation import ExtractiveAnswerGenerator, LlmProvider, OllamaAnswerGenerator
from app.guardrails import apply_output_guardrails, refusal_message
from app.schemas import Citation, GuardrailInfo
from app.stores.base import RetrievalStore, SearchResult


QUERY_STOP_WORDS = {
    "about",
    "are",
    "can",
    "does",
    "for",
    "from",
    "hello",
    "how",
    "is",
    "me",
    "please",
    "tell",
    "the",
    "this",
    "what",
    "when",
    "where",
    "who",
    "why",
}


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[Citation]
    guardrails: GuardrailInfo
    retrieved_chunks: int
    retrieval_scores: list[float]


class RagService:
    def __init__(
        self,
        vector_store: RetrievalStore,
        retrieval_min_score: float,
        ollama_base_url: str,
        ollama_default_model: str,
        ollama_timeout_seconds: float,
    ) -> None:
        self._vector_store = vector_store
        self._retrieval_min_score = retrieval_min_score
        self._extractive_generator = ExtractiveAnswerGenerator()
        self._ollama_base_url = ollama_base_url
        self._ollama_default_model = ollama_default_model
        self._ollama_timeout_seconds = ollama_timeout_seconds

    @property
    def chunks(self) -> list[PolicyChunk]:
        return self._vector_store.chunks

    def answer(
        self,
        question: str,
        top_k: int,
        redacted_input: bool,
        llm_provider: LlmProvider | None = None,
    ) -> RagAnswer:
        results = self._vector_store.search(question, top_k)
        relevant = [result for result in results if result.score >= self._retrieval_min_score]

        if not relevant or not _has_grounding_signal(question, relevant):
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
                retrieval_scores=[round(result.score, 4) for result in results],
            )

        answer = self._generate_answer(question, relevant, llm_provider)
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
            retrieval_scores=[round(result.score, 4) for result in relevant],
        )

    def _generate_answer(
        self,
        question: str,
        relevant: list[SearchResult],
        llm_provider: LlmProvider | None,
    ) -> str:
        if llm_provider == "ollama":
            generator = OllamaAnswerGenerator(
                base_url=self._ollama_base_url,
                model=self._ollama_default_model,
                timeout_seconds=self._ollama_timeout_seconds,
            )
            try:
                return generator.generate(question, relevant)
            except Exception:
                fallback = self._extractive_generator.generate(question, relevant)
                return (
                    f"{fallback} Note: Ollama generation was unavailable, so this "
                    "response used the deterministic extractive generator."
                )
        return self._extractive_generator.generate(question, relevant)


def _has_grounding_signal(question: str, results: list[SearchResult]) -> bool:
    query_terms = _content_terms(question)
    if not query_terms:
        return False

    chunk_terms: set[str] = set()
    for result in results[:3]:
        chunk_terms.update(_content_terms(result.chunk.text))
        chunk_terms.update(_content_terms(result.chunk.document.replace("_", " ")))
        chunk_terms.update(_content_terms(result.chunk.section))

    return bool(query_terms & chunk_terms)


def _content_terms(text: str) -> set[str]:
    return {
        term
        for term in re.findall(r"[a-z0-9]+", text.lower())
        if len(term) > 2 and term not in QUERY_STOP_WORDS
    }


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        deduped.append(citation)
    return deduped
