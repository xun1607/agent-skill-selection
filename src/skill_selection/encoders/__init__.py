"""Encoder specs: `st:<hf model>[@<revision>]` (local, must be pinned) or `openai:<model>` (paid API).

Backends are imported lazily, so the retrieval core and the explorer UI never load torch or the OpenAI client.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .base import CachedEncoder, EmbeddingCache, Encoder

DEFAULT_ENCODER = "st:Qwen/Qwen3-Embedding-0.6B"
PINNED_REVISIONS = {"Qwen/Qwen3-Embedding-0.6B": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"}


def parse_encoder_spec(spec: str) -> Tuple[str, str, str]:
    backend, sep, rest = spec.partition(":")
    if not sep or backend not in ("st", "openai") or not rest:
        raise ValueError(f"encoder must look like 'st:<model>[@rev]' or 'openai:<model>', got {spec!r}")
    model, _, revision = rest.partition("@")
    if backend == "st":
        revision = revision or PINNED_REVISIONS.get(model, "")
        if not revision:
            raise ValueError(f"pin a revision for local model {model!r}: 'st:{model}@<commit hash>'")
    return backend, model, revision or "api"


def build_encoder(spec: str, cache_dir: Optional[Path] = None):
    backend, model, revision = parse_encoder_spec(spec)
    if backend == "st":
        from .st_encoder import SentenceTransformerEncoder
        encoder = SentenceTransformerEncoder(model, revision)
    else:
        from .openai_encoder import OpenAIEncoder
        encoder = OpenAIEncoder(model)
    if cache_dir is None:
        return encoder
    slug = encoder.spec.replace("/", "--").replace(":", "_").replace("@", "_")
    return CachedEncoder(encoder, EmbeddingCache(Path(cache_dir) / f"{slug}.json"))
