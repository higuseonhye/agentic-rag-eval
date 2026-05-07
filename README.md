## Agentic RAG Evaluation Platform (MVP)

Developer-first evaluation + observability platform for **Agentic RAG workflows**: execution tracing, process-aware scoring, and trajectory visualization.

### Demo screenshots

Home:

![Home](docs/screenshots/home.png)

Traces (list):

![Traces](docs/screenshots/traces.png)

Evaluations:

![Evaluations](docs/screenshots/evaluations.png)

### What’s in the MVP
- **Backend**: FastAPI + SQLAlchemy + Postgres + Redis (Celery-ready)
- **Agent orchestration**: LangGraph workflow that emits **step-level traces**
- **Vector DB**: Chroma (initial)
- **Evaluation**: DeepEval integration scaffold + custom process metrics scaffold
- **Frontend**: Next.js + Tailwind + React Flow trace/trajectory viewer

### Repo layout
- `backend/`: FastAPI app, agents, tracing, retrieval, evaluation
- `frontend/`: Next.js UI (trace explorer + trajectory graph)
- `docker-compose.yml`: Postgres, Redis, Chroma, (optional) services

### Quickstart (Docker)
1. Start infra:

```bash
docker compose up -d
```

2. Backend (dev):

```bash
cd backend
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

3. Frontend (dev):

```bash
cd frontend
npm install
npm run dev
```

### URLs
- Backend API: `http://localhost:8000`
- OpenAPI docs: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

