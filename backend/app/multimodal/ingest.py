from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.graph.neo4j_store import get_graph_store
from app.knowledge_engine.entities import extract_entities_heuristic
from app.multimodal.models import Artifact
from app.retrieval.repository import RetrievalRepository
from app.retrieval.vector_store import get_vector_store


def artifacts_root() -> Path:
    root = Path(__file__).resolve().parents[2] / "storage" / "artifacts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def extract_keyframes(*, video_path: Path, out_dir: Path, every_seconds: int = 5) -> list[dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = str(out_dir / "kf_%04d.jpg")
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps=1/{every_seconds}",
        pattern,
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return []

    frames: list[dict[str, Any]] = []
    for i, p in enumerate(sorted(out_dir.glob("kf_*.jpg"))):
        frames.append({"index": i, "path": str(p), "approx_t_sec": i * every_seconds})
    return frames


def ingest_video_lite(
    *,
    db: Session,
    filename: str,
    file_bytes: bytes,
    transcript_segments: list[dict[str, Any]] | None,
    keyframe_every_seconds: int = 5,
) -> Artifact:
    aid = str(uuid.uuid4())
    safe_name = filename.replace("..", "_").replace("/", "_")[-200:]
    base = artifacts_root() / aid
    base.mkdir(parents=True, exist_ok=True)
    video_path = base / safe_name
    video_path.write_bytes(file_bytes)

    kf_dir = base / "keyframes"
    frames = extract_keyframes(video_path=video_path, out_dir=kf_dir, every_seconds=keyframe_every_seconds)

    artifact = Artifact(
        artifact_id=aid,
        kind="video",
        storage_path=str(video_path),
        meta={
            "filename": safe_name,
            "keyframes": frames,
            "keyframe_every_seconds": keyframe_every_seconds,
            "vector_backend": settings.vector_backend,
        },
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    if transcript_segments:
        _attach_transcript_segments(db=db, artifact=artifact, segments=transcript_segments)

    db.refresh(artifact)
    return artifact


def attach_transcript_segments(
    *,
    db: Session,
    artifact_id: str,
    segments: list[dict[str, Any]],
) -> Artifact:
    art = db.get(Artifact, artifact_id)
    if art is None:
        raise ValueError("artifact not found")
    if art.transcript_doc_id:
        raise ValueError("transcript already attached")
    _attach_transcript_segments(db=db, artifact=art, segments=segments)
    db.refresh(art)
    return art


def _attach_transcript_segments(*, db: Session, artifact: Artifact, segments: list[dict[str, Any]]) -> None:
    repo = RetrievalRepository(db)
    doc = repo.create_document(
        title=f"Transcript: {(artifact.meta or {}).get('filename') or artifact.artifact_id}",
        source=f"artifact:{artifact.artifact_id}",
        metadata={"artifact_id": artifact.artifact_id, "kind": "video_transcript"},
    )

    texts: list[str] = []
    metas: list[dict[str, Any] | None] = []
    for seg in segments:
        t0 = float(seg.get("t_start") or 0.0)
        t1 = float(seg.get("t_end") or t0)
        txt = str(seg.get("text") or "").strip()
        if not txt:
            continue
        texts.append(txt)
        metas.append(
            {
                "artifact_id": artifact.artifact_id,
                "t_start": t0,
                "t_end": t1,
                "modality": "transcript_segment",
            }
        )

    if not texts:
        return

    stored = repo.add_chunks_per_meta(doc_id=doc.doc_id, chunk_texts=texts, chunk_metas=metas)
    artifact.transcript_doc_id = doc.doc_id
    artifact.meta = {**(artifact.meta or {}), "transcript_segment_count": len(stored)}
    db.commit()
    db.refresh(artifact)

    store = get_vector_store()
    store.upsert_chunks(
        ids=[c.chunk_id for c in stored],
        texts=[c.text for c in stored],
        metadatas=[
            {"doc_id": c.doc_id, "chunk_id": c.chunk_id, "artifact_id": artifact.artifact_id, **(c.meta or {})}
            for c in stored
        ],
    )

    graph = get_graph_store()
    if graph:
        for c in stored:
            ents = extract_entities_heuristic(c.text)
            graph.sync_chunk_entities(chunk_id=c.chunk_id, doc_id=c.doc_id, entities=ents)
            graph.link_artifact_segment(artifact_id=artifact.artifact_id, chunk_like_id=c.chunk_id, label="TRANSCRIPT")
