# agent_skill_selection

Framework thực nghiệm cho bài toán **chọn skill theo ngữ cảnh** (context-aware skill selection) của LLM agent.
Phần lõi là benchmark truy xuất: catalog skill + query + nhãn relevance → selector → evaluator. Agent chỉ là adapter
tùy chọn để kiểm chứng end-to-end (chưa có).

Tiếp nối đồ án GR1 (`D:/PROJECT_GIT/gr1-prj`, bản tham chiếu). Thuật toán mới (Graph, Thompson Sampling) tạm thời vẫn
thử nghiệm ở codebase GR1 rồi mới chuyển sang đây.

## Cấu trúc

```
src/skill_selection/
  schemas.py        SkillRecord, QueryRecord, Qrels, SelectionResult
  datasets/         skillret.py (SkillRet, ghim revision), local_skills.py (thư mục SKILL.md)
  selectors/        base.py (fit / select / update), random_selector.py, bm25.py
  evaluation/       metrics.py (nDCG, Recall, Precision, MAP, Completeness; ngữ nghĩa trec_eval)
  experiments/      runner.py (chạy offline, ghi artifact)
  reporting/        markdown.py
  cli.py
tests/              unit/, integration/
docs/               protocol.md, worklog/
data/               raw/ (tải về), processed/ -- không commit
artifacts/          runs/, reports/ -- không commit
```

Nguyên tắc: lõi retrieval không import LangChain/LangGraph/sandbox/API client; selector không bao giờ thấy nhãn
(chỉ evaluator đọc qrels); mọi dataset tải về được ghim theo commit.

## Chạy

Không cần cài đặt, chỉ cần `numpy`, `scipy`, `pyyaml` (và `pytest` để chạy test):

```bash
cd D:/PROJECT_GIT/agent_skill_selection
export PYTHONPATH=src            # PowerShell: $env:PYTHONPATH = "src"
python -m pytest -q

python -m skill_selection download skillret --split test                  # v1.1 (mặc định)
python -m skill_selection --revision v1.0 download skillret --split test  # v1.0 (bản của bài báo)
python -m skill_selection stats skillret --split test
python -m skill_selection run --selector bm25 --k 15
python -m skill_selection --revision v1.0 run --selector bm25 --k 15      # so với số của bài báo
python -m skill_selection catalog --path <thư mục skills> --out data/processed/gr1_skills.jsonl --source gr1
```

Hoặc cài dạng editable: `pip install -e ".[dev]"`, sau đó dùng lệnh `skill-selection ...`.

## Kết quả baseline (SkillRet test, %)

| Phiên bản | Selector | NDCG@10 | Recall@10 | Completeness@10 |
|---|---|---:|---:|---:|
| v1.0 | BM25 (bài báo, Table 3) | 48.86 | 56.55 | 41.09 |
| v1.0 | BM25 (repo này) | 48.86 | 56.55 | 41.08 |
| v1.1 | BM25 (repo này) | 51.69 | 59.41 | 44.56 |
| v1.1 | Random | 0.12 | 0.20 | 0.09 |

Chi tiết và cách tái lập: [docs/worklog/2026-09-30.md](docs/worklog/2026-09-30.md).
