"""Text-pair scorers r(a, b) for the graph selectors (core.Scorer protocol: `kind` + `score(a, b) -> |a| x |b|`).

TfidfScorer   verbatim from GR1 experiments/skill_graph/scorers.py (lexical; used for the parity check with GR1).
EncoderScorer cosine of a text encoder from skill_selection.encoders (e.g. multilingual Qwen3-Embedding):
              `a` texts (task, sub-tasks, states) are encoded as queries, `b` texts (skill documents, preconditions,
              completions) as documents. Vectors go through the encoder's cache, so re-runs are offline.
"""
from __future__ import annotations

from typing import Dict, Sequence

import numpy as np


class TfidfScorer:
    """TF-IDF cosine fitted on a fixed corpus (all task and skill texts of the run), so scores are comparable.
    Rows are L2-normalised by the vectoriser and cached per text, so repeated texts are transformed once."""
    kind = "similarity"

    def __init__(self, corpus: Sequence[str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.vec = TfidfVectorizer(token_pattern=r"[A-Za-zÀ-ỹ]{2,}", sublinear_tf=True).fit(list(corpus))
        self._rows: Dict[str, object] = {}

    def rows(self, texts: Sequence[str]):
        from scipy.sparse import vstack
        todo = [t for t in dict.fromkeys(texts) if t not in self._rows]
        if todo:
            for t, row in zip(todo, self.vec.transform(todo)):
                self._rows[t] = row
        return vstack([self._rows[t] for t in texts])

    def score(self, a: Sequence[str], b: Sequence[str]) -> np.ndarray:
        if not len(a) or not len(b):
            return np.zeros((len(a), len(b)))
        return (self.rows(a) @ self.rows(b).T).toarray()


class EncoderScorer:
    kind = "similarity"

    def __init__(self, encoder):
        self.encoder = encoder

    def score(self, a: Sequence[str], b: Sequence[str]) -> np.ndarray:
        if not len(a) or not len(b):
            return np.zeros((len(a), len(b)))
        return self.encoder.encode(list(a), "query") @ self.encoder.encode(list(b), "document").T
