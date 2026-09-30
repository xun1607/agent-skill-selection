"""Command line entry point: `skill-selection <command>` (or `python -m skill_selection <command>`).

  download skillret [--split test]              fetch the pinned SkillRet files into <data-root>/raw/
  stats skillret [--split test]                 dataset statistics -> artifacts/reports/
  catalog --path <dir> --out <file.jsonl>       convert a SKILL.md folder into a skill catalog
  run --selector bm25 [--split test] [--k 15]   offline retrieval run -> artifacts/runs/<run id>/
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
    return p


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
