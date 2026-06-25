from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chunking import load_policy_chunks


def main() -> None:
    chunks = load_policy_chunks(Path("policies"))
    documents = {chunk.document for chunk in chunks}
    print(f"Loaded {len(chunks)} chunks from {len(documents)} policy documents.")
    for chunk in chunks[:5]:
        print(f"- {chunk.chunk_id} | {chunk.section}")


if __name__ == "__main__":
    main()
