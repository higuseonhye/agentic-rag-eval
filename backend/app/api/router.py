from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import artifacts, docs, evaluations, knowledge, memory, replay, runs, traces

api_router = APIRouter(prefix="/api")
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(traces.router, prefix="/traces", tags=["traces"])
api_router.include_router(docs.router, prefix="/docs", tags=["docs"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])
api_router.include_router(memory.router, prefix="/memory", tags=["memory"])
api_router.include_router(knowledge.router, prefix="/knowledge", tags=["knowledge"])
api_router.include_router(replay.router, prefix="/replay", tags=["replay"])
api_router.include_router(artifacts.router, prefix="/artifacts", tags=["artifacts"])

