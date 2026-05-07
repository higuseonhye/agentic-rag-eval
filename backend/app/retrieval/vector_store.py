from __future__ import annotations

from typing import Any, Protocol

from app.retrieval.types import RetrievalResult


def get_vector_store():
    """Return dense vector backend based on settings.vector_backend."""
    from app.core.config import settings

    if settings.vector_backend == "chroma":
        from app.retrieval.chroma_vector_store import ChromaVectorStore

        return ChromaVectorStore()
    from app.retrieval.qdrant_store import QdrantVectorStore

    return QdrantVectorStore()


class VectorStore(Protocol):
    """Dense vector index abstraction (Qdrant, Chroma, etc.)."""

    backend_name: str

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        """Index chunk texts with metadata."""
        ...

    def query_similar(self, *, query: str, k: int) -> tuple[list[RetrievalResult], dict[str, Any]]:
        """Return top-k chunks by semantic similarity + diagnostics."""
        ...
