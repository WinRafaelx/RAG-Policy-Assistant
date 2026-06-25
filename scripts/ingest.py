from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.chunking import load_policy_chunks
from app.config import get_settings
from app.embeddings import SentenceTransformerEmbeddingProvider
from app.stores.pgvector_store import PgVectorStore


def main() -> None:
    settings = get_settings()
    chunks = load_policy_chunks(settings.policies_dir)
    documents = {chunk.document for chunk in chunks}
    print(f"Loaded {len(chunks)} chunks from {len(documents)} policy documents.")

    if settings.retrieval_backend == "pgvector":
        if not settings.database_url:
            raise RuntimeError("TTB_DATABASE_URL is required when TTB_RETRIEVAL_BACKEND=pgvector")
        provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
        store = PgVectorStore(settings.database_url, provider)
        upserted = store.upsert_chunks(chunks)
        print(f"Upserted {upserted} chunks into pgvector.")
        print(f"Database now contains {store.count_chunks()} chunks.")
        return

    for chunk in chunks[:5]:
        print(f"- {chunk.chunk_id} | {chunk.section}")


if __name__ == "__main__":
    main()
