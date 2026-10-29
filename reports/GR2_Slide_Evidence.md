# Mapping bằng chứng — GR2 Progress 23/10/2026

Phạm vi: chỉ dùng code và artifact hiện có; không chạy lại agent/benchmark khi tạo slide. Slide 6 là kế hoạch. Hai nhánh PoC không được gộp thành bằng chứng về skill benefit.

| Slide | Số liệu / kết luận | Nguồn cụ thể | Trạng thái và giới hạn |
|---|---|---|---|
| 1 | Skill là package hướng dẫn + resources; mục tiêu task-aware/relations/no-skill | src/skill_selection/registry/packages.py (`file_manifest`, `profile_package`); src/skill_selection/schemas.py | Định nghĩa theo code; relations và no-skill correctness là mục tiêu nghiên cứu, chưa VERIFIED |
| 2 | QueryRecord, SkillRecord, SelectionResult; fit/select | src/skill_selection/schemas.py; src/skill_selection/selectors/base.py | Có code; Task của PoC được chuyển thành QueryRecord, không tuyên bố có Task class riêng |
| 2 | Registry/Loader, adapter mini/Codex và offline modules | src/skill_selection/registry/packages.py; scripts/agent_skill_poc.py; scripts/run_mini_skill_poc.py; src/skill_selection/experiments/runner.py; src/skill_selection/evaluation/metrics.py; src/skill_selection/reporting/markdown.py | Registry là package utilities/contracts, chưa phải production service; sơ đồ là module contracts, không execution flow |
| 3 | 51 pytest cases pass | artifacts/poc-a-tests-final.xml (`tests=51, failures=0, errors=0`); artifacts/poc-a-tests-final.log | VERIFIED artifact lưu sẵn; 26 PoC + 6 selector + 19 registry, không phải 51 live runs |
| 3 | 4 decisions []/[A]/[B]/[A,B] | tests/unit/test_agent_skill_poc.py (`CASES`, parametrized adapter tests); src/skill_selection/selectors/mock_selector.py | VERIFIED không LLM; A=systematic-debugging, B=verification-before-completion |
| 3 | decision skill_ids đúng B | artifacts/poc-a-live/20261022T175004388037Z-mini-pre/decision.json (`result.skill_ids[0]`) | VERIFIED; dòng JSON trên slide lấy nguyên giá trị từ file này |
| 3 | selected → provided → read_observed | artifacts/poc-a-live/20261022T175004388037Z-mini-pre/exposure.jsonl (dòng 1,2,6); artifacts/poc-a-live/20261022T175004388037Z-mini-pre/trajectory.json (`messages[2].extra.actions[1]`, `messages[4].extra`) | VERIFIED live mini. Trên slide command là phần sau cd &&, output là heading trích; không phải trace giả. returncode=0, full document đối chiếu bằng observe_read |
| 3 | Mini execution có trajectory và verifier | artifacts/poc-a-live/20261022T175004388037Z-mini-pre/agent-status.json; artifacts/poc-a-live/20261022T175004388037Z-mini-pre/verifier-result.json; artifacts/poc-a-live/20261022T175245063986Z-mini-pre/summary.json | Selected task 9/19, no-skill 14/19; đọc file không chứng minh áp dụng hay hiệu quả |
| 3 | Codex live read NOT_VERIFIED | [object Object]/verification.json; artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/events.jsonl (dòng 5,7,9); artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/summary.json | Model turn exit 0; Windows tool executor fail; không có read_observed. Ưu tiên kết quả controlled mới hơn run timeout cũ |
| 4 | 6.006 skills / 4.392 queries / 7.187 qrels | artifacts/poc-b-20261023/dataset-audit.json (`n_skills`, `n_queries`, `n_qrels`); artifacts/poc-b-20261023/provenance.json | VERIFIED; revision 6583d7d2ed07644d0fb8938ed8178f3a7dc42a12, test split, 0 query thiếu positive |
| 4 | Random NDCG@10=0.001181629203102274; Recall@10=0.002011232544019429; Completeness@10=0.0009107468123861566 | artifacts/poc-b-20261023/runs/skillret-6583d7d-test_random_d6955ee161/metrics.json (`mean`) | VERIFIED; bảng làm tròn 9 chữ số thập phân, chart dùng số gốc |
| 4 | BM25 NDCG@10=0.5168592611916537; Recall@10=0.5940725561627201; Completeness@10=0.4455828779599271 | artifacts/poc-b-20261023/runs/skillret-6583d7d-test_bm25_4df95007ee/metrics.json (`mean`) | VERIFIED; tỷ lệ [0,1], không phần trăm. Random rất nhỏ nhưng không bằng 0 |
| 4 | k=15, evaluation 5/10/15; seed Random=0 | artifacts/poc-b-20261023/runs/skillret-6583d7d-test_random_d6955ee161/manifest.json; artifacts/poc-b-20261023/runs/skillret-6583d7d-test_bm25_4df95007ee/manifest.json; src/skill_selection/evaluation/metrics.py | VERIFIED; NDCG linear gain, macro averaging; Completeness=1 khi lấy đủ positive |
| 4 | Ranking/scores/metrics reproduce chính xác | artifacts/poc-b-20261023/validation.json (`comparisons`); artifacts/poc-b-20261023/REPRODUCTION.md | VERIFIED 49 checks; 0 ranking khác, score delta 0, mọi metric delta 0; metrics.json/per_query.csv byte-identical. Không khẳng định historical raw/source byte identity |
| 4 | 12 tests + 49 post-run checks | artifacts/poc-b-20261023/tests.xml; artifacts/poc-b-20261023/validation.json | VERIFIED artifact lưu sẵn; không phải 61 independent experiments |
| 5 | Relevance chưa đo dependency/complementarity/conflict; no-skill benchmark thiếu | src/skill_selection/evaluation/metrics.py (`evaluate`); artifacts/poc-b-20261023/dataset-audit.json | Research gap; evaluator skip query không positive, test split hiện 0 query như vậy |
| 5 | Chưa chứng minh tăng pass rate/giảm cost; task verifier 9/19 và 14/19 | artifacts/poc-a-live/20261022T175004388037Z-mini-pre/verifier.log; artifacts/poc-a-live/20261022T175245063986Z-mini-pre/verifier.log; artifacts/poc-a-live/20261022T175004388037Z-mini-pre/summary.json; artifacts/poc-a-live/20261022T175245063986Z-mini-pre/summary.json | NOT_VERIFIED về hiệu quả; không suy từ 2 runs thành causal comparison |
| 6 | 5 deliverables tuần tới | Kế hoạch đề xuất trong yêu cầu người dùng; dựa trên interface hiện có và các giới hạn ở slide 5 | FUTURE / chưa triển khai. Ghi chú phân bố 2143/1703/546 đã có trong dataset-audit, không giả thành kết quả tương lai |

## Source fingerprints dùng cho deck

Fingerprint xác định file đã dùng lúc build, không thay thế provenance của thực nghiệm.

| Source | SHA-256 |
|---|---|
| `src/skill_selection/schemas.py` | `366a18101d30a39034deed549b47f06208d9e6bce1ad9fe585481fbed033b834` |
| `src/skill_selection/registry/packages.py` | `a3058275e3103e4625e7e7e9e6f5757baeeaef2604987e749b1ab14785eaa3c0` |
| `docs/poc/POC_A_RESULTS.md` | `4c08886d8f11f0023e1b96e4f81c020ea0350d82965b04330c04dcc92cd6a2c4` |
| `docs/poc/POC_B_RESULTS.md` | `1fd45ec8df54efe0d2dce013add6025ff7d8acb90bd3ac3cd89a3051579a7bf5` |
| `src/skill_selection/selectors/base.py` | `ac2f98f47d7a8e553f202f19a146e78ca08368e37136da443a4e97037d035251` |
| `src/skill_selection/selectors/mock_selector.py` | `5b32b712b4678e7e20e803f0bce888d08d82780fdb34ab9a2536f2af5c1722a1` |
| `src/skill_selection/experiments/runner.py` | `27908a9a9ddaa88d59f74e541067726fc330d8aff0b35c0964f6e44bd6d7b7b6` |
| `src/skill_selection/evaluation/metrics.py` | `86db46f4f9cbb7862215ff475a290051c71f459497f3f38ba97b84216324a5b2` |
| `src/skill_selection/reporting/markdown.py` | `313d5bb20190eda44561bbf1808bbacd2bea609936c384a7952b0ce6418a4efe` |
| `scripts/agent_skill_poc.py` | `acffd2bda4e20cbec6779c5cc60e721a8232b91efc42eea98705857473358d29` |
| `scripts/run_mini_skill_poc.py` | `198902ea4f54f48aaccc45fe8febd10bc583ae3385860074cc29474ab9b4c52d` |
| `artifacts/poc-a-tests-final.xml` | `e52644f8760b81dc32cf0a6fd6b4018b2c951688f67b8b3408dad1ec16ebc821` |
| `artifacts/poc-a-live/20261022T175004388037Z-mini-pre/decision.json` | `87cce166de5c2891897e9453c228992e285f63a58a9be1eab35b4435b9f77647` |
| `artifacts/poc-a-live/20261022T175004388037Z-mini-pre/exposure.jsonl` | `af1a106dba6e84997c7ccb2cf5a4d682856c0e2935dac2241ac610cafd6ed295` |
| `artifacts/poc-a-live/20261022T175004388037Z-mini-pre/trajectory.json` | `928c26bf0fe1c3945c2c17041947508e00bd5551af543004afaea326a6530f59` |
| `artifacts/poc-a-live/20261022T175004388037Z-mini-pre/verifier-result.json` | `522a8877a6803719ea00833d6e0803b00228dcc9dda0d3f38865ce9da560dbc3` |
| `artifacts/poc-a-live/20261022T175245063986Z-mini-pre/summary.json` | `009af2ec6a7f8279c7ac332ace96df106d334838bc3054ee9d4796df45369fbc` |
| `artifacts/codex-controlled/20261022T180909990579Z/verification.json` | `ec5077913ff8f24817ff3d2448f19988f66a16c2cacc6e32203a1f0362d28f82` |
| `artifacts/poc-b-20261023/dataset-audit.json` | `6746ef34fbbd83cbdbaed63ef2b58c1b232c426e95becd243264728fc3263f45` |
| `artifacts/poc-b-20261023/runs/skillret-6583d7d-test_random_d6955ee161/metrics.json` | `d09ddf7c4fb2e4edda7a10766c3f393c79b2312867807cb25b8fa15ad111967d` |
| `artifacts/poc-b-20261023/runs/skillret-6583d7d-test_bm25_4df95007ee/metrics.json` | `a365c1ad98fa7c0573deaddf666b7cfccbb2c6f25bf8a80f88680c20f14cce9f` |
| `artifacts/poc-b-20261023/validation.json` | `739eef29d2880daddc94a3cd71c5a367174309c7d7261df2f34816eda9712d6f` |
| `artifacts/poc-b-20261023/provenance.json` | `5b4ddbe63bdd7dbd6d3f47cc8277a3378d09998944318a0b5df6e16bdf1f00ac` |
| `artifacts/poc-b-20261023/tests.xml` | `88bbd6e7de9b78070bf47f00ae5cf1c34a00fe99ed6507084089f47a4e9288ca` |
| `artifacts/poc-a-live/20261022T175004388037Z-mini-pre/summary.json` | `c2ba2d7293d075afc09c3c3836bd14b61f48cd664cdc521e46e805725520fccb` |

## Kiểm tra sử dụng

- Slide count: 6, 16:9. Native chart/table/diagrams có thể chỉnh sửa.
- Trạng thái VERIFIED/NOT_VERIFIED/FUTURE được tách riêng. Không có generated evidence hoặc ảnh terminal giả.
- Speaker notes không được xem là trace; chỉ là lời trình bày dựa trên nguồn trên.
- Khả năng mở và render PowerPoint cùng kiểm tra overflow được lưu trong artifacts/gr2-slide-build; kết luận QA chỉ ghi sau khi thực hiện.

## QA hoàn tất

- Đã mở bằng Microsoft PowerPoint 16.0, render và xem cả 6 slide.
- Bản cuối khớp byte với bản đã render; kiểm tra OOXML pass, không phát hiện tràn chữ theo text bounds và kiểm tra ảnh.
- 1 native chart + 1 native table; chart dùng đúng số gốc và bảng khớp làm tròn 9 chữ số. Có 6 speaker notes tiếng Việt.
- Thời lượng 8 phút 45 giây là ước tính; chưa diễn tập với người trình bày.
