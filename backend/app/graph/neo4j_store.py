from __future__ import annotations

from typing import Any

from app.core.config import settings


class Neo4jGraphStore:
    """Entity–chunk graph for multi-hop-style augmentation (L3/L4)."""

    def __init__(self) -> None:
        self._driver: Any = None
        if not settings.graph_enabled:
            return
        try:
            from neo4j import GraphDatabase
        except ImportError:
            return
        try:
            self._driver = GraphDatabase.driver(
                settings.neo4j_uri,
                auth=(settings.neo4j_user, settings.neo4j_password),
            )
            self._driver.verify_connectivity()
        except Exception:  # noqa: BLE001
            self._driver = None

    @property
    def available(self) -> bool:
        return self._driver is not None

    def sync_chunk_entities(self, *, chunk_id: str, doc_id: str, entities: list[str]) -> None:
        if not self.available or not entities:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.doc_id = $doc_id
                WITH c
                UNWIND $entities AS en
                MERGE (e:Entity {name: en})
                MERGE (e)-[:MENTIONED_IN]->(c)
                """,
                chunk_id=chunk_id,
                doc_id=doc_id,
                entities=entities[:80],
            )

    def link_unit_to_chunk(self, *, unit_id: str, chunk_id: str) -> None:
        if not self.available:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (u:KnowledgeUnit {unit_id: $unit_id})
                MERGE (c:Chunk {chunk_id: $chunk_id})
                MERGE (u)-[:CITES]->(c)
                """,
                unit_id=unit_id,
                chunk_id=chunk_id,
            )

    def link_artifact_segment(self, *, artifact_id: str, chunk_like_id: str, label: str = "HAS_SEGMENT") -> None:
        """Link multimodal transcript/keyframe pseudo-chunks into the graph."""
        if not self.available:
            return
        with self._driver.session() as session:
            session.run(
                """
                MERGE (a:Artifact {artifact_id: $artifact_id})
                MERGE (s:Chunk {chunk_id: $chunk_id})
                MERGE (a)-[r:HAS_SEGMENT]->(s)
                SET r.label = $label
                """,
                artifact_id=artifact_id,
                chunk_id=chunk_like_id,
                label=label,
            )

    def neighbor_chunk_ids(self, seed_ids: list[str], *, limit: int = 8) -> list[str]:
        if not self.available or not seed_ids:
            return []
        with self._driver.session() as session:
            rec = session.run(
                """
                MATCH (c:Chunk)
                WHERE c.chunk_id IN $seed
                MATCH (c)<-[:MENTIONED_IN]-(e:Entity)-[:MENTIONED_IN]->(c2:Chunk)
                WHERE NOT c2.chunk_id IN $seed
                RETURN DISTINCT c2.chunk_id AS cid
                LIMIT $limit
                """,
                seed=seed_ids,
                limit=limit,
            )
            return [r["cid"] for r in rec if r.get("cid")]

    def close(self) -> None:
        if self._driver:
            self._driver.close()


_store: Neo4jGraphStore | None = None


def get_graph_store() -> Neo4jGraphStore | None:
    global _store
    if _store is None:
        _store = Neo4jGraphStore()
    return _store if _store.available else None
