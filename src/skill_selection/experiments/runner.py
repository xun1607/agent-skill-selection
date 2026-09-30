"""Offline retrieval run: fit a selector on a catalog, rank every query once, evaluate, write artifacts.

A run directory is named after a hash of its configuration, so rerunning the same configuration overwrites it:
  manifest.json   configuration, dataset version, timings, environment
  run.jsonl       one SelectionResult per query (full ranking and scores)
  per_query.csv   metrics per query
  metrics.json    mean metrics and evaluation counts
  report.md       human-readable summary
"""
from __future__ import annotations

import csv
import hashlib
import json
import platform
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Mapping, Optional, Sequence

from .. import __version__
from ..evaluation.metrics import DEFAULT_KS, EvalReport, evaluate
from ..io import write_json, write_jsonl
from ..reporting.markdown import run_report
from ..schemas import QueryRecord, Qrels, SkillRecord
from ..selectors.base import Selector


@dataclass
class RunOutput:
    run_dir: Path
    report: EvalReport
    manifest: Dict


def config_hash(config: Mapping) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()[:10]


def run_offline(selector: Selector, catalog: Sequence[SkillRecord], queries: Sequence[QueryRecord], qrels: Qrels,
                *, k: int, dataset: Mapping, out_root: Path, ks: Sequence[int] = DEFAULT_KS,
                reference: Optional[Mapping[str, float]] = None) -> RunOutput:
    config = {"selector": selector.config(), "dataset": dict(dataset), "k": k, "ks": list(ks),
              "n_queries": len(queries)}
    version = f"-{dataset['revision'][:7]}" if dataset.get("revision") else ""
    run_id = f"{dataset['name']}{version}-{dataset['split']}_{selector.name}_{config_hash(config)}"
    run_dir = Path(out_root) / run_id

    t0 = time.perf_counter()
    selector.fit(catalog)
    fit_s = time.perf_counter() - t0

    t1 = time.perf_counter()
    results = [selector.select(q, k) for q in queries]
    select_s = time.perf_counter() - t1

    # only the queries of this run are evaluated (a --limit run is scored on its subset)
    run = {r.query_id: r.skill_ids for r in results}
    report = evaluate(run, {q.id: qrels.get(q.id, {}) for q in queries}, ks)

    manifest = {
        "run_id": run_id, **config,
        "catalog_size": len(catalog),
        "fit_seconds": round(fit_s, 3),
        "select_seconds": round(select_s, 3),
        "mean_latency_ms": round(1000 * select_s / max(len(queries), 1), 3),
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "package_version": __version__,
        "python": sys.version.split()[0],
        "platform": platform.platform(),
    }
    write_json(manifest, run_dir / "manifest.json")
    write_jsonl((r.to_dict() for r in results), run_dir / "run.jsonl")
    write_json({"mean": report.mean, "n_evaluated": report.n_evaluated,
                "n_skipped_no_relevant": report.n_skipped_no_relevant,
                "n_missing_from_run": report.n_missing_from_run}, run_dir / "metrics.json")
    _write_per_query(report, run_dir / "per_query.csv")
    (run_dir / "report.md").write_text(run_report(manifest, report, reference), encoding="utf-8")
    return RunOutput(run_dir=run_dir, report=report, manifest=manifest)


def _write_per_query(report: EvalReport, path: Path) -> None:
    names = list(report.mean)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["query_id"] + names)
        for qid, scores in report.per_query.items():
            w.writerow([qid] + [round(scores[n], 6) for n in names])
