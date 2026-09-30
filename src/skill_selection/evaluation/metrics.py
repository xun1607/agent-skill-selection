"""Ranking metrics with trec_eval semantics (the SkillRet reference evaluation uses pytrec_eval).

A run maps query id -> ranked skill ids, best first. Qrels map query id -> {skill id: relevance}; relevance <= 0 is
non-relevant and graded relevance is used as the nDCG gain.
- Queries without any relevant skill are skipped and counted, never scored.
- Queries in the qrels but missing from the run score 0 (trec_eval -c).
- Completeness@k = 1 iff every relevant skill is in the top k (Recall@k == 1), as defined by SkillRet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Mapping, Sequence

from ..schemas import Qrels

DEFAULT_KS = (5, 10, 15)
METRICS = ("NDCG", "Recall", "Precision", "MAP", "Completeness")


def _dcg(gains: Sequence[float]) -> float:
    return sum(g / math.log2(i + 2) for i, g in enumerate(gains))


def ndcg_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> float:
    ideal = sorted((r for r in rels.values() if r > 0), reverse=True)[:k]
    if not ideal:
        return 0.0
    return _dcg([max(rels.get(s, 0), 0) for s in ranked[:k]]) / _dcg(ideal)


def _hits(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> int:
    return sum(1 for s in ranked[:k] if rels.get(s, 0) > 0)


def _n_relevant(rels: Mapping[str, int]) -> int:
    return sum(1 for r in rels.values() if r > 0)


def recall_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> float:
    n = _n_relevant(rels)
    return _hits(ranked, rels, k) / n if n else 0.0


def precision_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> float:
    return _hits(ranked, rels, k) / k          # trec_eval P_k divides by k even when fewer skills are returned


def map_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> float:
    n = _n_relevant(rels)
    if not n:
        return 0.0
    hits, total = 0, 0.0
    for i, s in enumerate(ranked[:k]):
        if rels.get(s, 0) > 0:
            hits += 1
            total += hits / (i + 1)
    return total / n                           # trec_eval map_cut divides by all relevant, not min(k, R)


def completeness_at_k(ranked: Sequence[str], rels: Mapping[str, int], k: int) -> float:
    n = _n_relevant(rels)
    return float(n > 0 and _hits(ranked, rels, k) == n)


_FUNCS = {"NDCG": ndcg_at_k, "Recall": recall_at_k, "Precision": precision_at_k, "MAP": map_at_k,
          "Completeness": completeness_at_k}


@dataclass
class EvalReport:
    mean: Dict[str, float]
    per_query: Dict[str, Dict[str, float]]
    n_evaluated: int
    n_skipped_no_relevant: int
    n_missing_from_run: int
    ks: Sequence[int] = field(default_factory=lambda: DEFAULT_KS)


def evaluate(run: Mapping[str, Sequence[str]], qrels: Qrels, ks: Sequence[int] = DEFAULT_KS) -> EvalReport:
    per_query: Dict[str, Dict[str, float]] = {}
    skipped = missing = 0
    for qid, rels in qrels.items():
        if not _n_relevant(rels):
            skipped += 1
            continue
        ranked: List[str] = list(run.get(qid, []))
        if qid not in run:
            missing += 1
        if len(set(ranked)) != len(ranked):
            raise ValueError(f"duplicate skill ids in the ranking of query {qid}")
        scores = {f"{m}@{k}": _FUNCS[m](ranked, rels, k) for m in METRICS for k in ks}
        scores["n_selected"] = float(len(ranked))
        per_query[qid] = scores
    names = [f"{m}@{k}" for m in METRICS for k in ks] + ["n_selected"]
    n = len(per_query)
    mean = {name: (sum(q[name] for q in per_query.values()) / n if n else 0.0) for name in names}
    return EvalReport(mean=mean, per_query=per_query, n_evaluated=n, n_skipped_no_relevant=skipped,
                      n_missing_from_run=missing, ks=tuple(ks))
