"""Application settings loaded from environment and backend/.env."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from gridline.events.payloads import DataMode

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

    data_dir: Path = Path("data")
    sim_tick_seconds: float = Field(default=1.0, gt=0, description="Real seconds per tick at speed 1.0")
    sim_minutes_per_tick: int = Field(default=5, ge=1, description="Simulated minutes advanced per tick")
    sim_default_scenario: str = "cascading_landslide_flood"
    sim_default_seed: int = 42
    sim_autostart: bool = False
    ws_heartbeat_seconds: float = Field(default=15.0, gt=0)
    event_queue_size: int = Field(default=1000, ge=1)

    data_mode: DataMode = "demo"  # the mode at startup; switchable at runtime via POST /api/source
    live_poll_seconds: float = Field(default=300.0, gt=0, description="Open-Meteo poll interval in LIVE mode")
    live_forecast_base_url: str = "https://api.open-meteo.com/v1/forecast"

    # The agent's LLM: a local Ollama model; "mock" uses the offline heuristic reasoner only.
    llm_provider: Literal["ollama", "mock"] = "ollama"
    ollama_host: str = "http://127.0.0.1:11434"  # IPv4: "localhost" can stall trying ::1 first on Windows
    ollama_model: str = "qwen2.5:7b-instruct"
    llm_timeout_seconds: float = Field(default=180.0, gt=0)

    def resolved_corpus_dir(self) -> Path:
        """Corpus directory as an absolute path (relative paths are relative to backend/)."""
        return self.corpus_dir if self.corpus_dir.is_absolute() else BACKEND_DIR / self.corpus_dir

    def resolved_data_dir(self) -> Path:
        """Data directory (holding city/ and corpus/) as an absolute path, relative to backend/."""
        return self.data_dir if self.data_dir.is_absolute() else BACKEND_DIR / self.data_dir
