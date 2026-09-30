import json

from skill_selection.experiments.runner import run_offline
from skill_selection.schemas import QueryRecord, SkillRecord
from skill_selection.selectors import BM25Selector

CATALOG = [SkillRecord(id=f"s{i}", name=n, description=d, body="", source="t") for i, (n, d) in enumerate([
    ("pytest-runner", "run pytest tests"),
    ("git-conflict", "resolve git merge conflicts"),
    ("docker-inspect", "inspect docker containers"),
])]
QUERIES = [QueryRecord(id="q1", text="my pytest tests fail", source="t"),
           QueryRecord(id="q2", text="git merge conflict", source="t")]
QRELS = {"q1": {"s0": 1}, "q2": {"s1": 1}}


def test_run_offline_writes_artifacts_and_is_idempotent(tmp_path):
    ds = {"name": "toy", "split": "test", "revision": "r"}
    out = run_offline(BM25Selector(), CATALOG, QUERIES, QRELS, k=2, dataset=ds, out_root=tmp_path, ks=(1, 2))
    assert out.report.mean["NDCG@1"] == 1.0
    assert out.report.mean["Completeness@2"] == 1.0
    for name in ("manifest.json", "run.jsonl", "per_query.csv", "metrics.json", "report.md"):
        assert (out.run_dir / name).exists()
    rows = [json.loads(l) for l in (out.run_dir / "run.jsonl").read_text(encoding="utf-8").splitlines()]
    assert [r["query_id"] for r in rows] == ["q1", "q2"]
    again = run_offline(BM25Selector(), CATALOG, QUERIES, QRELS, k=2, dataset=ds, out_root=tmp_path, ks=(1, 2))
    assert again.run_dir == out.run_dir                  # same configuration -> same run directory
