"""Record what GR1's own skill_graph code outputs, as the oracle for the ported copy in src/skill_selection/selectors/graph.

What it does
  Runs GR1 experiments/skill_graph (core.select with the heuristic parser and TfidfScorer, exactly the S2 setup) on
  (a) the 6 GR1 tasks against all 41 skills of the snapshot and (b) the first 60 SkillRet v1.1 test queries against
  their 30 best TF-IDF candidates, for every mode. Nothing in GR1 is written.

Input
  benchmarks/gr1_internal/ (snapshot) and data/raw/skillret/6583d7d2ed07/data/*/test.jsonl.
  Run with GR1's interpreter:  <gr1>/../../venv/Scripts/python.exe scripts/dump_gr1_graph_parity.py

Output
  tests/fixtures/gr1_graph_parity.json: per case and mode the plan size, selected skills and the top-10 ranking.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
GR1 = REPO.parent / "gr1-prj" / "ai-software-engineering-agent" / "backend" / "services" / "skill_testing"
MODES = ("full", "no_split", "no_edges", "state_rank", "path")
N_SKILLRET, K = 60, 30


def jsonl(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def main() -> int:
    sys.path.insert(0, str(GR1 / "experiments"))
    from skill_graph import core, parsing_heuristic as H
    from skill_graph.scorers import TfidfScorer

    cases = []
    gr1_skills = jsonl(REPO / "benchmarks" / "gr1_internal" / "skills.jsonl")
    gr1_tasks = jsonl(REPO / "benchmarks" / "gr1_internal" / "tasks.jsonl")
    for t in gr1_tasks:
        cases.append(("gr1", t["id"], t["text"], gr1_skills))
    sk_root = REPO / "data" / "raw" / "skillret" / "6583d7d2ed07" / "data"
    sr_skills = [{"id": s["id"], "name": s["name"], "description": s.get("description", ""),
                  "body": s.get("skill_md") or s.get("description", "")} for s in jsonl(sk_root / "skills" / "test.jsonl")]
    sr_queries = jsonl(sk_root / "queries" / "test.jsonl")[:N_SKILLRET]

    def text(s):
        return f"{s['name'].strip()} | {s['description'].strip()} | {s['body'].strip()}"

    tfidf_gr1 = TfidfScorer([text(s) for s in gr1_skills] + [t["text"] for t in gr1_tasks])
    tfidf_sr = TfidfScorer([text(s) for s in sr_skills] + [q["query"] for q in sr_queries])
    out = []
    for source, qid, qtext, pool in cases + [("skillret", q["id"], q["query"], None) for q in sr_queries]:
        scorer = tfidf_gr1 if source == "gr1" else tfidf_sr
        if pool is None:                                       # SkillRet: 30 best TF-IDF candidates
            sims = scorer.score([qtext], [text(s) for s in sr_skills])[0]
            pool = [sr_skills[i] for i in np.argsort(-sims, kind="stable")[:K]]
        plan = H.decompose(qtext)
        cands = []
        for s in pool:
            c = H.contract(s["name"], s["description"], s["body"])
            cands.append(core.Candidate(s["id"], text(s), c.precondition, c.completion))
        record = {"source": source, "id": qid, "text": qtext, "candidates": [c.id for c in cands],
                  "n_states": len(plan.states), "plan_valid": plan.valid, "modes": {}}
        for mode in MODES:
            res = core.select(qtext, plan, cands, scorer, mode, core.SelectParams(lam=-1.0, mu=0.5, k=3))
            record["modes"][mode] = {"selected": res.selected, "top10": res.ranking[:10]}
        out.append(record)
    dest = REPO / "tests" / "fixtures" / "gr1_graph_parity.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps({"oracle": "GR1 experiments/skill_graph", "k_candidates": K, "cases": out},
                               ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {dest}: {len(out)} cases x {len(MODES)} modes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
