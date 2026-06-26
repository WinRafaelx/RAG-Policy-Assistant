from dataclasses import dataclass
from typing import Callable

from app.domain.services.chunking import PolicyChunk
from app.domain.services.text_normalization import content_terms
from app.infrastructure.ai_providers.generation import ExtractiveAnswerGenerator, LlmProvider, OllamaAnswerGenerator
from app.domain.services.guardrails import GuardrailTimings, apply_output_guardrails, refusal_message
from app.api.schemas import Citation, GuardrailInfo
from app.infrastructure.databases.vector.base import RetrievalStore, SearchResult


@dataclass(frozen=True)
class RagAnswer:
    answer: str
    citations: list[Citation]
    guardrails: GuardrailInfo
    retrieved_chunks: int
    retrieval_scores: list[float]
    output_guardrail_timings: GuardrailTimings = GuardrailTimings()


class RagService:
    def __init__(
        self,
        vector_store: RetrievalStore,
        retrieval_min_score: float,
        ollama_base_url: str,
        ollama_default_model: str,
        ollama_timeout_seconds: float,
        ollama_keep_alive: str,
        ollama_num_predict: int = 80,
        ollama_num_ctx: int = 1024,
        ollama_context_top_k: int = 1,
    ) -> None:
        self._vector_store = vector_store
        self._retrieval_min_score = retrieval_min_score
        self._extractive_generator = ExtractiveAnswerGenerator()
        self._ollama_base_url = ollama_base_url
        self._ollama_default_model = ollama_default_model
        self._ollama_timeout_seconds = ollama_timeout_seconds
        self._ollama_keep_alive = ollama_keep_alive
        self._ollama_num_predict = ollama_num_predict
        self._ollama_num_ctx = ollama_num_ctx
        self._ollama_context_top_k = ollama_context_top_k

    @property
    def chunks(self) -> list[PolicyChunk]:
        return self._vector_store.chunks

    def answer(
        self,
        question: str,
        top_k: int,
        redacted_input: bool,
        output_redactor: Callable[[str], tuple[str, bool, GuardrailTimings]] = apply_output_guardrails,
        llm_provider: LlmProvider | None = None,
    ) -> RagAnswer:
        candidate_k = max(top_k * 4, top_k + 5)
        results = self._vector_store.search(question, candidate_k)
        relevant = _rerank_results(
            question,
            [result for result in results if result.score >= self._retrieval_min_score],
        )[:top_k]

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

        answer = self._with_inline_citation(
            self._generate_answer(question, relevant, llm_provider),
            relevant[0].chunk.chunk_id,
        )
        safe_answer, redacted_output, output_timings = output_redactor(answer)
        if safe_answer == refusal_message("guardrail_unavailable"):
            return RagAnswer(
                answer=safe_answer,
                citations=[],
                guardrails=GuardrailInfo(
                    redacted_input=redacted_input,
                    redacted_output=redacted_output,
                    refused=True,
                    reason="guardrail_unavailable",
                ),
                retrieved_chunks=0,
                retrieval_scores=[round(result.score, 4) for result in relevant],
                output_guardrail_timings=output_timings,
            )
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
            output_guardrail_timings=output_timings,
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
                keep_alive=self._ollama_keep_alive,
                num_predict=self._ollama_num_predict,
                num_ctx=self._ollama_num_ctx,
            )
            try:
                return generator.generate(
                    question,
                    relevant[: max(1, self._ollama_context_top_k)],
                )
            except Exception:
                fallback = self._extractive_generator.generate(question, relevant)
                return (
                    f"{fallback} Note: Ollama generation was unavailable, so this "
                    "response used the deterministic extractive generator."
                )
        return self._extractive_generator.generate(question, relevant)

    def _with_inline_citation(self, answer: str, chunk_id: str) -> str:
        citation = f"[{chunk_id}]"
        if citation in answer:
            return answer
        return f"{answer.rstrip()} {citation}"


def _has_grounding_signal(question: str, results: list[SearchResult]) -> bool:
    query_terms = content_terms(question)
    if not query_terms:
        return False

    chunk_terms: set[str] = set()
    for result in results[:3]:
        chunk_terms.update(content_terms(result.chunk.text))
        chunk_terms.update(content_terms(result.chunk.document.replace("_", " ")))
        chunk_terms.update(content_terms(result.chunk.section))

    return bool(query_terms & chunk_terms)


def _rerank_results(question: str, results: list[SearchResult]) -> list[SearchResult]:
    query_terms = content_terms(question)
    if not query_terms:
        return results

    def ranking(result: SearchResult) -> tuple[float, float]:
        chunk_terms = content_terms(
            " ".join(
                [
                    result.chunk.document.replace("_", " "),
                    result.chunk.section,
                    result.chunk.text,
                ]
            )
        )
        overlap = query_terms & chunk_terms
        lexical_score = len(overlap) / len(query_terms)
        return result.score + lexical_score, result.score

    return sorted(results, key=ranking, reverse=True)


def _dedupe_citations(citations: list[Citation]) -> list[Citation]:
    seen: set[str] = set()
    deduped: list[Citation] = []
    for citation in citations:
        if citation.chunk_id in seen:
            continue
        seen.add(citation.chunk_id)
        deduped.append(citation)
    return deduped
