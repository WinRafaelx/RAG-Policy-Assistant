import httpx

from app.domain.services.chunking import PolicyChunk
from app.infrastructure.ai_providers.generation import OllamaAnswerGenerator, _strip_thinking
from app.infrastructure.databases.vector.base import SearchResult


def test_strip_thinking_removes_qwen_thinking_block() -> None:
    text = "<think>private reasoning</think>The policy requires approval."

    assert _strip_thinking(text) == "The policy requires approval."


def test_strip_thinking_removes_truncated_qwen_thinking_block() -> None:
    text = "<think>private reasoning that was truncated"

    assert _strip_thinking(text) == ""


def test_ollama_generator_uses_compact_chat_api(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout
        request = httpx.Request("POST", url)
        return httpx.Response(
            200,
            request=request,
            json={"message": {"content": "Employees receive 22 business days."}},
        )

    monkeypatch.setattr(httpx, "post", fake_post)
    generator = OllamaAnswerGenerator(
        base_url="http://localhost:11434",
        model="qwen3.5:4b",
        timeout_seconds=3.0,
    )

    answer = generator.generate(
        "How many annual leave days?",
        [
            SearchResult(
                chunk=PolicyChunk(
                    chunk_id="policy_01_annual_leave.md:002",
                    document="policy_01_annual_leave.md",
                    section="2. Accrual and Allowance",
                    text="Full-time employees accrue 22 business days per calendar year.",
                ),
                score=0.9,
            )
        ],
    )

    assert answer == "Employees receive 22 business days."
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["timeout"] == 3.0
    payload = captured["json"]
    assert payload["model"] == "qwen3.5:4b"
    assert payload["stream"] is False
    assert payload["think"] is False
    assert payload["options"]["temperature"] == 0.0
    assert payload["options"]["num_predict"] == 80
    assert payload["options"]["num_ctx"] == 1024
    assert len(payload["messages"]) == 2
    assert "Policy context:" in payload["messages"][1]["content"]
    assert "one short sentence" in payload["messages"][0]["content"]
