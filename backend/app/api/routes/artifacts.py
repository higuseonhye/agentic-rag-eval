from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.multimodal.ingest import attach_transcript_segments, ingest_video_lite
from app.multimodal.models import Artifact


router = APIRouter()


class TranscriptSegment(BaseModel):
    t_start: float = 0.0
    t_end: float = 0.0
    text: str = Field(min_length=1)


class TranscriptAttachRequest(BaseModel):
    segments: list[TranscriptSegment]


@router.post("/video")
async def upload_video(
    db: Session = Depends(get_db),
    file: UploadFile = File(...),
    keyframe_every_seconds: int = 5,
) -> dict[str, Any]:
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty upload")
    art = ingest_video_lite(
        db=db,
        filename=file.filename or "video.bin",
        file_bytes=raw,
        transcript_segments=None,
        keyframe_every_seconds=keyframe_every_seconds,
    )
    return {"artifact_id": art.artifact_id, "meta": art.meta, "transcript_doc_id": art.transcript_doc_id}


@router.post("/transcript/{artifact_id}")
def attach_transcript(artifact_id: str, payload: TranscriptAttachRequest, db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        art = attach_transcript_segments(
            db=db,
            artifact_id=artifact_id,
            segments=[s.model_dump() for s in payload.segments],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"artifact_id": art.artifact_id, "transcript_doc_id": art.transcript_doc_id, "meta": art.meta}


@router.get("/{artifact_id}")
def get_artifact(artifact_id: str, db: Session = Depends(get_db)) -> dict[str, Any]:
    art = db.get(Artifact, artifact_id)
    if art is None:
        raise HTTPException(status_code=404, detail="artifact not found")
    return {
        "artifact_id": art.artifact_id,
        "kind": art.kind,
        "storage_path": art.storage_path,
        "meta": art.meta,
        "transcript_doc_id": art.transcript_doc_id,
        "created_at": art.created_at.isoformat(),
    }
