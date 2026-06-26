from typing import Literal, Protocol
import re

import httpx

from app.domain.services.chunking import PolicyChunk
from app.domain.services.text_normalization import content_terms
from app.infrastructure.databases.vector.base import SearchResult


LlmProvider = Literal["ollama"]


class AnswerGenerator(Protocol):
    def generate(self, question: str, results: list[SearchResult]) -> str:
        ...


class ExtractiveAnswerGenerator:
    def generate(self, question: str, results: list[SearchResult]) -> str:
        sentences_with_chunks = _rank_sentences(question, [result.chunk for result in results])
        if sentences_with_chunks:
            selected = sentences_with_chunks[:3]
            best = selected[0][1]
        else:
            best = results[0].chunk
            selected = [(_clean_markdown(best.text), best)]

        parts = []
        for sentence, chunk in selected:
            citation = f"[{chunk.chunk_id}]"
            s_clean = sentence.rstrip(".!?")
            punc = sentence[-1] if sentence and sentence[-1] in ".!?" else "."
            parts.append(f"{s_clean} {citation}{punc}")

        answer_body = " ".join(parts).strip()
        return f"{answer_body} Source: {best.document} ({best.section})."
 

class OllamaAnswerGenerator:
    def __init__(
        self,
        base_url: str,
        model: str,
        timeout_seconds: float,
        keep_alive: str = "5m",
        num_predict: int = 80,
        num_ctx: int = 1024,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout_seconds = timeout_seconds
        self._num_predict = num_predict
        self._num_ctx = num_ctx
        
        # Parse numeric keep_alive inputs (like "0" or "-1") as integers for Ollama compat
        try:
            self._keep_alive: int | str = int(keep_alive)
        except ValueError:
            self._keep_alive = keep_alive

    def generate(self, question: str, results: list[SearchResult]) -> str:
        context = _format_context(results)
        response = httpx.post(
            f"{self._base_url}/api/chat",
            json={
                "model": self._model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the provided policy context. Keep the "
                            "answer to one short sentence. Do not include reasoning. "
                            "Final answer only. If the context does not contain the answer "
                            "to the question, you must respond with: "
                            "\"I could not find enough grounded policy context to answer that question.\""
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Policy context:\n{context}\n\n"
                            f"Question: {question}\n"
                            "Answer using only the policy context. If the answer cannot be found in the context, "
                            "respond with: \"I could not find enough grounded policy context to answer that question.\" /no_think"
                        ),
                    },
                ],
                "stream": False,
                "think": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": self._num_predict,
                    "num_ctx": self._num_ctx,
                },
                "keep_alive": self._keep_alive,
            },
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        content = payload.get("message", {}).get("content", "")
        answer = _strip_thinking(str(content)).strip()
        if not answer:
            raise RuntimeError("Ollama returned an empty answer")
        return answer


def _format_context(results: list[SearchResult]) -> str:
    parts = []
    for result in results:
        chunk = result.chunk
        parts.append(
            "\n".join(
                [
                    f"Source: {chunk.document}",
                    f"Chunk ID: {chunk.chunk_id}",
                    f"Section: {chunk.section}",
                    f"Text: {chunk.text}",
                ]
            )
        )
    return "\n\n---\n\n".join(parts)


def _rank_sentences(question: str, chunks: list[PolicyChunk]) -> list[tuple[str, PolicyChunk]]:
    query_terms = content_terms(question)
    scored: list[tuple[float, str, PolicyChunk]] = []

    for chunk_index, chunk in enumerate(chunks):
        cleaned = _clean_markdown(chunk.text)
        for sentence in re.split(r"(?<=[.!?])\s+", cleaned):
            sentence = sentence.strip()
            if len(sentence) < 20:
                continue
            sentence_terms = content_terms(sentence)
            overlap = len(query_terms & sentence_terms)
            if overlap:
                density = overlap / max(len(sentence_terms), 1)
                chunk_boost = max(0, len(chunks) - chunk_index) * 0.25
                score = overlap + density + chunk_boost
                scored.append((score, sentence, chunk))

    ranked = sorted(scored, key=lambda item: (item[0], len(item[1])), reverse=True)
    return [(sentence, chunk) for _, sentence, chunk in ranked]


def _clean_markdown(text: str) -> str:
    cleaned = re.sub(r"[*_`#>-]", "", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _strip_thinking(text: str) -> str:
    without_closed_blocks = re.sub(
        r"<think>.*?</think>",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return re.sub(
        r"<think>.*$",
        "",
        without_closed_blocks,
        flags=re.DOTALL | re.IGNORECASE,
    )
