"""Backend of the explorer UI: precompute everything heavy, so the UI only reads two JSON files.

build_index   GR1 snapshot + encoders -> skill_index.json: skills (with SKILL.md text), tasks (with gate verdict) and,
              per encoder, one vector per skill ("name: description", as GR1) and per task (task description).
select_all    skill_index.json + environment -> selection_cache.json: per encoder and task, the full ranking.
              Tier 1 (OS / RAM) excludes skills with a reason; the remaining ones are ranked by cosine similarity and
              the top k are selected (GR1's method). Excluded skills are listed too, unranked, with their score.

select_all is deterministic and offline (numpy only), so the same index and parameters give a byte-identical file.
The seed is recorded for reproducibility but does not affect the cosine ranking.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Sequence

import numpy as np

from .datasets.gr1 import GR1Benchmark
from .filters.constraint import Environment, exclusion_reason
from .selectors.dense import rank_by_cosine

SCHEMA = 1
REPRESENTATION = "name: description"
SKILL_FIELDS = ("quality_flags", "skill_md_omitted", "python_class", "version", "level", "tags")


def skill_text(skill) -> str:
    """Same text GR1's SemanticFilterStrategy embeds for a skill."""
    return f"{skill.name}: {skill.description}"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json_stable(obj: Any, path: Path, pretty: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(obj, ensure_ascii=False, indent=2) if pretty else json.dumps(obj, ensure_ascii=False,
                                                                                   separators=(",", ":"))
    path.write_text(text + "\n", encoding="utf-8", newline="\n")


def build_index(bench: GR1Benchmark, encoders: Iterable) -> Dict[str, Any]:
    skills = [{"id": s.id, "name": s.name, "description": s.description, "category": s.category,
               "kind": s.metadata["kind"], "constraints": s.metadata.get("constraints") or {},
               "skill_md": bench.skill_md(s), **{k: s.metadata[k] for k in SKILL_FIELDS if k in s.metadata}}
              for s in bench.skills]
    tasks = [{"id": t.id, "text": t.text, **t.metadata, "gate": bench.gate.get(t.id, {"status": "not_run"})}
             for t in bench.tasks]
    vectors = {}
    for encoder in encoders:
        skill_vecs = encoder.encode([skill_text(s) for s in bench.skills], "document")
        task_vecs = encoder.encode([t.text for t in bench.tasks], "query")
        vectors[encoder.spec] = {
            "info": encoder.info(), "dim": int(skill_vecs.shape[1]),
            "skill_vectors": {s.id: v.tolist() for s, v in zip(bench.skills, skill_vecs)},
            "task_vectors": {t.id: v.tolist() for t, v in zip(bench.tasks, task_vecs)},
        }
    return {"schema": SCHEMA, "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "snapshot": {"gr1_commit": bench.manifest.get("gr1_commit"),
                         "manifest_sha256": sha256_file(bench.root / "MANIFEST.json")},
            "representation": REPRESENTATION, "skills": skills, "tasks": tasks, "encoders": vectors}


def _ranking(query: np.ndarray, matrix: np.ndarray, ids: Sequence[str], reasons: Dict[str, str], k: int) -> list:
    kept = [i for i, sid in enumerate(ids) if sid not in reasons]
    dropped = [i for i, sid in enumerate(ids) if sid in reasons]
    rows = []
    for group in (kept, dropped):
        if not group:
            continue
        order, scores = rank_by_cosine(query, matrix[group])
        for j in order:
            sid = ids[group[j]]
            excluded = sid in reasons
            rank = None if excluded else len(rows) + 1
            rows.append({"rank": rank, "skill_id": sid, "score": round(float(scores[j]), 6), "excluded": excluded,
                         "reason": reasons.get(sid), "selected": rank is not None and rank <= k})
    return rows


def select_all(index: Dict[str, Any], env: Environment, ram_mode: str, k: int, seed: int,
               encoders: Optional[Sequence[str]] = None, index_sha256: Optional[str] = None) -> Dict[str, Any]:
    ids = [s["id"] for s in index["skills"]]
    reasons = {s["id"]: r for s in index["skills"] if (r := exclusion_reason(s["id"], s["constraints"], env))}
    available = list(index["encoders"])
    if encoders:
        from .encoders import canonical_spec        # pure string parsing, no model import
        encoders = [canonical_spec(s) for s in encoders]
        unknown = [s for s in encoders if s not in index["encoders"]]
        if unknown:
            raise ValueError(f"encoder(s) {unknown} not in the index; available: {available}")
    runs = []
    for spec in encoders or available:
        enc = index["encoders"][spec]
        matrix = np.asarray([enc["skill_vectors"][sid] for sid in ids], dtype=np.float32)
        tasks = {}
        for task in index["tasks"]:
            rows = _ranking(np.asarray(enc["task_vectors"][task["id"]], dtype=np.float32), matrix, ids, reasons, k)
            tasks[task["id"]] = {"selected": [r["skill_id"] for r in rows if r["selected"]], "ranking": rows}
        runs.append({"params": {"encoder": spec, "representation": index["representation"], "k": k, "seed": seed,
                                "seed_note": "cosine ranking is deterministic; seed recorded for reproducibility only",
                                "ram_mode": ram_mode, "os": env.os_name, "tier1_excluded": sorted(reasons)},
                     "tasks": tasks})
    return {"schema": SCHEMA, "index_sha256": index_sha256, "index_created_at": index["created_at"],
            "snapshot": index["snapshot"], "runs": runs}
