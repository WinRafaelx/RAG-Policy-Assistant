from time import perf_counter
import logging
from uuid import uuid4

from fastapi import FastAPI, Response
from fastapi.openapi.utils import get_openapi

from app.chunking import load_policy_chunks
from app.config import get_settings
from app.embeddings import SentenceTransformerEmbeddingProvider
from app.guardrails import apply_input_guardrails, refusal_message
from app.logging_config import configure_logging
from app.rag import RagService
from app.schemas import AskRequest, AskResponse, GuardrailInfo, HealthResponse, Telemetry
from app.stores.pgvector_store import PgVectorStore
from app.vector_store import TfidfVectorStore


configure_logging()
logger = logging.getLogger("ttb_policy_assistant")
settings = get_settings()
retrieval_store = None
if settings.retrieval_backend == "pgvector":
    if not settings.database_url:
        raise RuntimeError("TTB_DATABASE_URL is required when TTB_RETRIEVAL_BACKEND=pgvector")
    embedding_provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
    if embedding_provider.dimension != settings.embedding_dimension:
        raise RuntimeError(
            f"Embedding model dimension {embedding_provider.dimension} does not match "
            f"configured dimension {settings.embedding_dimension}"
        )
    pgvector_store = PgVectorStore(settings.database_url, embedding_provider)
    if settings.bootstrap_on_startup:
        pgvector_store.bootstrap_if_empty(settings.policies_dir)
    retrieval_store = pgvector_store
else:
    chunks = load_policy_chunks(settings.policies_dir)
    retrieval_store = TfidfVectorStore(chunks)

rag_service = RagService(
    retrieval_store,
    settings.retrieval_min_score,
    settings.ollama_base_url,
    settings.ollama_default_model,
    settings.ollama_timeout_seconds,
)

app = FastAPI(title=settings.app_name, version="0.1.0")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=settings.app_name,
        version="0.1.0",
        routes=app.routes,
    )
    ask_example = {
        "question": "string",
        "top_k": 3,
        "llm_provider": None,
    }
    openapi_schema["components"]["schemas"]["AskRequest"]["example"] = ask_example
    openapi_schema["paths"]["/ask"]["post"]["requestBody"]["content"]["application/json"][
        "example"
    ] = ask_example
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    chunks = rag_service.chunks
    documents = {chunk.document for chunk in chunks}
    return HealthResponse(
        status="ok",
        retrieval_backend=settings.retrieval_backend,
        documents_loaded=len(documents),
        chunks_loaded=len(chunks),
        local_mode=settings.local_mode,
    )


@app.post("/ask", response_model=AskResponse)
def ask(request: AskRequest, response: Response) -> AskResponse:
    started = perf_counter()
    request_id = str(uuid4())
    response.headers["X-Request-ID"] = request_id
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
                "retrieval_backend": settings.retrieval_backend,
                "top_k": request.top_k,
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
        llm_provider=request.llm_provider,
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
            "retrieval_backend": settings.retrieval_backend,
            "top_k": request.top_k,
            "llm_provider": request.llm_provider or "extractive",
            "citation_chunk_ids": [citation.chunk_id for citation in rag_answer.citations],
            "retrieval_scores": rag_answer.retrieval_scores,
            "guardrail_reason": rag_answer.guardrails.reason,
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
