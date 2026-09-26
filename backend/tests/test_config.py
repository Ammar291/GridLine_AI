from pathlib import Path

import pytest

from gridline.config import Settings


def test_defaults_are_offline_friendly(monkeypatch):
    for key in ("DATABASE_URL", "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "CORPUS_DIR", "RAG_TOP_K"):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql+psycopg://")
    assert settings.database_url.endswith(":5433/gridline")
    assert settings.embedding_provider == "auto"
    assert settings.embedding_model == "BAAI/bge-small-en-v1.5"
    assert settings.corpus_dir == Path("data/corpus")
    assert settings.rag_top_k == 8


def test_env_overrides(monkeypatch):
    monkeypatch.setenv("EMBEDDING_PROVIDER", "hashed")
    monkeypatch.setenv("RAG_TOP_K", "3")
    settings = Settings(_env_file=None)
    assert settings.embedding_provider == "hashed"
    assert settings.rag_top_k == 3


def test_simulation_defaults(monkeypatch):
    for key in (
        "SIM_TICK_SECONDS",
        "SIM_MINUTES_PER_TICK",
        "SIM_DEFAULT_SCENARIO",
        "SIM_DEFAULT_SEED",
        "SIM_AUTOSTART",
        "WS_HEARTBEAT_SECONDS",
        "EVENT_QUEUE_SIZE",
        "DATA_DIR",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings(_env_file=None)
    assert settings.sim_tick_seconds == 1.0
    assert settings.sim_minutes_per_tick == 5
    assert settings.sim_default_scenario == "cascading_landslide_flood"
    assert settings.sim_default_seed == 42
    assert settings.sim_autostart is False
    assert settings.ws_heartbeat_seconds == 15.0
    assert settings.event_queue_size == 1000
    assert settings.data_dir == Path("data")
    assert settings.resolved_data_dir().is_absolute()
    assert (settings.resolved_data_dir() / "city" / "zones.yaml").is_file()


def test_simulation_env_overrides(monkeypatch):
    monkeypatch.setenv("SIM_TICK_SECONDS", "0.25")
    monkeypatch.setenv("SIM_AUTOSTART", "true")
    settings = Settings(_env_file=None)
    assert settings.sim_tick_seconds == 0.25
    assert settings.sim_autostart is True


def test_rejects_non_positive_tick():
    with pytest.raises(ValueError):
        Settings(_env_file=None, sim_tick_seconds=0)
