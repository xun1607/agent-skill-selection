"""The ported graph selectors must reproduce GR1's own outputs (fixture written by scripts/dump_gr1_graph_parity.py)."""
import json
from pathlib import Path

import pytest

pytest.importorskip("sklearn")
from skill_selection.selectors.graph import core, parsing_heuristic as H  # noqa: E402
from skill_selection.selectors.graph.scorers import TfidfScorer  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
FIXTURE = json.loads((REPO / "tests" / "fixtures" / "gr1_graph_parity.json").read_text(encoding="utf-8"))
SKILLRET = REPO / "data" / "raw" / "skillret" / "6583d7d2ed07" / "data"


def _jsonl(path):
    return [json.loads(line) for line in open(path, encoding="utf-8") if line.strip()]


def _text(s):
    return f"{s['name'].strip()} | {s['description'].strip()} | {s['body'].strip()}"


def _check(cases, skills, scorer):
    by_id = {s["id"]: s for s in skills}
    for case in cases:
        plan = H.decompose(case["text"])
        assert len(plan.states) == case["n_states"] and plan.valid == case["plan_valid"], case["id"]
        cands = []
        for sid in case["candidates"]:
            s = by_id[sid]
            c = H.contract(s["name"], s["description"], s["body"])
            cands.append(core.Candidate(sid, _text(s), c.precondition, c.completion))
        for mode, want in case["modes"].items():
            res = core.select(case["text"], plan, cands, scorer, mode, core.SelectParams(lam=-1.0, mu=0.5, k=3))
            assert res.selected == want["selected"], (case["id"], mode)
            assert res.ranking[:10] == want["top10"], (case["id"], mode)


def test_parity_on_gr1_tasks():
    skills = _jsonl(REPO / "benchmarks" / "gr1_internal" / "skills.jsonl")
    tasks = _jsonl(REPO / "benchmarks" / "gr1_internal" / "tasks.jsonl")
    cases = [c for c in FIXTURE["cases"] if c["source"] == "gr1"]
    assert len(cases) == 6
    _check(cases, skills, TfidfScorer([_text(s) for s in skills] + [t["text"] for t in tasks]))


@pytest.mark.skipif(not (SKILLRET / "skills" / "test.jsonl").exists(), reason="SkillRet v1.1 not downloaded")
def test_parity_on_skillret_queries():
    skills = [{"id": s["id"], "name": s["name"], "description": s.get("description", ""),
               "body": s.get("skill_md") or s.get("description", "")} for s in _jsonl(SKILLRET / "skills" / "test.jsonl")]
    cases = [c for c in FIXTURE["cases"] if c["source"] == "skillret"]
    assert len(cases) == 60
    _check(cases, skills, TfidfScorer([_text(s) for s in skills] + [c["text"] for c in cases]))
