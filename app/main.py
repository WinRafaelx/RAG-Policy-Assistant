from time import perf_counter
import logging
import secrets
from uuid import uuid4

from fastapi import FastAPI, Header, HTTPException, Request, Response
from fastapi.openapi.utils import get_openapi

from app.domain.services.chunking import load_policy_chunks
from app.core.config import get_settings
from app.infrastructure.ai_providers.embeddings import SentenceTransformerEmbeddingProvider
from app.domain.services.guardrails import apply_input_guardrails, refusal_message
from app.core.logging_config import configure_logging
from app.api.observability import InMemoryRateLimiter, ServiceMetrics
from app.domain.services.rag import RagService
from app.api.schemas import AskRequest, AskResponse, GuardrailInfo, HealthResponse, Telemetry
from app.infrastructure.databases.vector.pgvector import PgVectorStore
from app.infrastructure.databases.vector.tfidf import TfidfVectorStore


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
    settings.ollama_keep_alive,
    settings.ollama_num_predict,
    settings.ollama_num_ctx,
    settings.ollama_context_top_k,
)

app = FastAPI(title=settings.app_name, version="0.1.0")
metrics = ServiceMetrics()
rate_limiter = InMemoryRateLimiter()


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
def ask(
    request: AskRequest,
    response: Response,
    http_request: Request,
    x_api_key: str | None = Header(default=None),
) -> AskResponse:
    started = perf_counter()
    request_id = str(uuid4())
    response.headers["X-Request-ID"] = request_id
    _authorize_request(x_api_key)
    _check_rate_limit(http_request)
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
        metrics.record_request(telemetry.latency_ms, input_guardrail.reason)
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
    metrics.record_request(telemetry.latency_ms, rag_answer.guardrails.reason)
    return AskResponse(
        success=True,
        answer=rag_answer.answer,
        citations=rag_answer.citations,
        guardrails=rag_answer.guardrails,
        telemetry=telemetry,
    )


@app.get("/metrics")
def service_metrics() -> Response:
    return Response(
        content=metrics.render_prometheus(settings.retrieval_backend),
        media_type="text/plain; version=0.0.4",
    )


def _authorize_request(x_api_key: str | None) -> None:
    if not settings.api_key:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, settings.api_key):
        raise HTTPException(status_code=401, detail="Missing or invalid API key")


def _check_rate_limit(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    if not rate_limiter.allow(client, settings.rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


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
