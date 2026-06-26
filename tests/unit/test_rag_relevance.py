from app.domain.services.chunking import PolicyChunk
from app.domain.services.chunking import load_policy_chunks
from app.domain.services.guardrails import GuardrailTimings
from app.domain.services.rag import RagService
from app.infrastructure.databases.vector.base import SearchResult
from app.infrastructure.databases.vector.tfidf import TfidfVectorStore
from pathlib import Path


class FakeUnrelatedStore:
    @property
    def chunks(self) -> list[PolicyChunk]:
        return [
            PolicyChunk(
                chunk_id="policy_11_kyc_onboarding.md:007",
                document="policy_11_kyc_onboarding.md",
                section="6. Approvals and Escalations",
                text="High-risk onboarding requires signoff from the KYC Team Lead.",
            )
        ]

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        return [SearchResult(chunk=self.chunks[0], score=0.91)]


def test_rag_refuses_when_vector_search_returns_unrelated_nearest_chunk() -> None:
    service = RagService(
        FakeUnrelatedStore(),
        retrieval_min_score=0.08,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer("hello what is science ?", top_k=3, redacted_input=False)

    assert answer.guardrails.refused is True
    assert answer.guardrails.reason == "out_of_scope"
    assert answer.citations == []


class FakeRelatedStore:
    @property
    def chunks(self) -> list[PolicyChunk]:
        return [
            PolicyChunk(
                chunk_id="policy_01_annual_leave.md:002",
                document="policy_01_annual_leave.md",
                section="2. Accrual and Allowance",
                text="Full-time employees accrue 22 business days per calendar year.",
            )
        ]

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        return [SearchResult(chunk=self.chunks[0], score=0.91)]


def test_rag_falls_back_when_ollama_is_unavailable() -> None:
    service = RagService(
        FakeRelatedStore(),
        retrieval_min_score=0.08,
        ollama_base_url="http://127.0.0.1:1",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=0.01,
        ollama_keep_alive="5m",
    )

    answer = service.answer(
        "How many annual leave days do full-time employees receive?",
        top_k=3,
        redacted_input=False,
        llm_provider="ollama",
    )

    assert answer.guardrails.refused is False
    assert "Ollama generation was unavailable" in answer.answer
    assert answer.citations


def test_rag_answer_includes_inline_chunk_citation() -> None:
    service = RagService(
        FakeRelatedStore(),
        retrieval_min_score=0.08,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer(
        "How many annual leave days do full-time employees receive?",
        top_k=3,
        redacted_input=False,
    )

    assert "[policy_01_annual_leave.md:002]" in answer.answer


def test_rag_refuses_when_output_redactor_fails_closed() -> None:
    service = RagService(
        FakeRelatedStore(),
        retrieval_min_score=0.08,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer(
        "How many annual leave days do full-time employees receive?",
        top_k=3,
        redacted_input=False,
        output_redactor=lambda text: (
            "I cannot safely process that request because a required guardrail is unavailable.",
            True,
            GuardrailTimings(output_pii_redaction_ms=3),
        ),
    )

    assert answer.guardrails.refused is True
    assert answer.guardrails.reason == "guardrail_unavailable"
    assert answer.citations == []
    assert answer.output_guardrail_timings.output_pii_redaction_ms == 3


def test_rag_expands_vacation_to_annual_leave_allowance() -> None:
    chunks = [
        PolicyChunk(
            chunk_id="policy_01_annual_leave.md:003",
            document="policy_01_annual_leave.md",
            section="2. Accrual and Allowance",
            text=(
                "Full-Time Employees: All standard full-time employees accrue annual "
                "leave at a rate of 22 business days per calendar year."
            ),
        ),
        PolicyChunk(
            chunk_id="policy_03_remote_work.md:003",
            document="policy_03_remote_work.md",
            section="2. Hybrid Work Framework",
            text="Employees are required to work from the office three days per week.",
        ),
    ]
    service = RagService(
        TfidfVectorStore(chunks),
        retrieval_min_score=0.01,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer("How many vacation days do employee have?", 1, False)

    assert answer.guardrails.refused is False
    assert "22 business days" in answer.answer
    assert answer.citations[0].chunk_id == "policy_01_annual_leave.md:003"


class FakeWideCandidateStore:
    def __init__(self) -> None:
        self.requested_top_k = 0

    @property
    def chunks(self) -> list[PolicyChunk]:
        return []

    def search(self, query: str, top_k: int) -> list[SearchResult]:
        self.requested_top_k = top_k
        return [
            SearchResult(
                PolicyChunk(
                    "policy_01_annual_leave.md:004",
                    "policy_01_annual_leave.md",
                    "3. Carry-Over and Forfeiture",
                    "A maximum of 5 unused leave days may be carried over.",
                ),
                0.91,
            ),
            SearchResult(
                PolicyChunk(
                    "policy_01_annual_leave.md:003",
                    "policy_01_annual_leave.md",
                    "2. Accrual and Allowance",
                    "Full-time employees accrue annual leave at a rate of 22 business days.",
                ),
                0.84,
            ),
        ]


def test_rag_searches_wider_candidates_then_reranks_by_question_terms() -> None:
    store = FakeWideCandidateStore()
    service = RagService(
        store,
        retrieval_min_score=0.01,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer("How many vacation days do employees have?", 1, False)

    assert store.requested_top_k > 1
    assert "22 business days" in answer.answer
    assert answer.citations[0].chunk_id == "policy_01_annual_leave.md:003"


def test_rag_limits_ollama_context_to_top_reranked_chunk(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_generate(self, question, results):
        seen["question"] = question
        seen["chunk_ids"] = [result.chunk.chunk_id for result in results]
        return "Employees receive 22 business days."

    monkeypatch.setattr(
        "app.infrastructure.ai_providers.generation.OllamaAnswerGenerator.generate",
        fake_generate,
    )
    store = FakeWideCandidateStore()
    service = RagService(
        store,
        retrieval_min_score=0.01,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
        ollama_context_top_k=1,
    )

    answer = service.answer(
        "How many vacation days do employees have?",
        2,
        False,
        llm_provider="ollama",
    )

    assert answer.guardrails.refused is False
    assert seen["chunk_ids"] == ["policy_01_annual_leave.md:003"]
    assert answer.citations[0].chunk_id == "policy_01_annual_leave.md:003"


def test_real_policy_corpus_answers_vacation_allowance_wording() -> None:
    service = RagService(
        TfidfVectorStore(load_policy_chunks(Path("data/policies"))),
        retrieval_min_score=0.08,
        ollama_base_url="http://localhost:11434",
        ollama_default_model="qwen3.5:4b",
        ollama_timeout_seconds=1.0,
        ollama_keep_alive="5m",
    )

    answer = service.answer("How many vacation do employee have ?", 3, False)

    assert answer.guardrails.refused is False
    assert "22 business days" in answer.answer
    assert answer.citations[0].chunk_id == "policy_01_annual_leave.md:003"
