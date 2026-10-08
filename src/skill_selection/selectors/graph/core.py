# Ported verbatim from GR1 experiments/skill_graph/core.py (sha256 51a4581a7d4c9b1ec3a02005f523e45b53e9a3d88625e1ea9f3a2c427c9f18cc, uncommitted in GR1).
# Parity with the original: tests/unit/test_graph_parity.py.
"""
Task-decomposition-guided skill selection (SkillReranker; Chen et al. 2026, arXiv:2607.06283, Sec. 4), domain-free.

Per task: the task text q, its plan (m sub-tasks t_0..t_{m-1} and n = m+1 states s_0..s_m, where s_{i+1} is the
progress after t_i), and candidate skills with a precondition state p_k (None = no prerequisite), a completion state
e_k and the full document c_k. A Scorer r(a, b) scores text pairs (a cross-encoder in the paper, embeddings here).

  src_k = 0 if p_k is None else argmax_{0<=i<=n-2} r(s_i, p_k)                              (3)
  tgt_k = src_k + 1 + argmax_{0<=j<=n-src_k-2} r(s_{src_k+1+j}, e_k)                        (4)
  rho_k = r(q, c_k),  w_k = sigmoid(rho_k)
  In(i)    = sum_{k: tgt_k <= i} w_k / (1 + (i - tgt_k) / (n-1))                              (5)
  Out(i)   = sum_{k: src_k >= i} w_k / (1 + (src_k - i) / (n-1))
  Cross(i) = sum_{k: src_k < i < tgt_k} w_k
  node i in [1, n-2] is a split point iff In(i) > Cross(i) and Out(i) > Cross(i)             (6)
  per stage, tau = its sub-tasks joined:  phi_k = log sigmoid(rho_k) + log sigmoid(r(tau, c_k))  (7)
The best skill of every stage, deduplicated in stage order, is the selected set: its size follows the task.

Two further modes of this thesis (GR2 slide 4) treat each skill as a state transition s_i -> s_j. With the logits
A_k(i) = logit r(s_i, p_k) (0 when p_k is None), B_k(j) = logit r(s_j, e_k) and F_k(t) = logit r(t_t, c_k):
  state_rank  (M4) node score v_k = log sigmoid(rho_k) + log sigmoid(A_k(src_k)) + log sigmoid(B_k(tgt_k)), with the
              edge of (3)-(4); rank by v_k and select the top k (no graph)
  path        (M5) best path s_0 -> s_{n-1} on the state DAG, by dynamic programming over every segment i < j:
                 W_k(i, j) = log sigmoid(rho_k) + log sigmoid(A_k(i)) + log sigmoid(B_k(j))
                             + sum_{t=i}^{j-1} log sigmoid(F_k(t)) - lambda        # must fit every step it covers
                 best[0] = 0,  best[j] = max( best[j-1] - mu,                      # the agent does step j itself
                                              max_{i<j, k} best[i] + W_k(i, j) )
              the skills on the path are the selected set, so its size is the number of steps that need a skill;
              lambda is the price of one more skill, mu the price of a step left without one. Without the
              per-step fit term one skill spanning s_0 -> s_{n-1} always beats two shorter ones.

Scores of a "similarity" scorer (cosine) are standardised over the candidates before the sigmoid, so that
w_k and phi_k do not depend on the scale of the similarity; argmax steps (3)-(4) use the raw scores.
Nothing here reads labels, gold files or the number of gold skills.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol, Sequence, Tuple

import numpy as np

MODES = ("full", "no_split", "no_edges", "state_rank", "path")
#  full      the method of the paper
#  no_split  "w/o Split": every sub-task is its own stage (one skill per sub-task)
#  no_edges  "w/o Graph Edge": no execution graph; one joint stage over all sub-tasks
#  state_rank  M4: rank by relevance + state match of precondition/completion, fixed top k
#  path        M5: best path from the initial state to the goal (adaptive number of skills)


@dataclass(frozen=True)
class SelectParams:
    lam: float = 0.0                                     # path: cost of each selected skill
    mu: float = 1.0                                      # path: cost of a step covered by no skill
    k: int = 3                                           # state_rank: size of the selected set
    min_select: int = 1                                  # path: fill up from the best node scores below this size


class Scorer(Protocol):
    kind: str                                            # "similarity" (standardised) or "logit" (used as is)

    def score(self, a: Sequence[str], b: Sequence[str]) -> np.ndarray:  # |a| x |b| relevance matrix
        ...


@dataclass(frozen=True)
class TaskPlan:
    subtasks: Tuple[str, ...]
    states: Tuple[str, ...]                              # len(states) == len(subtasks) + 1
    valid: bool = True                                   # False: the parser failed and this is a fallback plan

    @staticmethod
    def fallback(task: str) -> "TaskPlan":
        return TaskPlan(subtasks=(task,), states=("The task has not been started.", "The task is completed."),
                        valid=False)


@dataclass(frozen=True)
class Candidate:
    id: str
    document: str                                        # full skill text c_k
    precondition: Optional[str]                          # p_k, None = no prerequisite
    completion: str                                      # e_k


@dataclass
class Stage:
    start: int                                           # state index where the stage begins
    end: int                                             # state index where it ends
    text: str                                            # tau
    winner: Optional[str]
    phi: Dict[str, float] = field(default_factory=dict)


@dataclass
class GraphSelection:
    selected: List[str]                                  # adaptive-size skill set, stage order
    ranking: List[str]                                   # selected first, then the other candidates by rho
    edges: Dict[str, Tuple[int, int]]                    # skill -> (src, tgt) state indices
    splits: List[int]
    stages: List[Stage]
    rho: Dict[str, float]
    n_states: int
    mode: str
    score: Dict[str, float] = field(default_factory=dict)    # state_rank / path: node score v_k
    path: List[Tuple[Optional[str], int, int]] = field(default_factory=list)  # path: (skill or None, src, tgt)

    @property
    def gaps(self) -> int:
        """path: steps covered by no skill (0 = a valid path made only of skills)."""
        return sum(1 for cid, _, _ in self.path if cid is None)


def sigmoid(x: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-x))


def log_sigmoid(x: np.ndarray) -> np.ndarray:
    return -np.logaddexp(0.0, -x)


def _logits(scores: np.ndarray, kind: str) -> np.ndarray:
    if kind == "logit":
        return scores
    sd = scores.std()
    return (scores - scores.mean()) / sd if sd > 1e-9 else np.zeros_like(scores)


def _match_scores(plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer):
    """Raw and logit matrices (n-1 x |cands|): precondition vs s_0..s_{n-2} (0 for p = None), completion vs
    s_1..s_{n-1}; has_pre marks the candidates with a precondition."""
    n = len(plan.states)
    has_pre = np.array([bool(c.precondition) for c in cands])
    pre_raw = np.zeros((n - 1, len(cands)))
    pre_l = np.zeros((n - 1, len(cands)))
    if has_pre.any():
        cols = np.flatnonzero(has_pre)
        raw = scorer.score(list(plan.states[:n - 1]), [cands[j].precondition for j in cols])
        pre_raw[:, cols] = raw
        pre_l[:, cols] = _logits(raw, scorer.kind)
    post_raw = scorer.score(list(plan.states[1:]), [c.completion for c in cands])
    return has_pre, pre_raw, pre_l, post_raw, _logits(post_raw, scorer.kind)


def edge_scores(plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer
                ) -> Tuple[Dict[str, Tuple[int, int]], np.ndarray, np.ndarray]:
    """Equations (3)-(4), plus the logits a_k, b_k of the precondition and completion match on the chosen edge."""
    n = len(plan.states)
    edges: Dict[str, Tuple[int, int]] = {}
    a = np.zeros(len(cands))
    b = np.zeros(len(cands))
    if n < 2 or not cands:
        return edges, a, b
    has_pre, pre_raw, pre_l, post_raw, post_l = _match_scores(plan, cands, scorer)
    for k, c in enumerate(cands):
        src = int(np.argmax(pre_raw[:, k])) if has_pre[k] else 0
        if src + 1 >= n:
            continue                                     # cannot advance the task (unreachable with (3))
        tgt = src + 1 + int(np.argmax(post_raw[src:, k]))   # row j = state j+1
        edges[c.id] = (src, tgt)
        a[k] = pre_l[src, k]
        b[k] = post_l[tgt - 1, k]
    return edges, a, b


def build_edges(plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer) -> Dict[str, Tuple[int, int]]:
    """Equations (3)-(4): each candidate becomes an edge src -> tgt between task states."""
    return edge_scores(plan, cands, scorer)[0]


def segment_weights(plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer, rho_l: np.ndarray, lam: float
                    ) -> Dict[Tuple[int, int], Tuple[str, float]]:
    """(i, j) -> (best skill, W_k(i, j)) for every segment i < j of the state chain."""
    n = len(plan.states)
    _, _, pre_l, _, post_l = _match_scores(plan, cands, scorer)
    fit = log_sigmoid(_logits(scorer.score(list(plan.subtasks), [c.document for c in cands]), scorer.kind))
    cum = np.vstack([np.zeros(len(cands)), np.cumsum(fit, axis=0)])          # cum[t] = sum of rows < t
    base = log_sigmoid(rho_l) - lam
    seg: Dict[Tuple[int, int], Tuple[str, float]] = {}
    for i in range(n - 1):
        for j in range(i + 1, n):
            w = base + log_sigmoid(pre_l[i]) + log_sigmoid(post_l[j - 1]) + cum[j] - cum[i]
            k = int(np.argmax(w))
            seg[(i, j)] = (cands[k].id, float(w[k]))
    return seg


def best_path(n: int, segments: Dict[Tuple[int, int], Tuple[str, float]], mu: float
              ) -> List[Tuple[Optional[str], int, int]]:
    """Highest-weight path 0 -> n-1 over skill segments and gap steps (j-1 -> j, weight -mu); ties go to the gap."""
    if n < 2:
        return []
    best = [-np.inf] * n
    back: List[Tuple[Optional[str], int]] = [(None, 0)] * n
    best[0] = 0.0
    for j in range(1, n):
        best[j], back[j] = best[j - 1] - mu, (None, j - 1)
        for i in range(j):
            if (i, j) in segments:
                cid, w = segments[(i, j)]
                if best[i] + w > best[j] + 1e-12:
                    best[j], back[j] = best[i] + w, (cid, i)
    path, j = [], n - 1
    while j > 0:
        cid, i = back[j]
        path.append((cid, i, j))
        j = i
    return path[::-1]


def split_points(edges: Dict[str, Tuple[int, int]], weights: Dict[str, float], n: int) -> List[int]:
    """Equations (5)-(6)."""
    splits = []
    for i in range(1, n - 1):
        inc = sum(weights[k] / (1 + (i - t) / (n - 1)) for k, (s, t) in edges.items() if t <= i)
        out = sum(weights[k] / (1 + (s - i) / (n - 1)) for k, (s, t) in edges.items() if s >= i)
        cross = sum(weights[k] for k, (s, t) in edges.items() if s < i < t)
        if inc > cross and out > cross:
            splits.append(i)
    return splits


def select(task: str, plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer, mode: str = "full",
           params: Optional[SelectParams] = None, rho: Optional[Sequence[float]] = None) -> GraphSelection:
    """rho: relevance of the task to each candidate given by the first-stage retriever (e.g. BM25), standardised like
    a similarity; None = r(q, c_k) from the scorer, as in the paper."""
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}; expected one of {MODES}")
    n = len(plan.states)
    if not cands:
        return GraphSelection([], [], {}, [], [], {}, n, mode)
    if rho is None:
        rho_raw = scorer.score([task], [c.document for c in cands])[0]
        rho_l = _logits(rho_raw, scorer.kind)
    else:
        rho_raw = np.asarray(rho, dtype=float)
        rho_l = _logits(rho_raw, "similarity")
    rho_by_id = {c.id: float(r) for c, r in zip(cands, rho_raw)}
    order_by_rho = [cands[i].id for i in np.argsort(-rho_raw, kind="stable")]
    if mode in ("state_rank", "path"):
        return _select_transitions(plan, cands, scorer, mode, params or SelectParams(), rho_by_id, rho_l)

    edges = build_edges(plan, cands, scorer) if mode == "full" else {}
    if mode == "full":
        weights = {c.id: float(w) for c, w in zip(cands, sigmoid(rho_l))}
        splits = split_points(edges, weights, n)
        bounds = [0] + splits + [n - 1]
    elif mode == "no_split":
        splits, bounds = list(range(1, n - 1)), list(range(n))
    else:
        splits, bounds = [], [0, n - 1]

    # stage-wise selection, equation (7); in full mode only skills that form an edge compete
    pool = [c for c in cands if c.id in edges] if mode == "full" else list(cands)
    idx = {c.id: i for i, c in enumerate(cands)}
    stages: List[Stage] = []
    if pool and n >= 2:
        taus = [" ".join(plan.subtasks[a:b]) for a, b in zip(bounds[:-1], bounds[1:])]
        fit_raw = scorer.score(taus, [c.document for c in pool])
        for (a, b), tau, row in zip(zip(bounds[:-1], bounds[1:]), taus, fit_raw):
            phi = log_sigmoid(rho_l[[idx[c.id] for c in pool]]) + log_sigmoid(_logits(row, scorer.kind))
            best = int(np.argmax(phi))
            stages.append(Stage(a, b, tau, pool[best].id, {c.id: float(p) for c, p in zip(pool, phi)}))
    selected = list(dict.fromkeys(s.winner for s in stages if s.winner))
    if not selected:
        selected = order_by_rho[:1]                      # degenerate plan / no edge: best global match
    ranking = selected + [cid for cid in order_by_rho if cid not in selected]
    return GraphSelection(selected, ranking, edges, splits, stages, rho_by_id, n, mode)


def _select_transitions(plan: TaskPlan, cands: Sequence[Candidate], scorer: Scorer, mode: str,
                        params: SelectParams, rho: Dict[str, float], rho_l: np.ndarray) -> GraphSelection:
    """M4 (state_rank) and M5 (path): skills as transitions between task states."""
    n = len(plan.states)
    edges, a, b = edge_scores(plan, cands, scorer)
    v = log_sigmoid(rho_l) + log_sigmoid(a) + log_sigmoid(b)
    v = np.where([c.id in edges for c in cands], v, log_sigmoid(rho_l) - 1e3)   # no edge: last, by relevance
    score = {c.id: float(x) for c, x in zip(cands, v)}
    by_score = [cands[i].id for i in np.argsort(-v, kind="stable")]
    path: List[Tuple[Optional[str], int, int]] = []
    if mode == "state_rank":
        selected = by_score[:max(0, params.k)]
    else:
        path = best_path(n, segment_weights(plan, cands, scorer, rho_l, params.lam), params.mu)
        selected = list(dict.fromkeys(cid for cid, _, _ in path if cid is not None))
        edges.update({cid: (i, j) for cid, i, j in path if cid is not None})     # draw the chosen segments
        selected += [cid for cid in by_score if cid not in selected][:max(0, params.min_select - len(selected))]
    ranking = selected + [cid for cid in by_score if cid not in selected]
    return GraphSelection(selected, ranking, edges, [], [], rho, n, mode, score=score, path=path)


def to_mermaid(plan: TaskPlan, result: GraphSelection, max_label: int = 60) -> str:
    """Execution graph: states as nodes, candidate skills as edges; selected skills drawn thick."""
    def esc(s: str) -> str:
        s = s.replace('"', "'")
        return s if len(s) <= max_label else s[:max_label - 1] + "…"
    lines = ["flowchart LR"]
    for i, s in enumerate(plan.states):
        mark = "*" if i in result.splits else ""
        lines.append(f'    S{i}["S{i}{mark}: {esc(s)}"]')
    grouped: Dict[Tuple[int, int], List[str]] = {}
    for cid, (s, t) in result.edges.items():
        grouped.setdefault((s, t), []).append(cid)
    for (s, t), ids in sorted(grouped.items()):
        ids.sort(key=lambda c: -result.rho.get(c, 0.0))
        label = "<br/>".join(esc(c) for c in ids[:3]) + (f"<br/>+{len(ids) - 3} more" if len(ids) > 3 else "")
        arrow = "==>" if any(c in result.selected for c in ids) else "-->"
        lines.append(f'    S{s} {arrow}|"{label}"| S{t}')
    return "\n".join(lines)
