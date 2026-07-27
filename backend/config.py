"""App settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    google_api_key: str = ""
    openai_api_key: str = ""
    llm_provider: str = "gemini"  # gemini | openai
    gemini_model: str = "gemini-3.1-flash-lite"
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    # Comma-separated origins, or "*" for any (credentials disabled when "*")
    cors_origins: str = "http://localhost:5173,http://localhost:5174,http://127.0.0.1:5173"

    # Production controls
    api_key: str = ""  # If set, required for upload/ingest/delete via X-API-Key
    rate_limit: str = "30/minute"
    enable_auth: bool = True
    # Serve Vite build from FastAPI when frontend/dist exists
    serve_frontend: bool = True

    data_dir: Path = ROOT / "data"
    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    sample_dir: Path = ROOT / "data" / "sample"
    mappings_path: Path = ROOT / "data" / "mappings" / "ipc_bns_map.json"
    index_path: Path = ROOT / "data" / "processed" / "faiss_index"
    frontend_dist: Path = ROOT / "frontend" / "dist"

    chunk_size: int = 600
    chunk_overlap: int = 80
    top_k: int = 4
    max_expand_queries: int = 3

    def model_post_init(self, __context) -> None:
        self.google_api_key = self.google_api_key.strip().strip("\"'")
        self.openai_api_key = self.openai_api_key.strip().strip("\"'")
        self.api_key = self.api_key.strip().strip("\"'")
        self.llm_provider = self.llm_provider.strip().lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    get_settings.cache_clear()
    return get_settings()
