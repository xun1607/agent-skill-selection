# Phân tích task và nhóm skill từ bốn baseline

**Ngày:** 23/10/2026. **Mục đích:** tìm hạn chế và xác định câu hỏi nghiên cứu tiếp theo từ kết quả đã chạy, không chọn thêm hyperparameters để làm đẹp test metrics.

Phân tích đọc lại ranking Random/BM25/TF-IDF/MiniLM trên cùng 4.392 queries, 6.006 skills và 7.187 qrels. Không chạy lại retrieval hoặc agent, không sửa nhãn. Metric theo nhóm được tính bằng evaluator hiện có, đối chiếu khớp số tổng đã lưu; [20 kiểm tra nhất quán PASS](../../artifacts/offline-analysis-20261023/validation.json).

## 1. Task trong benchmark có đặc điểm gì?

Có **2.249/4.392 query, khoảng 51,2%, được gán từ hai positive skills trở lên**. Đây là phần quan trọng nếu mục tiêu nghiên cứu là chọn *tập skill*, không chỉ tìm một skill đứng đầu.

Nhóm skill có metadata `major`, `sub`, `primary_action`, `domain`. Khi đối chiếu positive skills của mỗi query:

- **1.370 query (31,2%)** có positive skills thuộc nhiều major.
- **2.063 query (47,0%)** có positive skills thuộc nhiều nhóm major/sub.
- **1.997 query (45,5%)** có positive skills mang nhiều primary actions khác nhau.

Ví dụ, một task có thể vừa yêu cầu audit code, vừa sửa UI, vừa tạo PR. Một ranking tập trung vào “audit” có thể tìm đúng các tài liệu gần chủ đề nhưng chưa bao phủ các phần việc còn lại.

**Giới hạn cách phân nhóm:** đây là đặc điểm suy ra từ metadata của **gold skills**, chưa phải nhãn task intent được gán độc lập. Hai skill cùng là positive chỉ chứng minh chúng cùng được gán relevance cho query; chưa chứng minh dependency, complementarity hay conflict.

Nguồn: [summary.json](../../artifacts/offline-analysis-20261023/summary.json), [query-features.csv](../../artifacts/offline-analysis-20261023/query-features.csv), [skill-groups.csv](../../artifacts/offline-analysis-20261023/skill-groups.csv).

## 2. TF-IDF tốt về trung bình nhưng còn thiếu ở task multi-skill

**Completeness@10** là tỷ lệ query lấy đủ mọi positive ID trong top-10. Bảng dùng phần trăm; Recall của TF-IDF cũng là phần trăm.

| Số positive/query | Số query | BM25 Complete@10 | TF-IDF Complete@10 | MiniLM Complete@10 | TF-IDF Recall@10 |
|---|---:|---:|---:|---:|---:|
| 1 | 2.143 | 70,51% | **82,69%** | 72,05% | 82,69% |
| 2 | 1.703 | 24,49% | **45,86%** | 17,03% | 69,35% |
| 3 | 546 | 5,31% | **22,89%** | 1,28% | 60,81% |

Hiểu đơn giản: nếu cần ba món đồ, tìm đúng hai món vẫn là tìm được một phần khá lớn, nhưng chưa có đủ bộ. Vì vậy Recall và Completeness trả lời hai câu hỏi khác nhau.

TF-IDF đạt Completeness@10 tổng khoảng 61%, nhưng với nhóm ba positive chỉ có **125/546 query** lấy đủ cả ba. Kết quả tốt trên task một skill đang che bớt khó khăn ở task nhiều skill. Lấy đủ nhiều positive vốn là điều kiện chặt hơn lấy đủ một positive; sự suy giảm này **chưa tự chứng minh nguyên nhân là thiếu mô hình quan hệ**.

Tách lỗi TF-IDF ở top-10:

- **2.678 query:** lấy đủ tập positive.
- **1.200 query:** có lấy được positive nhưng chưa đủ tập.
- **514 query:** chưa lấy được positive nào.

Hai nhóm lỗi cuối cần hướng xử lý khác nhau: nhóm không có positive cần cải thiện hiểu task/candidate retrieval; nhóm thiếu một phần đáng được kiểm tra thêm về bao phủ các phần việc và ngân sách skill.

Nguồn: [groups.json — positive_count](../../artifacts/offline-analysis-20261023/groups.json), [group-metrics.csv](../../artifacts/offline-analysis-20261023/group-metrics.csv), [summary.json — tfidf_top10](../../artifacts/offline-analysis-20261023/summary.json).

## 3. Nhóm skill nào đang được đại diện và kết quả khác nhau ra sao?

Kho skill không chỉ chứa thao tác viết code. Có cả agent orchestration, lập kế hoạch, nội dung và tìm kiếm thông tin. **Software Engineering chiếm khoảng 62% corpus**, nên cần nhìn phân bố thay vì coi benchmark là một tập coding tasks đồng nhất.

Bảng dưới phân nhóm query theo major của gold skills. Nếu các gold skills thuộc nhiều major, query chỉ nằm trong hàng “Liên nhóm”, không được đếm lặp ở các hàng còn lại. Metric vẫn chấm toàn bộ tập positive của query.

| Nhóm | Skills trong corpus | Query cùng major | TF-IDF Complete@10 |
|---|---:|---:|---:|
| Software Engineering | 3.723 | 2.134 | 70,01% |
| AI Agents | 666 | 257 | 58,37% |
| Business & Planning | 584 | 235 | 80,00% |
| Content Creation | 434 | 148 | 86,49% |
| Data & ML | 407 | 163 | 91,41% |
| Information Retrieval | 192 | 85 | 68,24% |
| Liên nhóm major | Không phải nhóm corpus riêng | 1.370 | 37,30% |

Không diễn giải bảng thành “Data & ML dễ hơn AI Agents” một cách tổng quát: các hàng khác số mẫu và tỷ lệ task một/nhiều positive. Khi giữ cùng **hai positive/query**, TF-IDF Complete@10 là **48,70%** cho nhóm cùng major (731 query), và **43,72%** cho nhóm liên major (972 query). Chênh lệch vẫn xuất hiện nhưng chưa có kiểm định thống kê hay thí nghiệm để xác định nguyên nhân.

Hướng dùng kết quả này là **chọn mẫu gán nhãn cân bằng theo số positive và nhóm chức năng**, không chỉ lấy các task dễ hoặc nhóm Software Engineering đông nhất.

Nguồn: [skill-groups.csv](../../artifacts/offline-analysis-20261023/skill-groups.csv), [groups.json — exclusive_major](../../artifacts/offline-analysis-20261023/groups.json), [positive-count-controlled.json](../../artifacts/offline-analysis-20261023/positive-count-controlled.json).

## 4. Ba ví dụ thật giúp nhìn rõ lỗi

Các ví dụ được chọn để minh họa kiểu lỗi, **không phải mẫu đại diện để ước lượng tỷ lệ lỗi**. Query gốc, positive IDs, descriptions và top-10 của từng phương pháp nằm trong [cases.json](../../artifacts/offline-analysis-20261023/cases.json). “Không thấy” dưới đây có nghĩa không nằm trong top-15 đã lưu, không có nghĩa không tồn tại trong corpus.

### Ví dụ A — Audit đúng chủ đề nhưng chưa bao phủ đủ phần việc (`q-00019`)

**Task:** audit một dashboard React, tạo issues, sửa component UI ưu tiên cao và mở PR.

Gold skills gồm `quality-audit-workflow`, `ui-designer`, `GitHub Pull Requests`.

| Gold skill | TF-IDF rank | BM25 rank | MiniLM rank |
|---|---:|---:|---:|
| quality-audit-workflow | 1 | 10 | 1 |
| ui-designer | 14 | 1 | Không thấy |
| GitHub Pull Requests | Không thấy | Không thấy | Không thấy |

TF-IDF đứng đầu đúng skill audit, nhưng top-10 còn nhiều skill review/frontend gần chủ đề. Điều này gợi ý kiểm tra **bao phủ các phần việc** thay vì chỉ lấy nhiều tài liệu giống câu query tổng thể. Tuy nhiên, chỉ chia task thành các bước chưa bảo đảm cải thiện; cần một ablation để kiểm tra.

**Một vấn đề nhãn đáng chú ý:** description của `quality-audit-workflow` đã nhắc tới audit, tạo issues và tạo PR. Vì vậy, ba positive IDs **chưa chứng minh cả ba đều bắt buộc hoặc tạo thành tập tối thiểu**. Đây là lý do cần nhãn *required / optional / alternative* hoặc tập skill đủ chức năng, thay vì mặc định mọi cặp co-positive là dependency. Khả năng thực hiện đầy đủ bằng một skill đó chưa được kiểm chứng qua agent.

### Ví dụ B — Embedding có ích ở một số query dù điểm trung bình thấp hơn (`q-00032`)

**Task:** thiết lập workspace Deepnote, notebook cho ETL/Superset, cấu hình dùng chung và security hooks.

Hai gold skills là `insightpulse-deepnote-data-lab` và `shared-setup-patterns`.

- TF-IDF xếp chúng ở **1 và 11**: top-10 chưa đủ, top-15 đã đủ.
- MiniLM xếp ở **1 và 8**: đủ ngay trong top-10.
- BM25 lấy skill data lab ở rank 1 nhưng chưa lấy được skill setup trong top-15.

Trong toàn bộ test split có **149 query** MiniLM lấy đủ positive trong top-10 trong khi TF-IDF chưa đủ; chiều ngược lại là **986 query**. Điểm trung bình cao nhất không có nghĩa thắng ở mọi task. Điều này tạo cơ sở để thử hybrid/candidate fusion, nhưng **chưa phải kết quả chứng minh hybrid hiệu quả**.

### Ví dụ C — Chi tiết công nghệ có thể lấn át mục tiêu thực sự (`q-00072`)

**Task:** cấu hình coding assistant để các lần tương tác sau phản ánh sở thích và môi trường của người dùng; query liệt kê Kotlin, Rust, Git, Buildkite và quy ước làm việc.

Positive được gán là `personalize-skills`, nhưng cả BM25, TF-IDF và MiniLM đều không đưa ID này vào top-15. TF-IDF đưa lên đầu các skill như `test-optimization`, `prepare-changelog`, `git-commit` và Buildkite.

Một giả thuyết từ ví dụ này là mô hình đang khớp các chi tiết môi trường hơn mục tiêu “cá nhân hóa assistant”. Cần kiểm tra biểu diễn **mục tiêu chính + ràng buộc + các phần việc**, không kết luận ngay rằng một thuật toán cụ thể không hiểu ý định. Query này dài 236 MiniLM tokens, nên lỗi này cũng không thể được giải thích chỉ bằng việc query vượt 256 tokens.

## 5. Giới hạn biểu diễn ảnh hưởng cách đọc kết quả MiniLM

Đếm trên đúng `SkillRecord.text()` và query đầu vào bằng tokenizer của revision MiniLM đã chạy, gồm special tokens, chưa truncation:

- **5.898/6.006 skill documents (98,2%)** dài hơn 256 tokens; median **1.906 tokens**.
- **2.251/4.392 queries (51,3%)** dài hơn 256 tokens; median **260 tokens**.
- Model baseline đang dùng giới hạn 256 tokens cho cả hai phía.

Vì vậy, kết quả MiniLM phản ánh một **dense baseline context ngắn**, không phải so sánh mọi embedding model với TF-IDF trên toàn văn không bị cắt.

MiniLM Complete@10 là **51,61%** ở nhóm query không quá 256 tokens và **32,70%** ở nhóm dài hơn. Tuy nhiên TF-IDF cũng giảm ở nhóm dài, từ **65,76% xuống 56,42%** dù không có giới hạn đó. Task dài có thể đồng thời phức tạp và nhiều positive hơn. **Đây là tương quan, chưa phải bằng chứng truncation gây ra toàn bộ chênh lệch.**

Phép thử tiếp theo phù hợp là so sánh các biểu diễn `name + description`, toàn văn và chunk/summary trên cùng model/protocol hoặc model context dài hơn. Không chọn cấu hình tối ưu bằng chính test labels hiện tại.

Nguồn: [query-features.csv](../../artifacts/offline-analysis-20261023/query-features.csv), [summary.json — token lengths](../../artifacts/offline-analysis-20261023/summary.json), [model provenance](../../artifacts/poc-b-20261023-extra/model-provenance.json).

## 6. Tăng k có giải quyết được không?

Tính các cutoff nhỏ hơn từ ranking TF-IDF đã lưu, không chạy lại selector:

| k | Recall@k | Completeness@k |
|---|---:|---:|
| 1 | 44,71% | 28,14% |
| 3 | 61,64% | 45,22% |
| 5 | 67,82% | 52,60% |
| 10 | 74,80% | 60,97% |
| 15 | 77,79% | 64,85% |

Tăng từ 10 lên 15 lấy đủ thêm khoảng **3,87 điểm phần trăm query**, nhưng vẫn còn **35,15% query** chưa đủ positive. Ngược lại, cố định k=15 luôn cấp 15 ứng viên trong khi nhãn mỗi query chỉ có 1–3 positive.

Đây là động lực đánh giá **độ đầy đủ so với ngân sách skill**, rồi nghiên cứu dynamic-k. Không thể suy ra “mọi skill ngoài qrels đều thừa”: một skill chưa được gán positive vẫn có thể hữu ích hoặc thay thế được skill khác.

Kho còn có **153 nhóm trùng tên, gồm 358 skill IDs**. Trùng tên chưa chứng minh nội dung tương đương, nhưng cần rà soát khi gán nhãn và diễn giải việc ranking chọn đúng một phiên bản còn qrels chỉ đánh dấu phiên bản khác. Các artifact hiện chấm exact ID.

Nguồn: [tfidf-budget.csv](../../artifacts/offline-analysis-20261023/tfidf-budget.csv), [duplicate-names.json](../../artifacts/offline-analysis-20261023/duplicate-names.json).

## 7. Hướng nghiên cứu được rút ra

| Quan sát | Hạn chế cần kiểm tra | Thực nghiệm/đầu ra tiếp theo |
|---|---|---|
| Multi-skill Complete@10 giảm mạnh | Ranking giống chủ đề chưa chắc bao phủ đủ mọi phần việc | Annotate mục tiêu/phần việc; thử full-query vs subtask retrieval và role coverage |
| Một số task không có positive nào trong top-10 | Candidate retrieval/biểu diễn task chưa đủ | Phân tích top-100 candidate recall và lỗi entity-vs-goal trước khi thêm logic chọn tập |
| MiniLM thắng ở 149 query, thua ở nhiều query khác | Điểm trung bình che khả năng bổ sung giữa phương pháp | Hybrid cố định cấu hình, đánh giá theo nhóm task; không khẳng định trước sẽ tốt hơn |
| Phần lớn văn bản vượt context MiniLM | So sánh embedding bị giới hạn bởi biểu diễn/context | Ablation field/chunk/summary/context, giữ model/protocol rõ ràng |
| Workflow skill có thể bao phủ nhiều thao tác; qrels chưa ghi quan hệ | Co-relevance chưa phải dependency và tập positive chưa chắc tối thiểu | Guideline required/optional/alternative, dependency/conflict có bằng chứng; tập task mẫu rà soát thủ công |
| k lớn tăng completeness nhưng chưa lấy đủ hết | Cần cân bằng coverage với số tài nguyên cấp | Đường cong coverage–budget và dynamic-k; sau đó mới đo context tokens, cost, task success |

Ưu tiên gần nhất: **phân tích và gán nhãn một tập task multi-skill nhỏ, định nghĩa “tập skill đủ cho task”, rồi kiểm tra selection theo phần việc và budget**. Chưa cần coi graph là lời giải bắt buộc; quan hệ graph chỉ có ý nghĩa khi có định nghĩa nhãn và phép thử phân biệt được đóng góp của nó.

Mọi nhận xét trên là phân tích mô tả/hypothesis generation trên test split đã xem kết quả. Cần giữ tập phát triển/test độc lập hoặc một tập task mới cho bước chọn cấu hình và kiểm chứng giả thuyết. Chưa chứng minh causal effect, ý nghĩa thống kê hoặc cải thiện agent task success.

## 8. Bổ sung phân loại theo kỹ năng thao tác

Phân loại major/domain trả lời “task thuộc lĩnh vực gì”; phân loại `primary_action` trả lời gần hơn “skill chủ yếu làm việc gì”. [Báo cáo chính](../reports/GR2_Progress_2026-10-23.md) trình bày bản rút gọn các nhóm kỹ năng và task minh họa, giải thích MiniLM và giới hạn nhãn. Artifact bên dưới giữ thống kê đủ 13 actions và các ví dụ chi tiết.

- Debug: 178 skills, trong đó 164 thuộc Software Engineering; test: 273/248; analyze: 752/339; review: 359/295; search: 242/54.
- Không gộp tất cả analyze thành đọc hiểu code; search có cả tìm thông tin bên ngoài. Một workflow skill cũng có thể bao phủ nhiều thao tác dù chỉ mang một primary action.
- Ví dụ `q-00011`: debug Smalltalk + tạo AGENTS.md; `q-00035`: hiểu kiến trúc Go gRPC + viết API reference; `q-00080`: tra code nguồn IntelliJ; `q-00034`: đổi UI có ràng buộc giữ nguyên logic; `q-00323`: lập kế hoạch + deploy.
- Nhóm query theo action là “có ít nhất một gold skill mang action đó”, các nhóm chồng lặp. Artifact tách metric lấy đủ mọi positive của task (`complete10`) và recall chỉ trên gold skills của action đó (`action_gold_recall10`); không dùng hai đại lượng thay cho nhau.
- Trường raw `generator_model` bằng `Claude Opus 4.6` cho mọi query. Cần rà soát tính đại diện của các yêu cầu hỗn hợp và tài nguyên đính kèm trước khi coi chúng là task execution benchmark.

[action-profile.json](../../artifacts/offline-analysis-20261023/action-profile.json) lưu thống kê và task nguyên văn cùng ranks top-10; [action_profile.py](../../artifacts/offline-analysis-20261023/action_profile.py) đọc metadata/ranking đã có, exit 0, không inference hoặc thay nhãn. Phần bổ sung có kiểm tra tổng số skill/action, số skill Software Engineering và miền giá trị metric riêng; không cộng vào 20 kiểm tra của đợt phân tích trước.

## Artifact và tái lập phân tích

- [Script phân tích](../../artifacts/offline-analysis-20261023/analyze.py).
- [Summary](../../artifacts/offline-analysis-20261023/summary.json), [Group metrics](../../artifacts/offline-analysis-20261023/groups.json), [CSV](../../artifacts/offline-analysis-20261023/group-metrics.csv).
- [Ví dụ query/skill/rank](../../artifacts/offline-analysis-20261023/cases.json).
- [Input hashes và cách đếm tokens](../../artifacts/offline-analysis-20261023/provenance.json).
- [Kiểm tra nhất quán](../../artifacts/offline-analysis-20261023/validation.json).

Script chỉ đọc các baseline artifacts đã có. Nó bảo vệ kết quả đã hoàn thành bằng cách từ chối ghi đè `summary.json`; dùng một thư mục phân tích mới nếu muốn thực hiện đợt khác.
