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
    cors_origins: str = "http://localhost:5173,http://localhost:5174"

    data_dir: Path = ROOT / "data"
    raw_dir: Path = ROOT / "data" / "raw"
    processed_dir: Path = ROOT / "data" / "processed"
    sample_dir: Path = ROOT / "data" / "sample"
    mappings_path: Path = ROOT / "data" / "mappings" / "ipc_bns_map.json"
    index_path: Path = ROOT / "data" / "processed" / "faiss_index"

    chunk_size: int = 600
    chunk_overlap: int = 80
    top_k: int = 6

    def model_post_init(self, __context) -> None:
        # Strip whitespace / accidental quotes from pasted keys
        self.google_api_key = self.google_api_key.strip().strip("\"'")
        self.openai_api_key = self.openai_api_key.strip().strip("\"'")
        self.llm_provider = self.llm_provider.strip().lower()


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reload_settings() -> Settings:
    """Clear cache so .env edits are picked up without a full process restart."""
    get_settings.cache_clear()
    return get_settings()
