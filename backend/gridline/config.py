"""Application settings loaded from environment and backend/.env."""

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

EmbeddingProvider = Literal["auto", "fastembed", "hashed"]

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    """Runtime configuration. Secrets never appear in code or logs."""

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    database_url: str = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline"
    test_database_url: str = "postgresql+psycopg://gridline:gridline@localhost:5433/gridline_test"
    embedding_provider: EmbeddingProvider = "auto"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    corpus_dir: Path = Path("data/corpus")
    rag_top_k: int = 8

    def resolved_corpus_dir(self) -> Path:
        """Corpus directory as an absolute path (relative paths are relative to backend/)."""
        return self.corpus_dir if self.corpus_dir.is_absolute() else BACKEND_DIR / self.corpus_dir
