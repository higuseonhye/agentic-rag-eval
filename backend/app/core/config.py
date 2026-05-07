from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: str = "dev"

    database_url: str = "postgresql+psycopg://app:app@localhost:5432/agentic_rag_eval"
    chroma_http_url: str = "http://localhost:8001"

    # Optional: OpenAI-compatible endpoint for router + judge
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_model: str = "gpt-4.1-mini"

    # ADW constraints
    max_workflow_iterations: int = 6
    max_retrieval_iterations: int = 3
    max_tools_per_workflow: int = 20

    # Retrieval loop / stopping conditions
    retrieval_target_coverage: float = 0.75
    retrieval_min_gain: float = 0.03


settings = Settings()

