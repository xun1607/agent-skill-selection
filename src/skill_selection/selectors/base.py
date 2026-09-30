from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Mapping, Sequence

from ..schemas import QueryRecord, SelectionResult, SkillRecord


class Selector(ABC):
    """Chooses skills for a query from a fixed catalog.

    Lifecycle: fit(catalog) once, then select(query, k) per query. Online learners (Thompson Sampling, ...) also
    override update(), which a streaming runner calls with feedback after each select(); offline selectors ignore it.
    A selector never sees relevance labels except through update().
    """

    name = "base"

    def fit(self, catalog: Sequence[SkillRecord]) -> None:
        self.catalog = list(catalog)

    @abstractmethod
    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        ...

    def update(self, query: QueryRecord, result: SelectionResult, feedback: Mapping[str, float]) -> None:
        return None

    def config(self) -> Dict[str, Any]:
        return {"name": self.name}
