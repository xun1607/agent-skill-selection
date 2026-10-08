"""Collect every SkillRet v1.1 test number used in the comparison into one file, each row with its provenance.

What it does
  Gathers three kinds of rows and never mixes them up:
    reproduced_here  runs of this repo (artifacts/runs/<run>/metrics.json)
    reproduced_gr1   runs of the GR1 codebase, S2 heuristic study (results/sandbox/s2_20261001_201807/metrics.json)
    paper_reported   numbers printed in the SkillRet paper (arXiv 2605.05726, Tables 3-4), typed from the paper
  For BM25 it also records whether our run matches the paper (|delta| <= 0.05 points on every metric).

Input: the run folders above (paths printed if missing). Output: benchmarks/reference/skillret_v1.1_test.json.
"""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
GR1_S2 = (REPO.parent / "gr1-prj" / "ai-software-engineering-agent" / "backend" / "services" / "skill_testing"
          / "results" / "sandbox" / "s2_20261001_201807" / "metrics.json")
METRICS = ("NDCG@10", "Recall@10", "Completeness@10")
PAPER = "SkillRet (arXiv 2605.05726)"
# Table 3 (first stage, corrected benchmark: 6,006 skills, 4,392 queries) and Table 4 (+Rerank on first-stage top-20)
PAPER_ROWS = [
    ("BM25", "Từ khoá", {"NDCG@10": 51.69, "Recall@10": 59.41, "Completeness@10": 44.56}, "Table 3"),
    ("Qwen3-Embedding-0.6B (SkillRet-base)", "Vector nhúng", {"NDCG@10": 61.94, "Recall@10": 67.87, "Completeness@10": 51.09}, "Table 3"),
    ("Qwen3-Embedding-8B", "Vector nhúng", {"NDCG@10": 63.64, "Recall@10": 70.29, "Completeness@10": 54.14}, "Table 3"),
    ("SkillRouter-Embedding-0.6B", "Vector nhúng (tinh chỉnh)", {"NDCG@10": 73.54, "Recall@10": 78.18, "Completeness@10": 62.70}, "Table 3"),
    ("SkillRet-Embedding-0.6B (SkillRet-FT)", "Vector nhúng (tinh chỉnh)", {"NDCG@10": 81.12, "Recall@10": 87.74, "Completeness@10": 78.94}, "Table 3"),
    ("SkillRet-Embedding-8B", "Vector nhúng (tinh chỉnh)", {"NDCG@10": 86.44, "Recall@10": 93.25, "Completeness@10": 88.11}, "Table 3"),
    ("SkillRouter-Reranker-0.6B (+Rerank top-20)", "Truy hồi + xếp hạng lại", {"NDCG@10": 86.78}, "Table 4"),
    ("SkillRet-Reranker-0.6B (+Rerank top-20)", "Truy hồi + xếp hạng lại", {"NDCG@10": 87.74}, "Table 4"),
]
GR1_ROWS = [("M0-hyb", "BM25 + TF-IDF (không hợp đồng, không đồ thị)", "Từ khoá lai"),
            ("M4-SR", "SkillReranker-h: lõi chế độ full, bộ phân rã heuristic, scorer TF-IDF, ứng viên BM25 top-30",
             "Phân rã nhiệm vụ + đồ thị trạng thái"),
            ("M4", "Xếp hạng theo trạng thái (heuristic)", "Trạng thái"),
            ("M5", "Đề xuất: đường đi trên đồ thị trạng thái (heuristic, lambda/mu chỉnh trên train)", "Đề xuất"),
            ("M5-nc", "M5 không dùng hợp đồng tiền điều kiện/kết quả", "Đề xuất (ablation)")]


def run_metrics(prefix: str) -> dict:
    runs = sorted((REPO / "artifacts" / "runs").glob(f"{prefix}*/metrics.json"))
    if not runs:
        raise SystemExit(f"missing artifacts/runs/{prefix}*: run `python -m skill_selection run ...` first")
    m = json.loads(runs[-1].read_text(encoding="utf-8"))
    mean = m.get("mean", m)
    return {k: round(mean[k] * 100, 2) for k in METRICS}, runs[-1].parent.name


def main() -> int:
    rows = []
    bm25, bm25_run = run_metrics("skillret-6583d7d-test_bm25_")
    rand, rand_run = run_metrics("skillret-6583d7d-test_random_")
    paper_bm25 = PAPER_ROWS[0][2]
    rows.append({"method": "BM25", "family": "Từ khoá", "provenance": "reproduced_here", "source": f"artifacts/runs/{bm25_run}",
                 "metrics": bm25, "matches_paper": all(abs(bm25[k] - paper_bm25[k]) <= 0.05 for k in METRICS)})
    rows.append({"method": "Random", "family": "Sàn", "provenance": "reproduced_here", "source": f"artifacts/runs/{rand_run}",
                 "metrics": rand})
    if GR1_S2.exists():
        s2 = json.loads(GR1_S2.read_text(encoding="utf-8"))
        for key, desc, family in GR1_ROWS:
            a = s2[key]["all"]
            rows.append({"method": key, "family": family, "description": desc, "provenance": "reproduced_gr1",
                         "source": "GR1 results/sandbox/s2_20261001_201807 (tham số chỉnh trên 200 truy vấn train)",
                         "metrics": {**{k: round(a[k] * 100, 2) for k in METRICS},
                                     "set_f1": round(a["set_f1"] * 100, 2), "n_selected": round(a["n_selected"], 2)}})
    else:
        print(f"GR1 S2 results not found at {GR1_S2}; skipped")
    for name, family, metrics, table in PAPER_ROWS:
        rows.append({"method": name, "family": family, "provenance": "paper_reported", "source": f"{PAPER}, {table}",
                     "metrics": metrics})
    out = REPO / "benchmarks" / "reference" / "skillret_v1.1_test.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"dataset": "SkillRet v1.1 test (6,006 skills, 4,392 queries), metrics in %",
                               "not_available": {"GoS / GoS-lite": "chưa chạy trên SkillRet (bài báo GoS không báo cáo SkillRet)"},
                               "rows": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"wrote {out}: {len(rows)} rows; BM25 matches paper: {rows[0]['matches_paper']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
