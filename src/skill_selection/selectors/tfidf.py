"""Sublinear TF-IDF cosine baseline; fit IDF on the skill catalog only."""
from collections import Counter
import time

import numpy as np
from scipy.sparse import csr_matrix

from ..schemas import QueryRecord, SelectionResult
from .base import Selector
from .bm25 import tokenize


class TFIDFSelector(Selector):
    name = "tfidf"

    def fit(self, catalog):
        super().fit(catalog)
        self._vocab = {}
        rows, cols, counts = [], [], []
        for index, skill in enumerate(self.catalog):
            for token, count in Counter(tokenize(skill.text())).items():
                rows.append(index)
                cols.append(self._vocab.setdefault(token, len(self._vocab)))
                counts.append(count)
        col_array = np.asarray(cols, dtype=np.int64)
        df = np.bincount(col_array, minlength=len(self._vocab))
        self._idf = np.log((1 + len(self.catalog)) / (1 + df)) + 1
        weights = (1 + np.log(np.asarray(counts, dtype=float))) * self._idf[col_array]
        self._documents = csr_matrix((weights, (rows, cols)), shape=(len(self.catalog), len(self._vocab)))
        norms = np.sqrt(self._documents.multiply(self._documents).sum(axis=1)).A1
        self._documents = self._documents.multiply((1 / np.clip(norms, 1e-12, None))[:, None]).tocsr()

    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        start = time.perf_counter()
        if k < 0:
            raise ValueError("k must be non-negative")
        counts = Counter(self._vocab[t] for t in tokenize(query.text) if t in self._vocab)
        if not counts or k == 0:
            return SelectionResult(query.id, self.name, [], [], (time.perf_counter() - start) * 1000)
        columns = list(counts)
        weights = (1 + np.log([counts[c] for c in columns])) * self._idf[columns]
        weights /= np.linalg.norm(weights)
        scores = np.asarray(self._documents[:, columns] @ weights).ravel()
        positive = np.flatnonzero(scores > 0)
        ranked = positive[np.argsort(-scores[positive], kind="stable")][:k]
        return SelectionResult(query.id, self.name, [self.catalog[i].id for i in ranked],
                               [float(scores[i]) for i in ranked], (time.perf_counter() - start) * 1000)

    def config(self):
        return {"name": self.name, "tf": "1+ln(tf)", "idf": "ln((1+N)/(1+df))+1",
                "normalization": "l2", "similarity": "cosine", "stopwords": "lucene_en",
                "fit_scope": "catalog_only", "zero_scores": "excluded", "ties": "catalog_order"}
