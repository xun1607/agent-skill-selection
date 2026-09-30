"""Okapi BM25 with Lucene's idf and tf normalisation (the default method of bm25s, used by the SkillRet reference).

Tokens: lower-cased runs of 2+ word characters, Lucene's default English stop set removed, no stemming.
idf(t) = ln(1 + (N - df + 0.5) / (df + 0.5));  w(t, d) = idf(t) * tf / (tf + k1 * (1 - b + b * |d| / avgdl)).
A query term that occurs twice contributes twice. Skills with score 0 are not returned, as in the reference.
"""
from __future__ import annotations

import re
import time
from collections import Counter
from typing import Dict, List, Sequence

import numpy as np
from scipy.sparse import csc_matrix

from ..schemas import QueryRecord, SelectionResult, SkillRecord
from .base import Selector

TOKEN_RE = re.compile(r"(?u)\b\w\w+\b")
LUCENE_EN_STOPWORDS = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that the their then there these they "
    "this to was will with".split()
)


def tokenize(text: str, stopwords: frozenset = LUCENE_EN_STOPWORDS) -> List[str]:
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in stopwords]


class BM25Selector(Selector):
    name = "bm25"

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b

    def fit(self, catalog: Sequence[SkillRecord]) -> None:
        super().fit(catalog)
        self._ids = [s.id for s in self.catalog]
        self._vocab: Dict[str, int] = {}
        rows, cols, tfs = [], [], []
        doc_len = np.zeros(len(self.catalog))
        for d, skill in enumerate(self.catalog):
            counts = Counter(tokenize(skill.text()))
            doc_len[d] = sum(counts.values())
            for term, tf in counts.items():
                rows.append(d)
                cols.append(self._vocab.setdefault(term, len(self._vocab)))
                tfs.append(tf)
        n_docs, n_terms = len(self.catalog), len(self._vocab)
        rows_a, cols_a, tf_a = np.array(rows), np.array(cols), np.array(tfs, dtype=float)
        df = np.bincount(cols_a, minlength=n_terms)
        idf = np.log(1.0 + (n_docs - df + 0.5) / (df + 0.5))
        avgdl = doc_len.mean() if n_docs and doc_len.mean() > 0 else 1.0
        norm = self.k1 * (1.0 - self.b + self.b * doc_len / avgdl)
        weights = idf[cols_a] * tf_a / (tf_a + norm[rows_a])
        self._weights = csc_matrix((weights, (rows_a, cols_a)), shape=(n_docs, n_terms))

    def scores(self, text: str) -> np.ndarray:
        """BM25 score of every catalog skill for a query text (catalog order)."""
        qtf = Counter(self._vocab[t] for t in tokenize(text) if t in self._vocab)
        if not qtf:
            return np.zeros(len(self._ids))
        cols = list(qtf)
        sub = self._weights[:, cols]
        return np.asarray(sub @ np.array([qtf[c] for c in cols], dtype=float)).ravel()

    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        t0 = time.perf_counter()
        s = self.scores(query.text)
        positive = np.flatnonzero(s > 0)
        # highest score first; ties keep catalog order (stable sort on the negated score)
        order = positive[np.argsort(-s[positive], kind="stable")][:k]
        return SelectionResult(query_id=query.id, selector=self.name, skill_ids=[self._ids[i] for i in order],
                               scores=[float(s[i]) for i in order],
                               latency_ms=(time.perf_counter() - t0) * 1000)

    def config(self):
        return {"name": self.name, "k1": self.k1, "b": self.b, "stopwords": "lucene_en", "idf": "lucene"}
