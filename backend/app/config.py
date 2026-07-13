"""Application settings loaded from environment / .env file."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Loads the repo-root .env whether run from the root or backend/ directory
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    # Database
    database_url: str = "postgresql+asyncpg://synapse:synapse_dev@localhost:5432/synapse"

    # ChromaDB
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3:8b"

    # Job source API keys
    usajobs_api_key: str = ""
    usajobs_user_agent: str = ""
    adzuna_app_id: str = ""
    adzuna_app_key: str = ""
    jooble_api_key: str = ""

    # Search / ingestion (P2)
    search_keywords_primary: str = "AI Architect"
    greenhouse_companies: str = ""  # comma-separated board slugs, e.g. "anthropic,stripe"
    lever_companies: str = ""  # comma-separated slugs
    ingest_interval_minutes: int = 360
    scheduler_enabled: bool = True

    # Matching engine (P3)
    embedding_model: str = "all-MiniLM-L6-v2"
    # Surfacing threshold for the UI queue. PRD proposes 0.85, but MiniLM cosine
    # scores rarely reach that for real text pairs — calibrate with
    # scripts/calibrate_threshold.py (P3.5) before trusting any value here.
    alignment_threshold: float = 0.50

    # Observability (P7)
    phoenix_enabled: bool = True
    phoenix_endpoint: str = "http://localhost:6006/v1/traces"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000"


settings = Settings()
