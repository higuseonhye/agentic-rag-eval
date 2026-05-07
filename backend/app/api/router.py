from __future__ import annotations

from fastapi import APIRouter

from app.api.routes import docs, evaluations, runs, traces

api_router = APIRouter(prefix="/api")
api_router.include_router(runs.router, prefix="/runs", tags=["runs"])
api_router.include_router(traces.router, prefix="/traces", tags=["traces"])
api_router.include_router(docs.router, prefix="/docs", tags=["docs"])
api_router.include_router(evaluations.router, prefix="/evaluations", tags=["evaluations"])

