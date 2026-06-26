from dataclasses import dataclass
from functools import lru_cache
from time import perf_counter
from typing import Protocol
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

REDACTION_BY_ENTITY = {
    "EMAIL_ADDRESS": "[REDACTED_EMAIL]",
    "PHONE_NUMBER": "[REDACTED_PHONE]",
    "THAI_NATIONAL_ID": "[REDACTED_THAI_ID]",
    "CREDIT_CARD": "[REDACTED_CARD]",
    "BANK_IDENTIFIER": "[REDACTED_IDENTIFIER]",
    "ACCOUNT_NUMBER": "[REDACTED_NUMBER]",
}


class GuardrailUnavailable(RuntimeError):
    """Raised when a required guardrail component cannot make a decision."""


@dataclass(frozen=True)
class GuardrailTimings:
    input_pii_redaction_ms: int = 0
    injection_detection_ms: int = 0
    deterministic_rules_ms: int = 0
    output_pii_redaction_ms: int = 0


@dataclass(frozen=True)
class GuardrailResult:
    text: str
    redacted: bool
    refused: bool
    reason: str | None = None
    injection_score: float | None = None
    timings: GuardrailTimings = GuardrailTimings()


@dataclass(frozen=True)
class InjectionDecision:
    malicious: bool
    score: float


class PiiRedactor(Protocol):
    def redact(self, text: str) -> tuple[str, bool]:
        ...


class PromptInjectionDetector(Protocol):
    def classify(self, text: str) -> InjectionDecision:
        ...


class RegexPiiRedactor:
    def redact(self, text: str) -> tuple[str, bool]:
        redacted = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        redacted = PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
        redacted = THAI_NATIONAL_ID_PATTERN.sub("[REDACTED_THAI_ID]", redacted)
        redacted = CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", redacted)
        redacted = LABELED_IDENTIFIER_PATTERN.sub("[REDACTED_IDENTIFIER]", redacted)
        redacted = LONG_NUMBER_PATTERN.sub("[REDACTED_NUMBER]", redacted)
        return redacted, redacted != text


class PresidioPiiRedactor:
    def __init__(self) -> None:
        try:
            from presidio_analyzer import AnalyzerEngine, Pattern, PatternRecognizer, RecognizerRegistry
            from presidio_anonymizer import AnonymizerEngine
            from presidio_anonymizer.entities import OperatorConfig
        except Exception as error:
            raise GuardrailUnavailable("Presidio is not available") from error

        registry = RecognizerRegistry()
        registry.load_predefined_recognizers(languages=["en"])
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="THAI_NATIONAL_ID",
                patterns=[
                    Pattern(
                        "thai-national-id",
                        THAI_NATIONAL_ID_PATTERN.pattern,
                        0.9,
                    )
                ],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="PHONE_NUMBER",
                patterns=[Pattern("thai-phone", PHONE_PATTERN.pattern, 0.8)],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="BANK_IDENTIFIER",
                patterns=[
                    Pattern(
                        "bank-labeled-identifier",
                        LABELED_IDENTIFIER_PATTERN.pattern,
                        0.9,
                    )
                ],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="ACCOUNT_NUMBER",
                patterns=[Pattern("long-account-like-number", LONG_NUMBER_PATTERN.pattern, 0.65)],
            )
        )
        registry.add_recognizer(
            PatternRecognizer(
                supported_entity="CREDIT_CARD",
                patterns=[Pattern("card-like-number", CREDIT_CARD_PATTERN.pattern, 0.75)],
            )
        )

        self._analyzer = AnalyzerEngine(
            registry=registry,
            nlp_engine=_NoOpNlpEngine(),
            supported_languages=["en"],
        )
        self._anonymizer = AnonymizerEngine()
        self._operators = {
            entity: OperatorConfig("replace", {"new_value": replacement})
            for entity, replacement in REDACTION_BY_ENTITY.items()
        }

    def redact(self, text: str) -> tuple[str, bool]:
        try:
            results = self._analyzer.analyze(
                text=text,
                language="en",
                entities=list(REDACTION_BY_ENTITY),
            )
            anonymized = self._anonymizer.anonymize(
                text=text,
                analyzer_results=results,
                operators=self._operators,
            )
        except Exception as error:
            raise GuardrailUnavailable("Presidio redaction failed") from error
        return anonymized.text, anonymized.text != text


class RuleBasedPromptInjectionDetector:
    def classify(self, text: str) -> InjectionDecision:
        malicious = _matches_any(text, PROMPT_INJECTION_PATTERNS)
        return InjectionDecision(malicious, 1.0 if malicious else 0.0)


class TransformersPromptInjectionDetector:
    def __init__(self, model_name: str, malicious_label_pattern: str) -> None:
        self._model_name = model_name
        self._malicious_label_pattern = re.compile(malicious_label_pattern, re.IGNORECASE)
        self._classifier = None

    def classify(self, text: str) -> InjectionDecision:
        classifier = self._load_classifier()
        try:
            raw_results = classifier(text[:1000], truncation=True, top_k=None)
        except Exception as error:
            raise GuardrailUnavailable("Prompt-injection classifier failed") from error

        results = _flatten_classifier_results(raw_results)
        malicious_scores = [
            float(result.get("score", 0.0))
            for result in results
            if self._malicious_label_pattern.search(str(result.get("label", "")))
        ]
        return InjectionDecision(bool(malicious_scores), max(malicious_scores, default=0.0))

    def _load_classifier(self):
        if self._classifier is not None:
            return self._classifier
        try:
            from transformers import pipeline

            self._classifier = pipeline("text-classification", model=self._model_name)
        except Exception as error:
            raise GuardrailUnavailable("Prompt-injection classifier is not available") from error
        return self._classifier


class GuardrailService:
    def __init__(
        self,
        pii_redactor: PiiRedactor,
        injection_detector: PromptInjectionDetector,
        injection_threshold: float,
    ) -> None:
        self._pii_redactor = pii_redactor
        self._injection_detector = injection_detector
        self._injection_threshold = injection_threshold

    def apply_input(self, text: str) -> GuardrailResult:
        timings = GuardrailTimings()
        try:
            pii_started = perf_counter()
            redacted_text, redacted = self._pii_redactor.redact(text)
            timings = _with_timing(
                timings,
                input_pii_redaction_ms=_elapsed_ms(pii_started),
            )
            rules_started = perf_counter()
            if _matches_any(redacted_text, PROMPT_INJECTION_PATTERNS):
                timings = _with_timing(timings, deterministic_rules_ms=_elapsed_ms(rules_started))
                return GuardrailResult(
                    redacted_text,
                    redacted,
                    True,
                    "prompt_injection",
                    timings=timings,
                )
            injection_started = perf_counter()
            injection_decision = self._injection_detector.classify(redacted_text)
            timings = _with_timing(
                timings,
                injection_detection_ms=_elapsed_ms(injection_started),
            )
        except GuardrailUnavailable:
            return GuardrailResult(
                "[GUARDRAIL_UNAVAILABLE]",
                False,
                True,
                "guardrail_unavailable",
                timings=timings,
            )

        if injection_decision.malicious and injection_decision.score >= self._injection_threshold:
            return GuardrailResult(
                redacted_text,
                redacted,
                True,
                "prompt_injection",
                injection_decision.score,
                timings,
            )
        rules_started = perf_counter()
        if _matches_any(redacted_text, SENSITIVE_OUT_OF_SCOPE_PATTERNS):
            timings = _with_timing(timings, deterministic_rules_ms=_elapsed_ms(rules_started))
            return GuardrailResult(
                redacted_text,
                redacted,
                True,
                "out_of_scope_sensitive_data",
                injection_decision.score,
                timings,
            )
        if _matches_any(redacted_text, POLICY_BYPASS_PATTERNS):
            timings = _with_timing(timings, deterministic_rules_ms=_elapsed_ms(rules_started))
            return GuardrailResult(
                redacted_text,
                redacted,
                True,
                "policy_bypass",
                injection_decision.score,
                timings,
            )
        timings = _with_timing(timings, deterministic_rules_ms=_elapsed_ms(rules_started))

        return GuardrailResult(
            redacted_text,
            redacted,
            False,
            injection_score=injection_decision.score,
            timings=timings,
        )

    def apply_output(self, text: str) -> tuple[str, bool, GuardrailTimings]:
        timings = GuardrailTimings()
        try:
            started = perf_counter()
            redacted_text, redacted = self._pii_redactor.redact(text)
            return (
                redacted_text,
                redacted,
                _with_timing(timings, output_pii_redaction_ms=_elapsed_ms(started)),
            )
        except GuardrailUnavailable:
            return refusal_message("guardrail_unavailable"), True, timings

    def warm_up(self) -> GuardrailTimings:
        result = self.apply_input("warmup policy question")
        if result.refused and result.reason == "guardrail_unavailable":
            raise GuardrailUnavailable("Guardrail warmup failed")
        return result.timings

    def redact_pii(self, text: str) -> tuple[str, bool]:
        return self._pii_redactor.redact(text)


def build_guardrail_service(
    injection_model: str,
    injection_threshold: float,
    malicious_label_pattern: str,
) -> GuardrailService:
    return GuardrailService(
        pii_redactor=PresidioPiiRedactor(),
        injection_detector=TransformersPromptInjectionDetector(
            model_name=injection_model,
            malicious_label_pattern=malicious_label_pattern,
        ),
        injection_threshold=injection_threshold,
    )


def redact_pii(text: str) -> tuple[str, bool]:
    return _compatibility_service().redact_pii(text)


def apply_input_guardrails(text: str) -> GuardrailResult:
    return _compatibility_service().apply_input(text)


def apply_output_guardrails(text: str) -> tuple[str, bool, GuardrailTimings]:
    return _compatibility_service().apply_output(text)


def refusal_message(reason: str | None) -> str:
    messages = {
        "prompt_injection": "I cannot reveal hidden instructions or follow requests to override system rules.",
        "out_of_scope_sensitive_data": "I cannot answer questions about customer-specific, account-specific, or sensitive personal data.",
        "policy_bypass": "I cannot help bypass policy approvals or controls.",
        "guardrail_unavailable": "I cannot safely process that request because a required guardrail is unavailable.",
        "out_of_scope": "I could not find enough grounded policy context to answer that question.",
    }
    return messages.get(reason or "out_of_scope", messages["out_of_scope"])


@lru_cache
def _compatibility_service() -> GuardrailService:
    return GuardrailService(
        pii_redactor=PresidioPiiRedactor(),
        injection_detector=RuleBasedPromptInjectionDetector(),
        injection_threshold=0.75,
    )


def _matches_any(text: str, patterns: tuple[re.Pattern[str], ...]) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def _flatten_classifier_results(raw_results) -> list[dict]:
    if not isinstance(raw_results, list):
        return []
    if raw_results and isinstance(raw_results[0], list):
        return [item for group in raw_results for item in group if isinstance(item, dict)]
    return [item for item in raw_results if isinstance(item, dict)]


def _elapsed_ms(started: float) -> int:
    return max(int((perf_counter() - started) * 1000), 0)


def _with_timing(timings: GuardrailTimings, **updates: int) -> GuardrailTimings:
    values = {
        "input_pii_redaction_ms": timings.input_pii_redaction_ms,
        "injection_detection_ms": timings.injection_detection_ms,
        "deterministic_rules_ms": timings.deterministic_rules_ms,
        "output_pii_redaction_ms": timings.output_pii_redaction_ms,
    }
    values.update(updates)
    return GuardrailTimings(**values)


class _NoOpNlpEngine:
    def load(self) -> None:
        return None

    def is_loaded(self) -> bool:
        return True

    def is_stopword(self, _word: str, _language: str) -> bool:
        return False

    def is_punct(self, _word: str, _language: str) -> bool:
        return False

    def process_text(self, text: str, language: str):
        from presidio_analyzer.nlp_engine import NlpArtifacts

        return NlpArtifacts([], [], [], [], None, language, [])

    def process_batch(self, texts, language: str, **_kwargs):
        for text in texts:
            yield text, self.process_text(text, language)

    def get_supported_entities(self) -> list[str]:
        return []

    def get_supported_languages(self) -> list[str]:
        return ["en"]
