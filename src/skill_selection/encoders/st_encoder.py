"""Encode text into vectors using Sentence Transformers locally.

Uses Qwen/Qwen3-Embedding-0.6B by default with a pinned revision.
Queries use the model's query prompt; documents use no prompt.
Outputs are normalized float32 vectors.

The model loads lazily when uncached text needs encoding. The query
prompt is read from config_sentence_transformers.json without loading
the model. Optional bfloat16 reduces memory usage but may slightly
change vectors; the prompt and dtype are included in the cache key.

Runs on CPU without API costs.
"""
from __future__ import annotations
import json
from typing import List, Optional
import numpy as np
from .base import Encoder


def _shipped_prompts(model: str, revision: str) -> dict:
    from huggingface_hub import hf_hub_download
    try:
        path = hf_hub_download(model, "config_sentence_transformers.json", revision=revision)
    except Exception:
        return {}
    return json.loads(open(path, encoding="utf-8").read()).get("prompts") or {}


class SentenceTransformerEncoder(Encoder):
    backend = "st"
    def __init__(self, model: str, revision: str, model_obj=None, device: str = "cpu", batch_size: int = 8,
                max_seq_length: Optional[int] = None, dtype: Optional[str] = None):
        self.model, self.revision, self.batch_size, self.device = model, revision, batch_size, device
        self.max_seq_length = max_seq_length                 # None = the model's own default (not part of cache key)
        self.dtype = dtype                                   # None = float32 (not part of cache key)
        self._st = model_obj
        prompts = (getattr(model_obj, "prompts", None) if model_obj is not None else _shipped_prompts(model, revision)) or {}
        self._query_prompt_name = "query" if "query" in prompts else None
        self.query_prompt = prompts.get("query", "")

    def _load(self):
        if self._st is None:
            from sentence_transformers import SentenceTransformer
            kwargs = {}
            if self.dtype:
                import torch
                kwargs["model_kwargs"] = {"torch_dtype": getattr(torch, self.dtype)}
            self._st = SentenceTransformer(self.model, revision=self.revision, device=self.device, **kwargs)
        if self.max_seq_length:                              # cap long skill bodies (CPU time / RAM)
            self._st.max_seq_length = self.max_seq_length

    def _encode(self, texts: List[str], kind: str) -> np.ndarray:
        self._load()
        assert self._st is not None
        prompt_name = self._query_prompt_name if kind == "query" else None
        return self._st.encode(texts, prompt_name=prompt_name, batch_size=self.batch_size,
                            normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
