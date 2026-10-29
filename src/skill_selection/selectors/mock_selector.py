"""Configured decisions for integration tests; no retrieval or relevance claims."""
from ..schemas import QueryRecord, SelectionResult
from .base import Selector


class MockSelector(Selector):
    name = "mock"

    def __init__(self, skill_ids=()):
        self.skill_ids = list(skill_ids)

    def select(self, query: QueryRecord, k: int) -> SelectionResult:
        if len(set(self.skill_ids)) != len(self.skill_ids):
            raise ValueError("duplicate mock skill IDs")
        if k < len(self.skill_ids):
            raise ValueError("k cannot truncate a configured integration decision")
        return SelectionResult(query.id, self.name, self.skill_ids.copy(), [1.0] * len(self.skill_ids))
