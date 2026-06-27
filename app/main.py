from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import perf_counter
import logging
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.openapi.utils import get_openapi

from app.domain.services.chunking import load_policy_chunks
from app.core.config import get_settings
from app.infrastructure.ai_providers.embeddings import SentenceTransformerEmbeddingProvider
from app.domain.services.guardrails import GuardrailTimings, build_guardrail_service, refusal_message
from app.core.logging_config import configure_logging
from app.api.observability import InMemoryRateLimiter, ServiceMetrics
from app.domain.services.rag import RagService
from app.api.schemas import (
    AskRequest,
    AskResponse,
    GuardrailInfo,
    GuardrailTelemetry,
    HealthResponse,
    Telemetry,
)
from app.infrastructure.databases.vector.pgvector import PgVectorStore
from app.infrastructure.databases.vector.tfidf import TfidfVectorStore


configure_logging()
logger = logging.getLogger("ttb_policy_assistant")


@dataclass
class AppServices:
    settings: object
    rag_service: RagService
    guardrail_service: object
    metrics: ServiceMetrics
    rate_limiter: InMemoryRateLimiter
    guardrails_ready: bool = False


def build_retrieval_store(settings, embedding_provider=None):
    if settings.retrieval_backend == "pgvector":
        if not settings.database_url:
            raise RuntimeError("TTB_DATABASE_URL is required when TTB_RETRIEVAL_BACKEND=pgvector")
        provider = embedding_provider or SentenceTransformerEmbeddingProvider(settings.embedding_model)
        if provider.dimension != settings.embedding_dimension:
            raise RuntimeError(
                f"Embedding model dimension {provider.dimension} does not match "
                f"configured dimension {settings.embedding_dimension}"
            )
        pgvector_store = PgVectorStore(settings.database_url, provider)
        if settings.bootstrap_on_startup:
            pgvector_store.bootstrap_if_empty(settings.policies_dir)
        return pgvector_store

    chunks = load_policy_chunks(settings.policies_dir)
    return TfidfVectorStore(chunks)


def build_app_services(settings=None, retrieval_store=None, embedding_provider=None) -> AppServices:
    active_settings = settings or get_settings()
    active_store = retrieval_store or build_retrieval_store(active_settings, embedding_provider)
    rag_service = RagService(
        active_store,
        active_settings.retrieval_min_score,
        active_settings.ollama_base_url,
        active_settings.ollama_default_model,
        active_settings.ollama_timeout_seconds,
        active_settings.ollama_keep_alive,
        active_settings.ollama_num_predict,
        active_settings.ollama_num_ctx,
        active_settings.ollama_context_top_k,
    )
    guardrail_service = build_guardrail_service(
        active_settings.prompt_injection_model,
        active_settings.prompt_injection_threshold,
        active_settings.prompt_injection_malicious_label_pattern,
    )
    return AppServices(
        settings=active_settings,
        rag_service=rag_service,
        guardrail_service=guardrail_service,
        metrics=ServiceMetrics(),
        rate_limiter=InMemoryRateLimiter(),
    )


def custom_openapi(app: FastAPI, services: AppServices):
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title=services.settings.app_name,
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
    return openapi_schema


def warm_up_guardrails(services: AppServices) -> None:
    started = perf_counter()
    timings = services.guardrail_service.warm_up()
    services.guardrails_ready = True
    logger.info(
        "guardrails.warmed",
        extra={
            "latency_ms": max(int((perf_counter() - started) * 1000), 0),
            "guardrail_timings": {
                "input_pii_redaction_ms": timings.input_pii_redaction_ms,
                "injection_detection_ms": timings.injection_detection_ms,
                "deterministic_rules_ms": timings.deterministic_rules_ms,
                "output_pii_redaction_ms": timings.output_pii_redaction_ms,
            },
        },
    )


def create_app(
    settings=None,
    retrieval_store=None,
    embedding_provider=None,
    guardrail_service_override=None,
    warmup_guardrails: bool = True,
) -> FastAPI:
    services = build_app_services(settings, retrieval_store, embedding_provider)
    if guardrail_service_override is not None:
        services.guardrail_service = guardrail_service_override

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if warmup_guardrails:
            warm_up_guardrails(services)
        yield

    app = FastAPI(
        title=services.settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.services = services
    app.openapi = lambda: custom_openapi(app, services)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        chunks = services.rag_service.chunks
        documents = {chunk.document for chunk in chunks}
        return HealthResponse(
            status="ok",
            retrieval_backend=services.settings.retrieval_backend,
            documents_loaded=len(documents),
            chunks_loaded=len(chunks),
            local_mode=services.settings.local_mode,
            guardrails_ready=services.guardrails_ready,
        )

    @app.post("/ask", response_model=AskResponse)
    def ask(
        request: AskRequest,
        response: Response,
        http_request: Request,
    ) -> AskResponse:
        started = perf_counter()
        request_id = str(uuid4())
        response.headers["X-Request-ID"] = request_id
        _check_rate_limit(http_request, services)
        input_guardrail = services.guardrail_service.apply_input(request.question)

        if input_guardrail.refused:
            answer = refusal_message(input_guardrail.reason)
            telemetry = _telemetry(
                request_id=request_id,
                started=started,
                question=input_guardrail.text,
                answer=answer,
                retrieved_chunks=0,
                guardrail_timings=input_guardrail.timings,
            )
            logger.info(
                "ask.refused",
                extra={
                    "request_id": request_id,
                    "reason": input_guardrail.reason,
                    "latency_ms": telemetry.latency_ms,
                    "retrieval_backend": services.settings.retrieval_backend,
                    "top_k": request.top_k,
                    "guardrail_timings": telemetry.guardrails.model_dump(),
                },
            )
            services.metrics.record_request(telemetry.latency_ms, input_guardrail.reason)
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

        rag_answer = services.rag_service.answer(
            question=input_guardrail.text,
            top_k=request.top_k,
            redacted_input=input_guardrail.redacted,
            output_redactor=services.guardrail_service.apply_output,
            llm_provider=request.llm_provider,
        )
        telemetry = _telemetry(
            request_id=request_id,
            started=started,
            question=input_guardrail.text,
            answer=rag_answer.answer,
            retrieved_chunks=rag_answer.retrieved_chunks,
            guardrail_timings=_combine_guardrail_timings(
                input_guardrail.timings,
                rag_answer.output_guardrail_timings,
            ),
        )
        logger.info(
            "ask.completed",
            extra={
                "request_id": request_id,
                "latency_ms": telemetry.latency_ms,
                "input_tokens": telemetry.input_tokens,
                "output_tokens": telemetry.output_tokens,
                "retrieved_chunks": telemetry.retrieved_chunks,
                "retrieval_backend": services.settings.retrieval_backend,
                "top_k": request.top_k,
                "llm_provider": request.llm_provider or "extractive",
                "citation_chunk_ids": [citation.chunk_id for citation in rag_answer.citations],
                "retrieval_scores": rag_answer.retrieval_scores,
                "guardrail_reason": rag_answer.guardrails.reason,
                "refused": rag_answer.guardrails.refused,
                "injection_score": input_guardrail.injection_score,
                "guardrail_timings": telemetry.guardrails.model_dump(),
            },
        )
        services.metrics.record_request(telemetry.latency_ms, rag_answer.guardrails.reason)
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
            content=services.metrics.render_prometheus(services.settings.retrieval_backend),
            media_type="text/plain; version=0.0.4",
        )

    return app


def _check_rate_limit(request: Request, services: AppServices) -> None:
    client = request.client.host if request.client else "unknown"
    if not services.rate_limiter.allow(client, services.settings.rate_limit_per_minute):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")


def _telemetry(
    request_id: str,
    started: float,
    question: str,
    answer: str,
    retrieved_chunks: int,
    guardrail_timings: GuardrailTimings,
) -> Telemetry:
    return Telemetry(
        request_id=request_id,
        latency_ms=max(int((perf_counter() - started) * 1000), 0),
        input_tokens=_estimate_tokens(question),
        output_tokens=_estimate_tokens(answer),
        retrieved_chunks=retrieved_chunks,
        guardrails=GuardrailTelemetry(
            input_pii_redaction_ms=guardrail_timings.input_pii_redaction_ms,
            injection_detection_ms=guardrail_timings.injection_detection_ms,
            deterministic_rules_ms=guardrail_timings.deterministic_rules_ms,
            output_pii_redaction_ms=guardrail_timings.output_pii_redaction_ms,
        ),
    )


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.split()))


def _combine_guardrail_timings(
    input_timings: GuardrailTimings,
    output_timings: GuardrailTimings,
) -> GuardrailTimings:
    return GuardrailTimings(
        input_pii_redaction_ms=input_timings.input_pii_redaction_ms,
        injection_detection_ms=input_timings.injection_detection_ms,
        deterministic_rules_ms=input_timings.deterministic_rules_ms,
        output_pii_redaction_ms=output_timings.output_pii_redaction_ms,
    )


app = create_app()
