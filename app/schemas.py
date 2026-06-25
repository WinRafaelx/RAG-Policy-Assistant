from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    top_k: int = Field(default=3, ge=1, le=5)


class Citation(BaseModel):
    document: str
    chunk_id: str
    section: str | None = None


class GuardrailInfo(BaseModel):
    redacted_input: bool
    redacted_output: bool
    refused: bool
    reason: str | None = None


class Telemetry(BaseModel):
    request_id: str
    latency_ms: int
    input_tokens: int
    output_tokens: int
    retrieved_chunks: int


class AskResponse(BaseModel):
    success: bool
    answer: str
    citations: list[Citation]
    guardrails: GuardrailInfo
    telemetry: Telemetry


class HealthResponse(BaseModel):
    status: str
    documents_loaded: int
    chunks_loaded: int
    local_mode: bool
