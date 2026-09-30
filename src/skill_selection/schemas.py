"""Plain data records shared by loaders, selectors and the evaluator.

Selectors receive only SkillRecord and QueryRecord. Relevance labels (Qrels) are read by the evaluator alone, so a
QueryRecord must never carry gold information: no gold skill ids, and no number of gold skills.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict

# query id -> {skill id: relevance}; relevance <= 0 means non-relevant
Qrels = Dict[str, Dict[str, int]]


@dataclass(frozen=True)
class SkillRecord:
    id: str
    name: str
    description: str
    body: str                                   # full skill document (SKILL.md without front matter)
    source: str                                 # e.g. "skillret:test", "gr1"
    category: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def text(self) -> str:
        """Retrieval document, composed as in the SkillRet reference evaluation: name | description | body."""
        return f"{self.name.strip()} | {self.description.strip()} | {self.body.strip()}"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SkillRecord":
        return cls(**d)


@dataclass(frozen=True)
class QueryRecord:
    id: str
    text: str
    source: str
    group_id: str = ""                          # queries sharing a group must stay in the same split
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QueryRecord":
        return cls(**d)


@dataclass
class SelectionResult:
    query_id: str
    selector: str
    skill_ids: list                             # ranked, best first, no duplicates
    scores: list
    latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
