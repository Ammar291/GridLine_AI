from pathlib import Path

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
