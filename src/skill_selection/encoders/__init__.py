"""Encoder specs: `st:<hf model>[@<revision>]` (sentence-transformers), `hf:<hf model>[@<revision>]` (plain
transformers, last-token pooling) or `openai:<model>` (paid API). Local models must be pinned to a revision.

Backends are imported lazily, so the retrieval core and the explorer UI never load torch or the OpenAI client.
MODEL_PROFILES holds what each published model needs to be used as its authors intended (revision, query instruction).
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple

from .base import CachedEncoder, EmbeddingCache, Encoder

DEFAULT_ENCODER = "st:Qwen/Qwen3-Embedding-0.6B"
MODEL_PROFILES = {
    # Off-the-shelf baseline of the SkillRet paper; prompts come from the model's own sentence-transformers config
    "Qwen/Qwen3-Embedding-0.6B": {"revision": "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3"},
    # SkillRet fine-tuned retriever; shipped config: last-token pooling + normalisation, "query" prompt
    "ThakiCloud/SkillRet-Embedding-0.6B": {"revision": "67f1594c46c40e13a5eb2f4092cc85c98c9ed32d", "max_seq_length": 4096},
    # SkillRouter retriever; no sentence-transformers config, usage copied from the model card
    "pipizhao/SkillRouter-Embedding-0.6B": {
        "revision": "c03c9bcee9fce92ab0262bb6dcf54d174a8ba558",
        "query_instruction": ("Instruct: Given a task description, retrieve the most relevant "
                              "skill document that would help an agent complete the task\nQuery:")},
}
PINNED_REVISIONS = {model: p["revision"] for model, p in MODEL_PROFILES.items()}


def parse_encoder_spec(spec: str) -> Tuple[str, str, str]:
    backend, sep, rest = spec.partition(":")
    if not sep or backend not in ("st", "hf", "openai") or not rest:
        raise ValueError(f"encoder must look like 'st:<model>[@rev]', 'hf:<model>[@rev]' or 'openai:<model>', got {spec!r}")
    model, _, revision = rest.partition("@")
    if backend in ("st", "hf"):
        revision = revision or PINNED_REVISIONS.get(model, "")
        if not revision:
            raise ValueError(f"pin a revision for local model {model!r}: '{backend}:{model}@<commit hash>'")
    return backend, model, revision or "api"


def canonical_spec(spec: str) -> str:
    """The key an index stores an encoder under: `backend:model@revision` (revision filled in when pinned)."""
    backend, model, revision = parse_encoder_spec(spec)
    return f"{backend}:{model}@{revision}"


def build_encoder(spec: str, cache_dir: Optional[Path] = None, dtype: Optional[str] = None,
                  batch_size: Optional[int] = None):
    """batch_size: texts per forward pass; 1 keeps memory lowest on an 8 GB machine. Padding may move the last bits
    of a vector between batch sizes, so a comparison should keep one batch size (compare.py uses 1)."""
    backend, model, revision = parse_encoder_spec(spec)
    profile = MODEL_PROFILES.get(model, {})
    if backend == "st":
        from .st_encoder import SentenceTransformerEncoder
        encoder = SentenceTransformerEncoder(model, revision, max_seq_length=profile.get("max_seq_length"), dtype=dtype,
                                             **({"batch_size": batch_size} if batch_size else {}))
    elif backend == "hf":
        from .hf_encoder import LastTokenEncoder
        if "query_instruction" not in profile:
            raise ValueError(f"no query instruction known for {model!r}; add it to MODEL_PROFILES")
        encoder = LastTokenEncoder(model, revision, profile["query_instruction"], dtype=dtype,
                                   **({"batch_size": batch_size} if batch_size else {}))
    else:
        from .openai_encoder import OpenAIEncoder
        encoder = OpenAIEncoder(model)
    if cache_dir is None:
        return encoder
    slug = encoder.spec.replace("/", "--").replace(":", "_").replace("@", "_") + (f"_{dtype}" if dtype else "")
    return CachedEncoder(encoder, EmbeddingCache(Path(cache_dir) / f"{slug}.json"))
