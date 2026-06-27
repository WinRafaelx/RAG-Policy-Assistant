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


def test_chunking_uses_document_section_when_markdown_has_no_headings(tmp_path) -> None:
    policy_file = tmp_path / "plain_policy.md"
    policy_file.write_text(
        "Employees must follow all security procedures.\n"
        "***\n"
        "Synthetic training document. Not an official ttb policy.",
        encoding="utf-8",
    )

    chunks = chunk_markdown_file(policy_file)

    assert len(chunks) == 1
    assert chunks[0].section == "Document"
    assert chunks[0].text == "Employees must follow all security procedures."


def test_chunking_splits_large_sections_without_empty_parts(tmp_path) -> None:
    policy_file = tmp_path / "large_policy.md"
    policy_file.write_text(
        "# Large Policy\n\n"
        "First paragraph about annual leave eligibility.\n\n"
        "Second paragraph about annual leave allowance.\n\n"
        "Third paragraph about annual leave carry-over.",
        encoding="utf-8",
    )

    chunks = chunk_markdown_file(policy_file, target_chars=70)

    assert len(chunks) > 1
    assert [chunk.chunk_id for chunk in chunks] == [
        "large_policy.md:001",
        "large_policy.md:002",
        "large_policy.md:003",
    ]
    assert all(chunk.section == "Large Policy" for chunk in chunks)
    assert all(chunk.text.strip() for chunk in chunks)
