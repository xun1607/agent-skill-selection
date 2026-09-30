from __future__ import annotations

import random

from ..schemas import QueryRecord, SelectionResult
from .base import Selector


class RandomSelector(Selector):
    """Uniform random k skills. The RNG is seeded per (seed, query id), so results do not depend on query order."""

    name = "random"

    def __init__(self, seed: int = 0):
        self.seed = seed

    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        rng = random.Random(f"{self.seed}:{query.id}")
        picked = rng.sample(self.catalog, min(k, len(self.catalog)))
        return SelectionResult(query_id=query.id, selector=self.name, skill_ids=[s.id for s in picked],
                               scores=[float(len(picked) - i) for i in range(len(picked))])

    def config(self):
        return {"name": self.name, "seed": self.seed}
