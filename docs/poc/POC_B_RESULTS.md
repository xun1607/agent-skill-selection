# PoC B — Reproduce Offline Evaluation

Ngày 23/10/2026. **PASS**: chạy lại Random/BM25 trên SkillRet v1.1 bằng pipeline hiện có. Không sửa source, dataset, qrels, evaluator, test hoặc PoC A; không gọi LLM, tuning hay commit.

## Lệnh thực sự đã chạy

Chạy tại repo, Python trong `.venv`. Các lệnh sau đều **exit code 0**:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_metrics.py tests/unit/test_selectors.py tests/integration/test_runner.py --basetemp artifacts/poc-b-20261023/pytest-tmp --junitxml artifacts/poc-b-20261023/tests.xml

.\.venv\Scripts\python.exe -m skill_selection --revision v1.1 --artifacts artifacts/poc-b-20261023 run --selector random --split test --k 15 --seed 0

.\.venv\Scripts\python.exe -m skill_selection --revision v1.1 --artifacts artifacts/poc-b-20261023 run --selector bm25 --split test --k 15
```

CLI đã được kiểm tra bằng `run --help` và parser hiện tại trước execution. Output root chưa tồn tại; tạo mới với `exist_ok=False`, không ghi đè artifact cũ. `commands.json` lưu argv thực tế với đường dẫn Python tuyệt đối, cwd, exit code và log.

## Protocol đã kiểm tra

- Revision `6583d7d2ed07644d0fb8938ed8178f3a7dc42a12`, split test, không limit: **6.006 skills, 4.392 queries, 7.187 dòng qrels**, không trùng cặp qrel, mọi relevance đều bằng 1.
- Cả hai baseline dùng cùng loader/corpus/query; hash file đầu vào trước và sau khớp. Selector không nhận gold skill IDs/names hoặc gold k trong QueryRecord.
- Random seed 0. BM25 giữ nguyên mặc định k1=1.5, b=0.75, Lucene IDF/English stopwords; không có seed ngẫu nhiên.
- Retrieval k=15; evaluation tại k=5/10/15. Thực tế mọi ranking của cả hai baseline đều dài 15, ID hợp lệ, không trùng; scores hữu hạn, giảm dần.
- Relevant là relevance > 0; skill không được gán nhãn được chấm như không relevant theo protocol. NDCG dùng gain tuyến tính relevance, discount log2(rank+1), chia ideal DCG. Recall chia tổng positive; Precision chia k; AP chia tổng positive; Completeness bằng 1 khi lấy đủ mọi positive trong top-k. Metrics tổng hợp là macro mean trên query.
- Có 2.143 query với 1 positive, 1.703 với 2, 546 với 3. Không chọn một nhãn đại diện: Recall/MAP/Completeness xét toàn bộ positive. Không query thiếu positive, thiếu ranking hoặc mismatch giữa qrels và label list trong raw query.
- Query không positive sẽ bị evaluator bỏ qua; query có qrels nhưng thiếu ranking được chấm 0. Điều này không chứng minh hỗ trợ no-skill.

## Kết quả mới và đối chiếu cũ

Đơn vị **tỷ lệ [0,1]**, không phải phần trăm:

| Phương pháp | NDCG@10 | Recall@10 | Completeness@10 |
|---|---:|---:|---:|
| Random | 0.001181629203102274 | 0.002011232544019429 | 0.0009107468123861566 |
| BM25 | 0.5168592611916537 | 0.5940725561627201 | 0.4455828779599271 |

**12 tests pass**; **49 kiểm tra hậu nghiệm pass**. Mỗi phương pháp có đủ 4.392 query; n_skipped_no_relevant=0, n_missing_from_run=0. Tính lại metrics từ run.jsonl khớp metrics.json; mọi ô per_query.csv khớp theo làm tròn 6 chữ số; report.md khớp renderer của kết quả đã kiểm tra. Không NaN/Inf.

So với artifact v1.1 cũ trong `artifacts/runs/`, cả hai phương pháp có **0 ranking khác, scores giống hệt, mọi metric có delta=0**. `metrics.json` và `per_query.csv` khớp từng byte. Thời gian và timestamp khác là dữ liệu runtime của các lần thực thi khác nhau; chưa cô lập nguyên nhân biến thiên thời gian, không kết luận về tăng/giảm hiệu năng.

| Phương pháp | Fit mới / cũ (s) | Selection mới / cũ (s) |
|---|---:|---:|
| Random | 0 / 0 | 0.178 / 0.261 |
| BM25 | 23.714 / 7.640 | 7.774 / 9.329 |

## Artifact và provenance

- [Báo cáo tái lập đầy đủ](../../artifacts/poc-b-20261023/REPRODUCTION.md)
- [Validation: 49 checks](../../artifacts/poc-b-20261023/validation.json)
- [Provenance: input/source hashes và versions](../../artifacts/poc-b-20261023/provenance.json)
- [Commands và exit codes](../../artifacts/poc-b-20261023/commands.json)
- [JUnit](../../artifacts/poc-b-20261023/tests.xml)
- [Random](../../artifacts/poc-b-20261023/runs/skillret-6583d7d-test_random_d6955ee161/report.md)
- [BM25](../../artifacts/poc-b-20261023/runs/skillret-6583d7d-test_bm25_4df95007ee/report.md)

Mỗi run có manifest.json, run.jsonl, per_query.csv, metrics.json, report.md và reproduction-inputs.json. File bổ sung lưu raw/normalized input hashes và selector config; BM25 seed=null vì không dùng RNG.

Repo đang dirty, nên không dùng riêng git HEAD để mô tả source chạy. `source-snapshot/`, `source-tracked-before.patch`, `source-status-before.txt`, `source-status-after.txt` và source hashes bảo toàn trạng thái liên quan. Source/dataset hashes không đổi trong quá trình chạy. Manifest cũ không có hash raw input/source, nên chưa chứng minh được historical input/source khớp từng byte; kết quả đầu ra đã tái lập chính xác.

## PASS / FAIL / NOT_VERIFIED

- **PASS:** protocol theo code, tests, execution hai baseline, số lượng/ID/k, artifact nhất quán, hash input/source không đổi và đầu ra khớp artifact cũ.
- **FAIL:** không có trong lượt reproduce này.
- **NOT_VERIFIED:** chạy đối chiếu pytrec_eval bên ngoài, tái lập độc lập bảng số liệu paper, chất lượng nhãn do người kiểm định, historical input/source byte identity.

PoC chứng minh pipeline offline hiện có tái lập được ranking và metrics Random/BM25 trên benchmark cố định. Chưa chứng minh skill giúp agent hoàn thành task, chưa đánh giá quyết định no-skill hay thuật toán mới. Không chuyển sang triển khai PoC A trong lượt này.
