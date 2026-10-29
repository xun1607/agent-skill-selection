"""Pinned, CPU MiniLM baseline reusing the local encoder and cosine ranker."""
import time

from ..schemas import QueryRecord, SelectionResult
from .base import Selector
from .dense import rank_by_cosine


class MiniLMSelector(Selector):
    name = "minilm"
    model = "sentence-transformers/all-MiniLM-L6-v2"
    revision = "c9745ed1d9f207416be6d2e6f8de32d1f16199bf"

    def __init__(self, encoder=None):
        self.encoder = encoder

    def fit(self, catalog):
        super().fit(catalog)
        if self.encoder is None:
            from ..encoders.st_encoder import SentenceTransformerEncoder
            self.encoder = SentenceTransformerEncoder(self.model, self.revision, device="cpu",
                                                       batch_size=32, max_seq_length=256)
        self._vectors = self.encoder.encode([skill.text() for skill in self.catalog], kind="document")

    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        start = time.perf_counter()
        if k < 0:
            raise ValueError("k must be non-negative")
        if not self.catalog or k == 0:
            return SelectionResult(query.id, self.name, [], [], (time.perf_counter() - start) * 1000)
        vector = self.encoder.encode([query.text], kind="query")[0]
        order, scores = rank_by_cosine(vector, self._vectors)
        selected = order[:k]
        return SelectionResult(query.id, self.name, [self.catalog[i].id for i in selected],
                               [float(scores[i]) for i in selected], (time.perf_counter() - start) * 1000)

    def config(self):
        return {"name": self.name, "encoder": "st", "model": self.model, "revision": self.revision,
                "max_seq_length": 256, "document_batch_size": 32, "query_batch_size": 1,
                "device": "cpu", "dtype": "float32", "normalization": "l2",
                "similarity": "cosine", "query_prompt": "", "ties": "catalog_order"}
