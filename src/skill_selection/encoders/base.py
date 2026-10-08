"""Text encoders: common interface and an on-disk embedding cache.

Input: texts plus their kind ("query" for tasks, "document" for skills); models with asymmetric prompts treat the two
differently. Output: an (n, dim) float32 matrix with L2-normalised rows, so cosine similarity is a dot product.
The cache key covers backend, model, revision, kind, query prompt and text, so changing any of them re-encodes.
"""
from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

KINDS = ("query", "document")


class Encoder(ABC):
    backend: str = ""
    model: str = ""
    revision: str = ""
    query_prompt: str = ""

    @property
    def spec(self) -> str:
        return f"{self.backend}:{self.model}@{self.revision}"

    def info(self) -> Dict[str, str]:
        return {"spec": self.spec, "backend": self.backend, "model": self.model, "revision": self.revision,
                "query_prompt": self.query_prompt}

    def encode(self, texts: Sequence[str], kind: str) -> np.ndarray:
        if kind not in KINDS:
            raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
        vectors = np.asarray(self._encode(list(texts), kind), dtype=np.float32)
        return vectors / np.clip(np.linalg.norm(vectors, axis=1, keepdims=True), 1e-12, None)

    @abstractmethod
    def _encode(self, texts: List[str], kind: str) -> np.ndarray:
        ...


class EmbeddingCache:
    """JSON file {key: vector}; vectors are stored as exact float32 values, so reloading is bit-identical."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.data: Dict[str, List[float]] = (json.loads(self.path.read_text(encoding="utf-8"))
                                             if self.path.exists() else {})

    @staticmethod
    def key(encoder: Encoder, kind: str, text: str) -> str:
        prompt = encoder.query_prompt if kind == "query" else ""
        raw = json.dumps([encoder.backend, encoder.model, encoder.revision, kind, prompt, text], ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, separators=(",", ":")), encoding="utf-8")


class CachedEncoder:
    """Wraps an Encoder; only texts missing from the cache reach the model (or the paid API)."""

    def __init__(self, inner: Encoder, cache: EmbeddingCache):
        self.inner, self.cache = inner, cache

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def encode(self, texts: Sequence[str], kind: str) -> np.ndarray:
        keys = [EmbeddingCache.key(self.inner, kind, t) for t in texts]
        missing = list(dict.fromkeys(t for t, k in zip(texts, keys) if k not in self.cache.data))
        if missing:
            for text, vector in zip(missing, self.inner.encode(missing, kind)):
                self.cache.data[EmbeddingCache.key(self.inner, kind, text)] = vector.astype(np.float32).tolist()
            self.cache.save()
        return np.asarray([self.cache.data[k] for k in keys], dtype=np.float32)
