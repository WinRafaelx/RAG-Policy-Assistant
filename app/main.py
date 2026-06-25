from time import perf_counter
import logging
from uuid import uuid4

from fastapi import FastAPI

from app.chunking import load_policy_chunks
from app.config import get_settings
from app.guardrails import apply_input_guardrails, refusal_message
from app.logging_config import configure_logging
from app.rag import RagService
from app.schemas import AskRequest, AskResponse, GuardrailInfo, HealthResponse, Telemetry
from app.vector_store import TfidfVectorStore


configure_logging()
logger = logging.getLogger("ttb_policy_assistant")
settings = get_settings()
chunks = load_policy_chunks(settings.policies_dir)
rag_service = RagService(TfidfVectorStore(chunks), settings.retrieval_min_score)

app = FastAPI(title=settings.app_name, version="0.1.0")


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    documents = {chunk.document for chunk in chunks}
    return HealthResponse(
        status="ok",
        documents_loaded=len(documents),
        chunks_loaded=len(chunks),
        local_mode=settings.local_mode,
    )


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    started = perf_counter()
    request_id = str(uuid4())
    input_guardrail = apply_input_guardrails(request.question)

    if input_guardrail.refused:
        answer = refusal_message(input_guardrail.reason)
        telemetry = _telemetry(
            request_id=request_id,
            started=started,
            question=input_guardrail.text,
            answer=answer,
            retrieved_chunks=0,
        )
        logger.info(
            "ask.refused",
            extra={
                "request_id": request_id,
                "reason": input_guardrail.reason,
                "latency_ms": telemetry.latency_ms,
            },
        )
        return AskResponse(
            success=True,
            answer=answer,
            citations=[],
            guardrails=GuardrailInfo(
                redacted_input=input_guardrail.redacted,
                redacted_output=False,
                refused=True,
                reason=input_guardrail.reason,
            ),
            telemetry=telemetry,
        )

    rag_answer = rag_service.answer(
        question=input_guardrail.text,
        top_k=request.top_k,
        redacted_input=input_guardrail.redacted,
    )
    telemetry = _telemetry(
        request_id=request_id,
        started=started,
        question=input_guardrail.text,
        answer=rag_answer.answer,
        retrieved_chunks=rag_answer.retrieved_chunks,
    )
    logger.info(
        "ask.completed",
        extra={
            "request_id": request_id,
            "latency_ms": telemetry.latency_ms,
            "input_tokens": telemetry.input_tokens,
            "output_tokens": telemetry.output_tokens,
            "retrieved_chunks": telemetry.retrieved_chunks,
            "refused": rag_answer.guardrails.refused,
        },
    )
    return AskResponse(
        success=True,
        answer=rag_answer.answer,
        citations=rag_answer.citations,
        guardrails=rag_answer.guardrails,
        telemetry=telemetry,
    )


def _telemetry(
    request_id: str,
    started: float,
    question: str,
    answer: str,
    retrieved_chunks: int,
) -> Telemetry:
    return Telemetry(
        request_id=request_id,
        latency_ms=max(int((perf_counter() - started) * 1000), 0),
        input_tokens=_estimate_tokens(question),
        output_tokens=_estimate_tokens(answer),
        retrieved_chunks=retrieved_chunks,
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))
