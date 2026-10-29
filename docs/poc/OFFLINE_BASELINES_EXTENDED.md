# Bổ sung offline baselines — 23/10/2026

## Phạm vi

Bổ sung hai phương pháp vào pipeline hiện có: **TF-IDF + cosine** và **MiniLM + cosine**. Không sửa dataset, qrels, evaluator, PoC A hoặc artifacts cũ; không tuning bằng test labels, không gọi API model.

Cả hai tái sử dụng `Selector.fit(catalog)` / `select(query, k)`, `SelectionResult`, CLI, offline runner, metrics và reporting. MiniLM tái sử dụng `SentenceTransformerEncoder` và `rank_by_cosine` đã có; không xây pipeline embedding mới.

## Protocol và cấu hình

- SkillRet v1.1 test: 6.006 skills, 4.392 queries, 7.187 qrels; revision `6583d7d2ed07644d0fb8938ed8178f3a7dc42a12`.
- Cùng corpus/query như Random/BM25; retrieval k=15, evaluation k=5/10/15. Ground truth chỉ đưa vào evaluator.
- **TF-IDF:** tokenization/stopwords giống BM25 hiện có; tf=`1+ln(tf)`, smoothed idf=`ln((1+N)/(1+df))+1`; L2 normalization, cosine similarity, bỏ zero-score documents, ties theo catalog order. Chỉ fit IDF trên catalog.
- **MiniLM:** `sentence-transformers/all-MiniLM-L6-v2`, revision `c9745ed1d9f207416be6d2e6f8de32d1f16199bf`; local CPU, float32, 384 dimensions, max sequence length 256, document batch size 32, query batch size 1, không thêm query instruction. Model đã có trong cache; chạy với `HF_HUB_OFFLINE=1`, không tải model mới.
- MiniLM có thể cắt skill documents dài ở 256 tokens. Đây là baseline dense gọn, không đại diện cho mọi embedding model hay retriever tối ưu riêng cho SkillRet.

## Source và tests

- [TFIDFSelector](../../src/skill_selection/selectors/tfidf.py).
- [MiniLMSelector](../../src/skill_selection/selectors/minilm.py).
- [Selector registry](../../src/skill_selection/selectors/__init__.py): thêm `tfidf`, `minilm`; CLI nhận lựa chọn qua registry hiện có.
- [Tests](../../tests/unit/test_additional_selectors.py): cosine tính tay, IDF không học từ query, OOV/empty/tie/k, fake encoder và tích hợp runner.

Lệnh kiểm tra đã chạy, exit 0: **19 tests PASS**.

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_additional_selectors.py tests/unit/test_selectors.py tests/unit/test_metrics.py tests/integration/test_runner.py --junitxml artifacts/additional-baselines-tests.xml
```

TF-IDF còn được đối chiếu độc lập với `sklearn.feature_extraction.text.TfidfVectorizer` trên toàn corpus và 33 queries lấy cách đều theo thứ tự gốc: ranking khớp, sai số scores dưới `1e-12`. Không chọn query theo nhãn hoặc mức metric.

## Lệnh chạy

Output root mới: `artifacts/poc-b-20261023-extra/`, không ghi đè hai run reproduce cũ.

```powershell
.\.venv\Scripts\python.exe -m skill_selection --revision v1.1 --artifacts artifacts/poc-b-20261023-extra run --selector tfidf --split test --k 15

$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:TOKENIZERS_PARALLELISM = 'false'
.\.venv\Scripts\python.exe -m skill_selection --revision v1.1 --artifacts artifacts/poc-b-20261023-extra run --selector minilm --split test --k 15
```

Runner đặt tên run theo config nên cùng config/output root có thể ghi đè. Dùng root mới khi thực hiện đợt khác. Các biến môi trường ở trên áp dụng cho terminal hiện tại; không sửa global config.

## Kết quả

Hai lệnh mới đều **exit code 0**. Mỗi phương pháp đánh giá đủ **4.392 queries**, cùng corpus **6.006 skills** và **7.187 qrels**. Bảng dưới dùng tỷ lệ [0,1], làm tròn 9 chữ số; Random/BM25 được lấy từ đợt reproduce đã kiểm chứng, không chạy lại hay ghi đè.

| Phương pháp | NDCG@10 | Recall@10 | Completeness@10 |
|---|---:|---:|---:|
| Random | 0.001181629 | 0.002011233 | 0.000910747 |
| BM25 | 0.516859261 | 0.594072556 | 0.445582878 |
| TF-IDF + cosine | 0.662205291 | 0.747950820 | 0.609744991 |
| MiniLM + cosine | 0.515836839 | 0.580411354 | 0.419171220 |

**71 kiểm tra hậu nghiệm PASS** trên bốn artifact sets: coverage/ID/k/scores/metrics, tính lại từ ranking, mọi ô CSV và renderer báo cáo. Input/source hashes không đổi trong đợt mở rộng. Hai baseline mới chưa có lần reproduce độc lập thứ hai; đây là kết quả execution đầu tiên đã được kiểm tra, không gọi là đã reproduce lặp lại.

- [TF-IDF + cosine report](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_tfidf_a37d3f18fa/report.md); [metrics.json](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_tfidf_a37d3f18fa/metrics.json); [manifest.json](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_tfidf_a37d3f18fa/manifest.json).
- [MiniLM + cosine report](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_minilm_083e427ef7/report.md); [metrics.json](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_minilm_083e427ef7/metrics.json); [manifest.json](../../artifacts/poc-b-20261023-extra/runs/skillret-6583d7d-test_minilm_083e427ef7/manifest.json).
- [Bảng so sánh và timing](../../artifacts/poc-b-20261023-extra/COMPARISON.md).
- [Validation](../../artifacts/poc-b-20261023-extra/validation.json).

Các giá trị là kết quả của cấu hình cố định trên test split này. Không chọn hyperparameters theo test labels hoặc chọn run tốt nhất. MiniLM là model generic với giới hạn 256 tokens; không dùng riêng kết quả của nó để kết luận embedding nói chung kém hoặc tốt hơn lexical retrieval. TF-IDF được đối chiếu độc lập về phép tính với scikit-learn, nhưng chưa có ablation để giải thích nguyên nhân mọi chênh lệch metric.

## Bằng chứng

- [JUnit](../../artifacts/additional-baselines-tests.xml).
- [TF-IDF độc lập với scikit-learn](../../artifacts/poc-b-20261023-extra/tfidf-independent-check.json).
- [Dataset/source provenance](../../artifacts/poc-b-20261023-extra/provenance.json).
- [Model revision và hashes](../../artifacts/poc-b-20261023-extra/model-provenance.json).
- [Commands và exit codes](../../artifacts/poc-b-20261023-extra/commands.json).

Kết quả retrieval theo relevance không phải bằng chứng skill giúp agent hoàn thành task. Benchmark hiện không có query thiếu positive nên chưa đánh giá no-skill correctness. Những kết quả này không làm thay đổi kết luận PoC A.
