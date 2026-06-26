from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)
    llm_provider: Literal["ollama"] | None = Field(
        default=None,
        description=(
            "Optional answer-generation provider. Leave null to use the default "
            "deterministic extractive answer generator, which requires no LLM or "
            "API key. Set to 'ollama' only when a local Ollama server is running "
            "and TTB_OLLAMA_BASE_URL / TTB_OLLAMA_DEFAULT_MODEL are configured. "
            "Retrieval, guardrails, grounding checks, citations, and output "
            "redaction still run outside the LLM."
        ),
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        stripped = value.strip()
        if len(stripped) < 3:
            raise ValueError("Question must contain at least 3 non-whitespace characters")
        return stripped

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "question": "string",
                "top_k": 3,
                "llm_provider": None,
            }
        }
    )


class Citation(BaseModel):
    document: str
    chunk_id: str
    section: str | None = None


class GuardrailInfo(BaseModel):
    redacted_input: bool
    redacted_output: bool
    refused: bool
    reason: str | None = None


class GuardrailTelemetry(BaseModel):
    input_pii_redaction_ms: int = 0
    injection_detection_ms: int = 0
    deterministic_rules_ms: int = 0
    output_pii_redaction_ms: int = 0


class Telemetry(BaseModel):
    request_id: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    retrieved_chunks: int
    guardrails: GuardrailTelemetry = Field(default_factory=GuardrailTelemetry)


class AskResponse(BaseModel):
    success: bool
    answer: str
    citations: list[Citation]
    guardrails: GuardrailInfo
    telemetry: Telemetry


class HealthResponse(BaseModel):
    status: str
    retrieval_backend: str
    documents_loaded: int
    chunks_loaded: int
    local_mode: bool
    guardrails_ready: bool = True
