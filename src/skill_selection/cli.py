"""Command line entry point: `skill-selection <command>` (or `python -m skill_selection <command>`).

  download skillret [--split test]              fetch the pinned SkillRet files into <data-root>/raw/
  stats skillret [--split test]                 dataset statistics -> artifacts/reports/
  catalog --path <dir> --out <file.jsonl>       convert a SKILL.md folder into a skill catalog
  run --selector bm25 [--split test] [--k 15]   offline retrieval run -> artifacts/runs/<run id>/
  index gr1 [--encoder SPEC ...]                embed the GR1 snapshot -> artifacts/explorer/skill_index.json
  select gr1 [--seed 0] [--ram-mode fixed:8192] [--os windows] [--k 3]
                                                Tier 1 + cosine top-k -> artifacts/explorer/selection_cache.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .datasets import skillret
from .datasets.local_skills import load_skill_dir
from .experiments.runner import run_offline
from .io import write_json, write_jsonl
from .reporting.markdown import metrics_table
from .selectors import REGISTRY, build_selector


def _revision(args) -> str:
    return skillret.REVISIONS.get(args.revision, args.revision)


def _cmd_download(args) -> int:
    paths = skillret.download(args.split, args.data_root, revision=_revision(args), force=args.force)
    for subset, path in paths.items():
        print(f"{subset:8s} {path} ({path.stat().st_size / 1e6:.1f} MB)")
    return 0


def _stats_markdown(stats: dict) -> str:
    rows = [(k, v) for k, v in stats.items() if k not in ("top_categories", "body_words", "positives_per_query",
                                                            "generator_models")]
    out = [f"# SkillRet {stats['split']} statistics", "", "| Field | Value |", "|---|---|"]
    out += [f"| {k} | {v} |" for k, v in rows]
    out += ["", "## Relevant skills per query", "", "| #relevant | #queries |", "|---:|---:|"]
    out += [f"| {n} | {c} |" for n, c in stats["positives_per_query"].items()]
    bw = stats["body_words"]
    out += ["", f"Skill body length (words): mean {bw['mean']}, median {bw['median']}, max {bw['max']}.", "",
            "## Top categories (major/sub)", "", "| Category | #skills |", "|---|---:|"]
    out += [f"| {c or '(none)'} | {n} |" for c, n in stats["top_categories"]]
    out += ["", f"Query generators: {stats['generator_models']}", ""]
    return "\n".join(out)


def _cmd_stats(args) -> int:
    stats = skillret.split_stats(args.split, args.data_root, revision=_revision(args))
    out = Path(args.artifacts) / "reports"
    stem = f"skillret_{args.revision}_{args.split}_stats"
    write_json(stats, out / f"{stem}.json")
    (out / f"{stem}.md").write_text(_stats_markdown(stats), encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))
    return 0


def _cmd_catalog(args) -> int:
    skills = load_skill_dir(Path(args.path), source=args.source)
    n = write_jsonl((s.to_dict() for s in skills), Path(args.out))
    print(f"{n} skills -> {args.out}")
    return 0


def _cmd_run(args) -> int:
    revision = _revision(args)
    skills, queries, qrels = skillret.load_split(args.split, args.data_root, revision=revision)
    if args.limit:
        queries = queries[:args.limit]
    params = {"seed": args.seed} if args.selector == "random" else {}
    selector = build_selector(args.selector, **params)
    dataset = {"name": "skillret", "split": args.split, "revision": revision, "limit": args.limit}
    reference = (skillret.PAPER_BM25 if args.selector == "bm25" and args.split == "test" and not args.limit
                 and revision == skillret.REVISIONS["v1.0"] else None)
    out = run_offline(selector, skills, queries, qrels, k=args.k, dataset=dataset,
                      out_root=Path(args.artifacts) / "runs", reference=reference)
    print(metrics_table(out.report.mean, out.report.ks, reference))
    print(f"\nrun written to {out.run_dir}")
    return 0


def _load_env_file(path: Path) -> None:
    """KEY=VALUE lines into os.environ (existing variables win); values are never printed."""
    import os
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _cmd_index(args) -> int:
    from .datasets.gr1 import load_gr1
    from .encoders import build_encoder
    from .explorer import build_index, write_json_stable
    if args.env_file:
        _load_env_file(args.env_file)
    bench = load_gr1()
    encoders = [build_encoder(spec, cache_dir=Path(args.artifacts) / "cache" / "embeddings") for spec in args.encoder]
    index = build_index(bench, encoders)
    out = Path(args.artifacts) / "explorer" / "skill_index.json"
    write_json_stable(index, out)
    for spec, enc in index["encoders"].items():
        print(f"{spec}: dim {enc['dim']}, {len(enc['skill_vectors'])} skills, {len(enc['task_vectors'])} tasks")
    print(f"index written to {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return 0


def _cmd_select(args) -> int:
    from .explorer import select_all, sha256_file, write_json_stable
    from .filters.constraint import Environment, parse_ram_mode
    index_path = Path(args.artifacts) / "explorer" / "skill_index.json"
    if not index_path.exists():
        raise SystemExit(f"{index_path} not found; run `python -m skill_selection index gr1` first")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    env = Environment(os_name=args.os, ram_mb=parse_ram_mode(args.ram_mode))
    try:
        cache = select_all(index, env, ram_mode=args.ram_mode, k=args.k, seed=args.seed, encoders=args.encoder,
                           index_sha256=sha256_file(index_path))
    except ValueError as e:
        raise SystemExit(str(e))
    out = Path(args.artifacts) / "explorer" / "selection_cache.json"
    write_json_stable(cache, out, pretty=True)
    for run in cache["runs"]:
        print(f"\n{run['params']['encoder']}  (Tier 1 excluded: {', '.join(run['params']['tier1_excluded']) or '-'})")
        for task_id, task in run["tasks"].items():
            print(f"  {task_id:24s} {', '.join(task['selected'])}")
    print(f"\nselection written to {out}  sha256 {sha256_file(out)[:16]}")
    return 0


def _cmd_compare(args) -> int:
    from .compare import METHODS, run_gr1, score_gr1
    from .datasets.gr1 import load_gr1
    from .explorer import write_json_stable
    bench = load_gr1()
    run = run_gr1(bench, cache_dir=Path(args.artifacts) / "cache" / "embeddings")
    scored = score_gr1(run, bench)
    out = Path(args.artifacts) / "compare" / "gr1.json"
    write_json_stable({"methods": METHODS, "info": run["info"], "tier1_excluded": run["tier1_excluded"],
                       "results": run["results"], **scored}, out, pretty=True)
    cols = ["Recall@3", "NDCG@3", "Recall@5", "Completeness@5", "set_f1", "n_selected"]
    print(f"labels: {scored['labels_status']}\n{'method':16s} " + " ".join(f"{c:>14s}" for c in cols) + "  checks")
    for m, row in scored["metrics"].items():
        ok = sum(c["passed"] for c in scored["checks"][m])
        print(f"{m:16s} " + " ".join(f"{row[c]:14.3f}" for c in cols) + f"  {ok}/{len(scored['checks'][m])}")
    print(f"\nwritten to {out}; rankings sha256 {scored['rankings_sha256'][:16]}")
    return 0


def _cmd_eval_run(args) -> int:
    """Score a ranked-list file produced elsewhere (e.g. scripts/colab_skillret_dense.py) with our metrics and qrels."""
    from .evaluation.metrics import evaluate
    from .io import iter_jsonl
    run = {row["query_id"]: row["skill_ids"] for row in iter_jsonl(Path(args.run))}
    _, queries, qrels = skillret.load_split(args.split, args.data_root, revision=_revision(args))
    missing = sorted(set(qrels) - set(run))
    if missing:
        print(f"warning: {len(missing)} queries of the qrels are not in the run (scored 0)")
    report = evaluate(run, qrels, ks=(5, 10, 15))
    mean = {k: round(v * 100, 2) for k, v in report.mean.items() if k != "n_selected"}
    out = Path(args.run).with_suffix(".metrics.json")
    write_json({"run": str(args.run), "revision": _revision(args), "n_evaluated": report.n_evaluated, "mean": mean}, out)
    for key in ("NDCG@10", "Recall@10", "Completeness@10"):
        print(f"{key:16s} {mean[key]:6.2f}")
    print(f"written to {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="skill-selection", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-root", default="data", type=Path)
    p.add_argument("--artifacts", default="artifacts", type=Path)
    p.add_argument("--revision", default="v1.1",
                   help="SkillRet version: v1.1 (default, Hub main), v1.0 (paper), or a commit hash")
    sub = p.add_subparsers(dest="command", required=True)

    d = sub.add_parser("download", help="fetch a dataset")
    d.add_argument("dataset", choices=["skillret"])
    d.add_argument("--split", default="test", choices=skillret.SPLITS)
    d.add_argument("--force", action="store_true")
    d.set_defaults(func=_cmd_download)

    s = sub.add_parser("stats", help="dataset statistics")
    s.add_argument("dataset", choices=["skillret"])
    s.add_argument("--split", default="test", choices=skillret.SPLITS)
    s.set_defaults(func=_cmd_stats)

    c = sub.add_parser("catalog", help="convert a SKILL.md folder into a catalog jsonl")
    c.add_argument("--path", required=True)
    c.add_argument("--out", required=True)
    c.add_argument("--source", default="local")
    c.set_defaults(func=_cmd_catalog)

    r = sub.add_parser("run", help="offline retrieval run on SkillRet")
    r.add_argument("--selector", required=True, choices=sorted(REGISTRY))
    r.add_argument("--split", default="test", choices=skillret.SPLITS)
    r.add_argument("--k", type=int, default=15)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--limit", type=int, default=0, help="only the first N queries (smoke test)")
    r.set_defaults(func=_cmd_run)

    from .encoders import DEFAULT_ENCODER
    i = sub.add_parser("index", help="embed a benchmark snapshot for the explorer")
    i.add_argument("dataset", choices=["gr1"])
    i.add_argument("--encoder", action="append", default=None,
                   help=f"repeatable; default {DEFAULT_ENCODER}. Example: openai:text-embedding-3-small")
    i.add_argument("--env-file", type=Path, help="file with OPENAI_API_KEY=... (only needed for openai:)")
    i.set_defaults(func=_cmd_index)

    e = sub.add_parser("select", help="Tier 1 + cosine top-k for every task, from the precomputed index")
    e.add_argument("dataset", choices=["gr1"])
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--ram-mode", default="fixed:8192")
    e.add_argument("--os", default="windows", choices=["windows", "linux", "darwin"])
    e.add_argument("--k", type=int, default=3)
    e.add_argument("--encoder", action="append", default=None, help="repeatable; default: every encoder in the index")
    e.set_defaults(func=_cmd_select)

    c = sub.add_parser("compare", help="run every baseline on a benchmark and score it against its labels")
    c.add_argument("dataset", choices=["gr1"])
    c.set_defaults(func=_cmd_compare)

    v = sub.add_parser("eval-run", help="score a ranked-list jsonl (query_id, skill_ids) against SkillRet qrels")
    v.add_argument("--run", required=True)
    v.add_argument("--split", default="test", choices=skillret.SPLITS)
    v.set_defaults(func=_cmd_eval_run)
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "command", None) == "index" and not args.encoder:
        from .encoders import DEFAULT_ENCODER
        args.encoder = [DEFAULT_ENCODER]
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
