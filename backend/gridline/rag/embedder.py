"""Embedding providers: a local fastembed model, or a deterministic hashed fallback (spec §7).

Embedding is CPU-bound and synchronous; async callers wrap it in ``asyncio.to_thread``.
"""

import hashlib
import logging
import math
import re
from itertools import pairwise
from typing import TYPE_CHECKING, Protocol

from gridline.config import EmbeddingProvider
from gridline.db.models import EMBEDDING_DIMENSION

if TYPE_CHECKING:
    from fastembed import TextEmbedding

log = logging.getLogger(__name__)

# Words, decimals and asset ids ("0.70", "d-7", "sl-hv-3") are single tokens.
TOKEN = re.compile(r"[a-z0-9]+(?:[.\-][a-z0-9]+)*")
STOPWORD_TEXT = (
    "a an the and or but of to in on at by for from with as into onto than then so if is are was were be "
    "been being it its this that these those which who whom what there their they them he she we you our "
    "your i shall should may must will would can could has have had do does did all any each such other also"
)
STOPWORDS = frozenset(STOPWORD_TEXT.split())


class Embedder(Protocol):
    @property
    def name(self) -> str: ...

    @property
    def dimension(self) -> int: ...

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


def _stem(word: str) -> str:
    """Strip one common inflection so "blocked", "blocking" and "blocks" all become "block"."""
    if not word.isalpha() or len(word) <= 4:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    for suffix in ("ing", "ed"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word[:-1] if word.endswith("s") and not word.endswith("ss") else word


def _features(text: str) -> list[str]:
    """Stemmed content words, the pieces of hyphenated tokens ("2025-05-20" -> "2025"), and word bigrams."""
    words = [_stem(w) for w in TOKEN.findall(text.lower()) if len(w) > 1 and w not in STOPWORDS]
    pieces = [_stem(p) for w in words if "-" in w for p in w.split("-") if len(p) > 1]
    return words + pieces + [f"{a} {b}" for a, b in pairwise(words)]


class HashedEmbedder:
    """Feature hashing of words and bigrams: deterministic, offline, lexical rather than semantic."""

    def __init__(self, dimension: int = EMBEDDING_DIMENSION) -> None:
        self._dimension = dimension

    @property
    def name(self) -> str:
        return "hashed:v1"

    @property
    def dimension(self) -> int:
        return self._dimension

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._embed(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._embed(text)

    def _embed(self, text: str) -> list[float]:
        vec = [0.0] * self._dimension
        for feature in _features(text):
            digest = hashlib.sha1(feature.encode("utf-8")).digest()
            bucket = int.from_bytes(digest[:4], "big") % self._dimension
            vec[bucket] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec


class FastEmbedEmbedder:
    """fastembed's local ONNX text embedding. The model loads on first use (one-time download)."""

    def __init__(self, model_name: str) -> None:
        self._model_name = model_name
        self._model: TextEmbedding | None = None

    @property
    def name(self) -> str:
        return f"fastembed:{self._model_name}"

    @property
    def dimension(self) -> int:
        return EMBEDDING_DIMENSION

    def warm_up(self) -> None:
        """Import fastembed and load the model; raises if either is unavailable (e.g. offline, no cache)."""
        if self._model is None:
            from fastembed import TextEmbedding  # heavy import, deferred until the provider is used

            self._model = TextEmbedding(model_name=self._model_name)

    def _loaded(self) -> "TextEmbedding":
        self.warm_up()
        assert self._model is not None
        return self._model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[float(x) for x in vec] for vec in self._loaded().embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        vectors = [[float(x) for x in vec] for vec in self._loaded().query_embed(text)]
        return vectors[0]


def build_embedder(provider: EmbeddingProvider, model_name: str) -> Embedder:
    """``hashed``/``fastembed`` are taken as asked; ``auto`` prefers fastembed, falling back to hashed."""
    if provider == "hashed":
        return HashedEmbedder()
    fast = FastEmbedEmbedder(model_name)
    if provider == "fastembed":
        return fast
    try:
        fast.warm_up()
    except Exception as exc:  # any failure (import, download, ONNX runtime) means: stay offline-capable
        log.warning(
            "fastembed model %s unavailable (%s); falling back to hashed embedder",
            model_name,
            type(exc).__name__,
        )
        return HashedEmbedder()
    return fast
