from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True)
class PolicyChunk:
    chunk_id: str
    document: str
    section: str
    text: str


HEADING_PATTERN = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def load_policy_chunks(policies_dir: Path) -> list[PolicyChunk]:
    markdown_files = sorted(policies_dir.glob("*.md"))
    chunks: list[PolicyChunk] = []
    for file_path in markdown_files:
        chunks.extend(chunk_markdown_file(file_path))
    return chunks


def chunk_markdown_file(file_path: Path, target_chars: int = 1200) -> list[PolicyChunk]:
    text = _strip_synthetic_footer(file_path.read_text(encoding="utf-8"))
    sections = _split_sections(text)
    chunks: list[PolicyChunk] = []

    for section_title, section_text in sections:
        for part in _split_to_target_size(section_text, target_chars):
            chunk_number = len(chunks) + 1
            chunks.append(
                PolicyChunk(
                    chunk_id=f"{file_path.name}:{chunk_number:03d}",
                    document=file_path.name,
                    section=section_title,
                    text=part.strip(),
                )
            )

    return chunks


def _strip_synthetic_footer(text: str) -> str:
    text = re.sub(r"\n\*{3}\s*\n*", "\n", text)
    return re.sub(
        r"\n?Synthetic training document\. Not an official ttb policy\.\s*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()


def _split_sections(text: str) -> list[tuple[str, str]]:
    matches = list(HEADING_PATTERN.finditer(text))
    if not matches:
        return [("Document", text)]

    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        title = match.group(2).strip()
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        section_text = text[start:end].strip()
        if section_text:
            sections.append((title, section_text))
    return sections


def _split_to_target_size(text: str, target_chars: int) -> list[str]:
    if len(text) <= target_chars:
        return [text]

    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in paragraphs:
        projected_len = current_len + len(paragraph) + 2
        if current and projected_len > target_chars:
            chunks.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len = projected_len

    if current:
        chunks.append("\n\n".join(current))

    return chunks


def enrich_chunk_text(chunk: PolicyChunk) -> str:
    doc_name = chunk.document.replace("policy_", "").replace(".md", "").replace("_", " ").strip().title()
    return f"Document: {doc_name}\nSection: {chunk.section}\nContent: {chunk.text}"

