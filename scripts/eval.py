import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.guardrails import apply_input_guardrails
from app.main import rag_service


def main() -> None:
    eval_path = Path("data/eval/eval_questions.json")
    adversarial_path = Path("data/eval/adversarial_questions.json")
    questions = json.loads(eval_path.read_text(encoding="utf-8"))
    adversarial = json.loads(adversarial_path.read_text(encoding="utf-8"))

    citation_hits = 0
    term_hits = 0
    answered = 0

    print("Evaluation Summary")
    print("==================")
    for item in questions:
        guarded = apply_input_guardrails(item["question"])
        result = rag_service.answer(guarded.text, top_k=3, redacted_input=guarded.redacted)
        cited_sources = {citation.document for citation in result.citations}
        expected_sources = set(item["expected_sources"])
        has_expected_source = bool(cited_sources & expected_sources)
        has_expected_term = any(
            term.lower() in result.answer.lower()
            for term in item.get("expected_terms", [])
        )
        citation_hits += int(has_expected_source)
        term_hits += int(has_expected_term)
        answered += int(not result.guardrails.refused)
        print(
            f"{item['id']}: answered={not result.guardrails.refused} "
            f"citation_hit={has_expected_source} term_hit={has_expected_term}"
        )

    refusals = 0
    for item in adversarial:
        guarded = apply_input_guardrails(item["question"])
        refused = guarded.refused
        refusals += int(refused)
        print(f"{item['id']}: refused={refused} reason={guarded.reason}")

    print()
    print(f"Grounded questions answered: {answered}/{len(questions)}")
    print(f"Expected citation hits: {citation_hits}/{len(questions)}")
    print(f"Expected term hits: {term_hits}/{len(questions)}")
    print(f"Adversarial refusals: {refusals}/{len(adversarial)}")


if __name__ == "__main__":
    main()
