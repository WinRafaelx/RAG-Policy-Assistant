from pathlib import Path

from app.domain.services.chunking import chunk_markdown_file, load_policy_chunks


def test_chunk_markdown_file_preserves_metadata() -> None:
    chunks = chunk_markdown_file(Path("data/policies/policy_01_annual_leave.md"))

    assert chunks
    assert chunks[0].document == "policy_01_annual_leave.md"
    assert chunks[0].chunk_id.startswith("policy_01_annual_leave.md:")
    assert "Annual Leave Policy" in chunks[0].text


def test_chunking_does_not_create_empty_chunks() -> None:
    chunks = load_policy_chunks(Path("data/policies"))

    assert len(chunks) >= 18
    assert all(chunk.text.strip() for chunk in chunks)
    assert all(chunk.section for chunk in chunks)
