"""Local multilingual encoder through sentence-transformers (default: Qwen/Qwen3-Embedding-0.6B, pinned revision).

Input: texts and kind. Queries use the model's own "query" prompt (an instruction prefix); documents use none, as the
model card prescribes. Output: normalised float32 vectors. Runs on CPU, no API cost; the first load downloads the
model into the Hugging Face cache, later loads work offline.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .base import Encoder


class SentenceTransformerEncoder(Encoder):
    backend = "st"

    def __init__(self, model: str, revision: str, model_obj=None, device: str = "cpu", batch_size: int = 8):
        self.model, self.revision, self.batch_size = model, revision, batch_size
        if model_obj is None:
            from sentence_transformers import SentenceTransformer
            model_obj = SentenceTransformer(model, revision=revision, device=device)
        self._st = model_obj
        prompts = getattr(model_obj, "prompts", None) or {}
        self._query_prompt_name = "query" if "query" in prompts else None
        self.query_prompt = prompts.get("query", "")

    def _encode(self, texts: List[str], kind: str) -> np.ndarray:
        prompt_name = self._query_prompt_name if kind == "query" else None
        return self._st.encode(texts, prompt_name=prompt_name, batch_size=self.batch_size,
                               normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False)
