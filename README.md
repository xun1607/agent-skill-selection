# agent_skill_selection

Framework thực nghiệm cho bài toán **chọn skill theo ngữ cảnh** (context-aware skill selection) của LLM agent.
Phần lõi là benchmark truy xuất: catalog skill + query + nhãn relevance → selector → evaluator. Agent chỉ là adapter
tùy chọn để kiểm chứng end-to-end (chưa có).

Tiếp nối đồ án GR1. Thuật toán mới (Graph base task decomposition, Thompson Sampling)

Khung schema GR2 và công cụ nhập skill theo commit từ Superpowers/Anthropic:
[hướng dẫn](docs/registry/README.md), [kế hoạch file](docs/registry/implementation-plan.md).
Phần này tạo inventory cần duyệt; adapter agent E2E chưa được triển khai.

## Cấu trúc

```
src/skill_selection/            BACKEND
  schemas.py        SkillRecord, QueryRecord, Qrels, SelectionResult
  datasets/         skillret.py (SkillRet, ghim revision), local_skills.py (thư mục SKILL.md), gr1.py (snapshot GR1)
  filters/          constraint.py (tầng 1: OS / RAM / blacklist, có lý do loại)
  encoders/         Qwen3-Embedding (local, ghim revision), OpenAI; cache trên đĩa; chỉ nạp khi cần
  selectors/        base.py (fit / select / update), random_selector.py, bm25.py, dense.py (cosine)
  evaluation/       metrics.py (nDCG, Recall, Precision, MAP, Completeness; ngữ nghĩa trec_eval)
  experiments/      runner.py (chạy offline, ghi artifact)
  explorer.py       tính sẵn index và kết quả chọn cho giao diện
  reporting/        markdown.py
  cli.py
app/explorer.py                 FRONTEND (Streamlit), chỉ đọc JSON đã tính sẵn
benchmarks/gr1_internal/        snapshot bộ GR1 (41 skill, 6 nhiệm vụ, cổng kiểm định), kiểm sha256
scripts/                        export snapshot GR1, kiểm tra trùng khớp với GR1 (chạy bằng venv GR1)
tests/              unit/, integration/
doc/                nhật ký công việc theo ngày / tuần
data/               raw/ (tải về), processed/ -- không commit
artifacts/          runs/, reports/, explorer/, cache/ -- không commit
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

## Giao diện Explorer (bộ GR1)

Cài một lần (Windows cmd, trong thư mục repo):

```bat
python -m venv .venv
.venv\Scripts\activate
pip install torch --index-url https://download.pytorch.org/whl/cpu
pip install -e ".[dev,embed,app]"
```

Tính sẵn (lần đầu tải Qwen3-Embedding-0.6B khoảng 1.2 GB; các lần sau chạy offline, không gọi API):

```bat
python -m skill_selection index gr1
python -m skill_selection select gr1 --seed 0 --ram-mode fixed:8192 --os windows --k 3
streamlit run app/explorer.py
```

Ba khu vực: nhiệm vụ (kèm trạng thái cổng kiểm định), thư viện skill (tìm kiếm, xem SKILL.md), kết quả chọn
(hạng, điểm cosine, bị loại ở tầng 1 và lý do, 3 skill được chọn). Giao diện chỉ đọc
`artifacts/explorer/skill_index.json` và `selection_cache.json`; `select` chạy lại cho tệp giống hệt từng byte.

## Kết quả baseline (SkillRet test, %)

| Phiên bản | Selector                | NDCG@10 | Recall@10 | Completeness@10 |
| --------- | ----------------------- | ------: | --------: | --------------: |
| v1.0      | BM25 (bài báo, Table 3) |   48.86 |     56.55 |           41.09 |
| v1.0      | BM25 (repo này)         |   48.86 |     56.55 |           41.08 |
| v1.1      | BM25 (repo này)         |   51.69 |     59.41 |           44.56 |
| v1.1      | Random                  |    0.12 |      0.20 |            0.09 |
