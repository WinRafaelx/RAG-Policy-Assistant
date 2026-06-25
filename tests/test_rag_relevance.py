from app.chunking import PolicyChunk
from app.rag import RagService
from app.stores.base import SearchResult


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
        ollama_default_model="qwen3.5:9b",
        ollama_timeout_seconds=1.0,
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
        ollama_default_model="qwen3.5:9b",
        ollama_timeout_seconds=0.01,
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
