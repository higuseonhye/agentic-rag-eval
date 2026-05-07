from __future__ import annotations

from typing import Any

from qdrant_client import QdrantClient
from qdrant_client.http import models as qm

from app.core.config import settings
from app.retrieval.types import RetrievalResult


class QdrantVectorStore:
    """Dense retrieval via Qdrant + FastEmbed (same embedding model at index and query time)."""

    backend_name = "qdrant"

    def __init__(self) -> None:
        self._url = settings.qdrant_url
        self._collection = settings.qdrant_collection
        self._client = QdrantClient(url=self._url)
        self._embedding_model_name = settings.fastembed_model
        self._embedder = None  # lazy FastEmbed TextEmbedding

    def _get_embedder(self):  # noqa: ANN202
        try:
            from fastembed import TextEmbedding
        except ImportError as e:
            raise RuntimeError(
                "fastembed is required for Qdrant vector store. Install with: pip install fastembed"
            ) from e
        if self._embedder is None:
            self._embedder = TextEmbedding(model_name=self._embedding_model_name)
        return self._embedder

    def _embed(self, texts: list[str]) -> list[list[float]]:
        emb = self._get_embedder()
        return [list(v) for v in emb.embed(texts)]

    def _ensure_collection(self, vector_size: int) -> None:
        collections = self._client.get_collections().collections
        names = {c.name for c in collections}
        if self._collection not in names:
            self._client.create_collection(
                collection_name=self._collection,
                vectors_config=qm.VectorParams(size=vector_size, distance=qm.Distance.COSINE),
            )

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        if not ids:
            return
        vectors = self._embed(texts)
        self._ensure_collection(len(vectors[0]))
        points = []
        for i, cid in enumerate(ids):
            payload = {**(metadatas[i] if i < len(metadatas) else {}), "chunk_id": cid, "text": texts[i]}
            points.append(qm.PointStruct(id=cid, vector=vectors[i], payload=payload))
        self._client.upsert(collection_name=self._collection, points=points)

    def query_similar(self, *, query: str, k: int) -> tuple[list[RetrievalResult], dict[str, Any]]:
        diagnostics: dict[str, Any] = {"backend": self.backend_name, "collection": self._collection}
        q = query.strip()
        try:
            qvec = self._embed([q])[0]
        except Exception as e:  # noqa: BLE001
            diagnostics["vector_error"] = str(e)
            return [], diagnostics

        try:
            hits = self._client.search(
                collection_name=self._collection,
                query_vector=qvec,
                limit=k,
                with_payload=True,
            )
        except Exception as e:  # noqa: BLE001
            diagnostics["vector_error"] = str(e)
            return [], diagnostics

        out: list[RetrievalResult] = []
        for h in hits:
            pl = dict(h.payload or {})
            text = str(pl.get("text") or "")
            chunk_id = str(pl.get("chunk_id") or h.id)
            doc_id = pl.get("doc_id")
            score = float(h.score) if h.score is not None else 0.0
            meta = {k: v for k, v in pl.items() if k != "text"}
            out.append(
                RetrievalResult(
                    chunk_id=chunk_id,
                    doc_id=str(doc_id) if doc_id is not None else None,
                    text=text,
                    source="qdrant",
                    score=score,
                    metadata=meta,
                )
            )
        diagnostics["vector_count"] = len(out)
        return out, diagnostics
