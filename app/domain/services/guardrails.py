from dataclasses import dataclass
import re


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"\b(?:\+?66|0)\d{1,2}[-\s]?\d{3}[-\s]?\d{4}\b")
THAI_NATIONAL_ID_PATTERN = re.compile(r"\b\d[-\s]?\d{4}[-\s]?\d{5}[-\s]?\d{2}[-\s]?\d\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]?){13,19}\b")
LABELED_IDENTIFIER_PATTERN = re.compile(
    r"\b(?:customer|cif|account|employee|staff|id)\s*(?:id|number|no\.?|#)?\s*[:#-]?\s*\d{4,20}\b",
    re.IGNORECASE,
)
LONG_NUMBER_PATTERN = re.compile(r"\b\d{8,20}\b")

PROMPT_INJECTION_PATTERNS = (
    re.compile(r"\bignore\b.*\b(instruction|instructions|rules|policy|policies)\b", re.IGNORECASE),
    re.compile(r"\bforget\b.*\b(instruction|instructions|rules|policy|policies)\b", re.IGNORECASE),
    re.compile(r"\boverride\b.*\b(instruction|instructions|rules|policy|policies)\b", re.IGNORECASE),
    re.compile(r"\b(system|developer)\s+prompt\b", re.IGNORECASE),
    re.compile(r"\b(system|developer)\s+(instruction|instructions|message|messages)\b", re.IGNORECASE),
    re.compile(r"\bprint\b.*\b(prompt|hidden|secret)\b", re.IGNORECASE),
    re.compile(r"\breveal\b.*\b(prompt|hidden|secret)\b", re.IGNORECASE),
    re.compile(r"\btranslate\b.*\b(system|developer)\s+prompt\b", re.IGNORECASE),
)

SENSITIVE_OUT_OF_SCOPE_PATTERNS = (
    re.compile(
        r"\b(customer|cif|account|card)\b.*\b(balance|account|transactions?|profile|phone|address|limit)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\baccount\s+balance\b", re.IGNORECASE),
    re.compile(r"\b(card|credit\s+card)\b.*\b(number|limit|balance)\b", re.IGNORECASE),
)

POLICY_BYPASS_PATTERNS = (
    re.compile(r"\b(bypass|avoid|evade|skip)\b.*\b(approval|control|policy|review)\b", re.IGNORECASE),
    re.compile(r"\bhow\b.*\b(bypass|avoid|evade|skip)\b", re.IGNORECASE),
    re.compile(r"\bavoid\b.*\b(kyc|aml|escalation|screening)\b", re.IGNORECASE),
)


@dataclass(frozen=True)
class GuardrailResult:
    text: str
    redacted: bool
    refused: bool
    reason: str | None = None


def redact_pii(text: str) -> tuple[str, bool]:
    redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
    redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
    redacted = THAI_NATIONAL_ID_PATTERN.sub("[REDACTED_THAI_ID]", redacted)
    redacted = CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", redacted)
    redacted = LABELED_IDENTIFIER_PATTERN.sub("[REDACTED_IDENTIFIER]", redacted)
    redacted = LONG_NUMBER_PATTERN.sub("[REDACTED_NUMBER]", redacted)
    return redacted, redacted != text


def apply_input_guardrails(text: str) -> GuardrailResult:
    redacted_text, redacted = redact_pii(text)

    if _matches_any(text, PROMPT_INJECTION_PATTERNS):
        return GuardrailResult(redacted_text, redacted, True, "prompt_injection")
    if _matches_any(text, SENSITIVE_OUT_OF_SCOPE_PATTERNS):
        return GuardrailResult(redacted_text, redacted, True, "out_of_scope_sensitive_data")
    if _matches_any(text, POLICY_BYPASS_PATTERNS):
        return GuardrailResult(redacted_text, redacted, True, "policy_bypass")

    return GuardrailResult(redacted_text, redacted, False)


def apply_output_guardrails(text: str) -> tuple[str, bool]:
    return redact_pii(text)


def refusal_message(reason: str | None) -> str:
    messages = {
        "prompt_injection": "I cannot reveal hidden instructions or follow requests to override system rules.",
        "out_of_scope_sensitive_data": "I cannot answer questions about customer-specific, account-specific, or sensitive personal data.",
        "policy_bypass": "I cannot help bypass policy approvals or controls.",
        "out_of_scope": "I could not find enough grounded policy context to answer that question.",
    }
    return messages.get(reason or "out_of_scope", messages["out_of_scope"])


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)
