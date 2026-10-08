"""GoS-lite: an offline, LLM-free re-implementation of the retrieval step of Graph of Skills (Li et al. 2026,
arXiv:2604.05333). Not the authors' code: their graph is extracted from SKILL.md files by an LLM; here edges come only
from what the files state themselves.

Graph (directed, u -> v means "u needs v"):
  - front-matter `sub_skills` of u lists v                 (declared dependency)
  - the body of u mentions the id of v (word boundary)     (stated reference; ids without - or _ are ignored)
Retrieval, following the paper's four steps:
  1. seed: a lexical ranking (BM25) and a semantic ranking (embedding) are fused by reciprocal rank (k = 60);
     the top `seed_k` skills are the seeds, weighted by their fused score
  2. propagate: personalised PageRank from the seeds (damping 0.85) on the graph where forward edges weigh 1 and
     reverse edges (v -> u, "who needs me") weigh `gamma_r` (reverse-aware propagation)
  3. rank: by PageRank mass, ties by fused seed score, then catalog order
  4. bundle: best skills in rank order until `top_n` skills or `max_chars` of skill text
Defaults are the paper's retrieval defaults (top_n 8, seed_k 5, 12,000 chars); gamma_r = 0.5 is our choice.

Input: skill ids in catalog order, two rankings, the graph, skill text lengths. Output: full ranking + bundle.
"""
from __future__ import annotations

import re
from typing import Dict, List, Mapping, Sequence, Tuple

import numpy as np

from ..datasets.local_skills import split_front_matter


def dependency_graph(skills: Sequence, skill_md: Mapping[str, str]) -> Dict[str, List[str]]:
    """{u: [v, ...]} from declared sub_skills and body mentions; only edges between catalog skills, no self loops."""
    ids = [s.id for s in skills]
    known = set(ids)
    patterns = {v: re.compile(rf"(?<![\w-]){re.escape(v)}(?![\w-])") for v in ids if "-" in v or "_" in v}
    graph: Dict[str, List[str]] = {}
    for s in skills:
        targets = []
        md = skill_md.get(s.id)
        if md:
            meta, _ = split_front_matter(md)
            for item in meta.get("sub_skills") or []:
                name = str(item).split("#")[0].strip()
                if name in known:
                    targets.append(name)
        for v, pat in patterns.items():
            if v != s.id and pat.search(s.body or ""):
                targets.append(v)
        graph[s.id] = sorted(set(t for t in targets if t != s.id))
    return graph


def rrf(rankings: Sequence[Sequence[str]], k: int = 60) -> Dict[str, float]:
    fused: Dict[str, float] = {}
    for ranking in rankings:
        for r, sid in enumerate(ranking, 1):
            fused[sid] = fused.get(sid, 0.0) + 1.0 / (k + r)
    return fused


def personalized_pagerank(ids: Sequence[str], graph: Mapping[str, Sequence[str]], seeds: Mapping[str, float],
                          gamma_r: float = 0.5, damping: float = 0.85, iters: int = 200, tol: float = 1e-12) -> np.ndarray:
    n, pos = len(ids), {sid: i for i, sid in enumerate(ids)}
    w = np.zeros((n, n))
    for u, targets in graph.items():
        for v in targets:
            w[pos[u], pos[v]] += 1.0               # forward: u needs v
            w[pos[v], pos[u]] += gamma_r           # reverse
    p = np.zeros(n)
    for sid, weight in seeds.items():
        p[pos[sid]] = weight
    p /= p.sum()
    out = w.sum(axis=1)
    x = p.copy()
    for _ in range(iters):
        spread = np.zeros(n)
        nz = out > 0
        spread += (x[nz, None] * w[nz] / out[nz, None]).sum(axis=0)
        new = (1 - damping) * p + damping * (spread + x[~nz].sum() * p)   # dangling mass returns to the seeds
        if np.abs(new - x).sum() < tol:
            x = new
            break
        x = new
    return x


def gos_lite(ids: Sequence[str], lexical: Sequence[str], semantic: Sequence[str], graph: Mapping[str, Sequence[str]],
             lengths: Mapping[str, int], seed_k: int = 5, top_n: int = 8, max_chars: int = 12000,
             gamma_r: float = 0.5) -> Tuple[List[str], List[str], Dict[str, float]]:
    fused = rrf([lexical, semantic])
    seed_order = sorted(ids, key=lambda s: (-fused.get(s, 0.0), ids.index(s)))[:seed_k]
    mass = personalized_pagerank(ids, graph, {s: fused[s] for s in seed_order}, gamma_r=gamma_r)
    score = {sid: float(m) for sid, m in zip(ids, mass)}
    ranking = sorted(ids, key=lambda s: (-round(score[s], 12), -fused.get(s, 0.0), ids.index(s)))
    bundle, used = [], 0
    for sid in ranking:
        if len(bundle) >= top_n or (bundle and used + lengths.get(sid, 0) > max_chars):
            break
        bundle.append(sid)
        used += lengths.get(sid, 0)
    return ranking, bundle, score
