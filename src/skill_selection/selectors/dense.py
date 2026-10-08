"""Dense retrieval on precomputed, L2-normalised vectors (numpy only: no model is loaded at selection time).

Input: one query vector and a skill matrix in catalog order. Output: skill positions sorted by cosine similarity,
best first, plus the scores. Ties keep catalog order (stable sort), as in GR1's SemanticFilterStrategy.
"""
from __future__ import annotations

from typing import Tuple

import numpy as np


def rank_by_cosine(query: np.ndarray, skills: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    scores = skills.astype(np.float32) @ query.astype(np.float32)
    return np.argsort(-scores, kind="stable"), scores
