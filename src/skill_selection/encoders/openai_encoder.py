"""OpenAI embeddings (text-embedding-3-small), used only to reproduce GR1's selection for comparison.

Input: texts; needs OPENAI_API_KEY (paid API, so always wrap it in CachedEncoder). Texts are cut at 16,000 characters
like GR1's OpenAIEmbedder. Query and document are encoded the same way (the model has no prompts).
Output: normalised float32 vectors. API models cannot be pinned, so the revision is recorded as "api".
"""
from __future__ import annotations

from typing import List

import numpy as np

from .base import Encoder

MAX_CHARS = 16000


class OpenAIEncoder(Encoder):
    backend = "openai"
    revision = "api"

    def __init__(self, model: str = "text-embedding-3-small", client=None):
        self.model = model
        self._client = client

    def _encode(self, texts: List[str], kind: str) -> np.ndarray:
        if self._client is None:
            from openai import OpenAI
            self._client = OpenAI()
        response = self._client.embeddings.create(model=self.model, input=[t[:MAX_CHARS] for t in texts])
        return np.asarray([item.embedding for item in sorted(response.data, key=lambda d: d.index)], dtype=np.float32)
