import re


STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "at",
    "be",
    "before",
    "by",
    "can",
    "do",
    "does",
    "for",
    "from",
    "have",
    "hello",
    "how",
    "if",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "or",
    "please",
    "tell",
    "the",
    "this",
    "to",
    "what",
    "when",
    "where",
    "who",
    "why",
    "with",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z0-9]+")

TERM_EXPANSIONS = {
    "holiday": ("annual", "leave", "vacation", "allowance", "accrue", "entitled"),
    "holidays": ("annual", "leave", "vacation", "allowance", "accrue", "entitled"),
    "pto": ("annual", "leave", "vacation", "allowance", "accrue", "entitled"),
    "vacation": ("annual", "leave", "holiday", "allowance", "accrue", "entitled"),
    "vacations": ("annual", "leave", "holiday", "allowance", "accrue", "entitled"),
}


def content_terms(text: str, expand: bool = True) -> set[str]:
    terms = {_normalize_token(token) for token in TOKEN_PATTERN.findall(text)}
    terms = {term for term in terms if len(term) > 1 and term not in STOP_WORDS}
    if not expand:
        return terms

    expanded = set(terms)
    for term in terms:
        expanded.update(TERM_EXPANSIONS.get(term, ()))
    expanded.update(_phrase_expansions(text))
    return expanded


def normalized_tokens(text: str, expand: bool = True) -> list[str]:
    terms: list[str] = []
    for token in TOKEN_PATTERN.findall(text):
        term = _normalize_token(token)
        if len(term) <= 1 or term in STOP_WORDS:
            continue
        terms.append(term)
        if expand:
            terms.extend(TERM_EXPANSIONS.get(term, ()))
    if expand:
        terms.extend(_phrase_expansions(text))
    return terms


def _phrase_expansions(text: str) -> tuple[str, ...]:
    normalized = text.lower()
    if "how many" in normalized:
        return ("allowance", "accrual", "accrue", "entitled", "rate")
    return ()


def _normalize_token(token: str) -> str:
    term = token.lower()
    if len(term) > 4 and term.endswith("ies"):
        return f"{term[:-3]}y"
    if len(term) > 3 and term.endswith("es"):
        return term[:-2]
    if len(term) > 3 and term.endswith("s"):
        return term[:-1]
    return term
