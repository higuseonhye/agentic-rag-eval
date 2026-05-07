from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.exc import OperationalError

from app.core.db import Base, engine
from app.evaluation import models as _evaluation_models  # noqa: F401
from app.knowledge_engine.compilation import models as _ku_models  # noqa: F401
from app.memory import models as _memory_models  # noqa: F401
from app.multimodal import models as _multimodal_models  # noqa: F401
from app.replay import models as _replay_models  # noqa: F401
from app.retrieval import models as _retrieval_models  # noqa: F401
from app.state_management import models as _workflow_models  # noqa: F401
from app.tracing import models as _trace_models  # noqa: F401

from app.api.router import api_router


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        # MVP: create tables automatically. We'll switch to Alembic migrations next.
        # Don't fail import/startup if Postgres isn't up yet.
        try:
            Base.metadata.create_all(bind=engine)
        except OperationalError:
            pass
        yield

    app = FastAPI(title="ADW Platform API", version="0.1.0", lifespan=lifespan)

    app.include_router(api_router)
    return app


app = create_app()

