from __future__ import annotations

from typing import Any

from app.retrieval.chroma_client import get_chroma_client, get_default_collection_name
from app.retrieval.types import RetrievalResult


class ChromaVectorStore:
    backend_name = "chroma"

    def __init__(self) -> None:
        self._client = get_chroma_client()
        self._collection_name = get_default_collection_name()

    def upsert_chunks(
        self,
        *,
        ids: list[str],
        texts: list[str],
        metadatas: list[dict[str, Any]],
    ) -> None:
        col = self._client.get_or_create_collection(self._collection_name)
        col.add(ids=ids, documents=texts, metadatas=metadatas)

    def query_similar(self, *, query: str, k: int) -> tuple[list[RetrievalResult], dict[str, Any]]:
        diagnostics: dict[str, Any] = {"backend": self.backend_name}
        col = self._client.get_or_create_collection(self._collection_name)
        res = col.query(query_texts=[query.strip()], n_results=k, include=["documents", "metadatas", "distances"])
        docs = (res.get("documents") or [[]])[0]
        metas = (res.get("metadatas") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out: list[RetrievalResult] = []
        for doc_text, md, d in zip(docs, metas, dists, strict=False):
            md = dict(md or {})
            chunk_id = str(md.get("chunk_id") or md.get("id") or "")
            sim = 1.0 / (1.0 + float(d))
            out.append(
                RetrievalResult(
                    chunk_id=chunk_id or "unknown",
                    doc_id=md.get("doc_id"),
                    text=str(doc_text),
                    source="chroma",
                    score=float(sim),
                    metadata=md,
                )
            )
        diagnostics["vector_count"] = len(out)
        return out, diagnostics
