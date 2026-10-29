"""Last-token-pooling encoder through plain transformers, for models shipped without a sentence-transformers config
(e.g. pipizhao/SkillRouter-Embedding-0.6B). Follows the model card: left padding, last-token pooling, L2 normalisation,
query = instruction + text (no separator), documents as they are, max 4096 tokens.

Input: texts and kind. Output: normalised float32 vectors.
"""
from __future__ import annotations

from typing import List

import numpy as np

from .base import Encoder


class LastTokenEncoder(Encoder):
    backend = "hf"

    def __init__(self, model: str, revision: str, query_instruction: str, max_length: int = 4096,
                 batch_size: int = 2, model_obj=None, tokenizer=None, dtype=None):
        self.model, self.revision, self.max_seq_length, self.batch_size = model, revision, max_length, batch_size
        self.dtype = dtype                                   # None = float32; e.g. "bfloat16" halves memory
        self.query_prompt = query_instruction
        self._model, self._tok = model_obj, tokenizer

    def _load(self):
        if self._model is None:
            from transformers import AutoModel, AutoTokenizer
            self._tok = AutoTokenizer.from_pretrained(self.model, revision=self.revision, padding_side="left")
            import torch
            kwargs = {"torch_dtype": getattr(torch, self.dtype)} if self.dtype else {}
            self._model = AutoModel.from_pretrained(self.model, revision=self.revision, **kwargs).eval()

    def query_text(self, text: str) -> str:
        return self.query_prompt + text

    def _encode(self, texts: List[str], kind: str) -> np.ndarray:
        import torch
        self._load()
        if self._tok is None:
            raise RuntimeError("Tokenizer is not initialized after _load(); provide a tokenizer with model_obj.")
        if self._model is None:
            raise RuntimeError("Model is not initialized after _load().")
        texts = [self.query_text(t) for t in texts] if kind == "query" else list(texts)
        out = []
        for i in range(0, len(texts), self.batch_size):
            enc = self._tok(texts[i:i + self.batch_size], padding=True, truncation=True, max_length=self.max_seq_length,
                            return_tensors="pt")
            with torch.no_grad():
                hidden = self._model(**enc).last_hidden_state
            out.append(hidden[:, -1].float().numpy())        # left padding: the last position is the last token
        return np.concatenate(out)
