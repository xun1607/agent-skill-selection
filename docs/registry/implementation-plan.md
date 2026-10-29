# Kế hoạch bổ sung kho skill vào demo 8 giờ

Ngày: 22/10/2026. Phạm vi hiện tại: tạo nền tảng dữ liệu và nhập nguồn. Chưa triển khai toàn bộ demo agent.

## Thứ tự tạo file và tiêu chí hoàn thành

| Bước | File/thư mục | Trạng thái và điều kiện qua bước |
|---|---|---|
| 1 | `config/registry/schema-source.snapshot.json` | Đã tạo: giữ bản đọc Sheets để đối chiếu thay đổi |
| 2 | `src/skill_selection/registry/schemas/v1/*.schema.json` | Đã tạo: 7 thông điệp và common; có ví dụ validate được |
| 3 | `examples/registry/*.json`, `registry/contracts.py` | Đã tạo: ví dụ và validator offline, phân biệt no-skill/error |
| 4 | `config/registry/sources.yaml`, `sources.lock.json` | Đã tạo: khai báo nguồn, commit và hash lần nhập thật |
| 5 | `registry/packages.py`, `scripts/sync_skill_sources.py` | Đã tạo: tải archive ghim commit, hash gói, giữ resource, inventory/rejections |
| 6 | `tests/unit/test_registry.py` | Đã tạo: contract, status, budget âm, sửa resource, gói bất biến, archive path |
| 7 | `config/registry/reviews/<source>/<skill>.yaml` | Tiếp theo: nguồn bằng chứng license, taxonomy, tool/runtime/quyền; không sửa gói gốc |
| 8 | `registry/review.py`, `registry/snapshots.py` | Tiếp theo: áp review overlay, tạo profile revision, kiểm tham chiếu, đóng snapshot ready |
| 9 | `registry/bridge.py` | Tiếp theo: chuyển profile được duyệt sang SkillRecord cho retrieval hiện có |
| 10 | `selection/policy.py`, `selection/rule_selector.py` | Tiếp theo: điều kiện, budget, selected/no_skill/error; kiểm quan hệ hard |
| 11 | `adapters/mini_swe.py`, `execution/runner.py`, `execution/verifier.py` | Tiếp theo: context nạp thật, run ID, trajectory, verifier độc lập |
| 12 | `benchmarks/e2e_demo/`, `tests/integration/test_e2e_demo.py` | Tiếp theo: hai task Python và verifier; integration giả + smoke thật |

Đường dẫn module rút gọn trong bảng đều nằm dưới `src/skill_selection/`. Không tạo trước các file Python rỗng
cho phần chưa triển khai, để tránh làm người đọc hiểu nhầm đã có chức năng.

## Tải và cập nhật các nguồn

Tải archive hai kho public vào vùng raw theo commit, giữ đầy đủ gói và license/notices; không cài plugin hay dùng
workflow tự bootstrap từ upstream. Nhập tất cả gói vào inventory để khảo sát; chỉ duyệt 2–3 gói cho demo đầu.
Không đồng nhất "đã tải", "đã parse", "đã duyệt" và "đã nạp vào agent".

Shortlist ban đầu là systematic-debugging, test-driven-development, verification-before-completion từ Superpowers;
webapp-testing/mcp-builder của Anthropic để khảo sát yêu cầu harness hoặc làm distractor khi phù hợp.
Shortlist là đề xuất cần đọc lại, không phải quyết định selected. Skill dùng browser hoặc MCP không tự phù hợp với
hai task pytest chỉ vì cùng thuộc nhóm development.

SWE-Skills-Bench hiện là paper_reference bị chặn do liên kết repo chính thức trả 404. Khi nguồn truy cập được:
xác nhận commit, vị trí gói, license từng gói và nguồn task; cập nhật source config rồi bổ sung importer riêng.
Không nhập requirement, verifier, gold patch vào profile/retrieval. Dữ liệu benchmark đặt `benchmarks/` hoặc
vùng evaluation riêng; chỉ runner/evaluator đọc nhãn và verifier ẩn.

## Quy tắc lưu và cập nhật

- Raw: `data/raw/skill_sources/<source>/<commit>/`, nguyên bản. Không sửa skill gốc tại đây.
- Gói: `data/processed/registry/packages/.../<revision>/`, giữ tất cả resource của skill; revision thay khi file thay.
- Hồ sơ: inventory JSONL có profile hash; review tạo hồ sơ mới, không thay lịch sử import.
- Quan hệ: lưu JSONL có typed relation và bằng chứng; chỉ confirmed mới ép/chặn.
- Snapshot: bước sau lưu `data/processed/registry/snapshots/<snapshot-id>/`; list revision skill/profile/relation
  và manifest chuẩn hóa. Chỉ snapshot ready được selector đọc; invalid/needs_review bị loại kèm lý do.
- Run: bước sau lưu `artifacts/e2e/<run-id>/` với request/decision/load-manifest/trajectory/patch/verifier/report.
  VerifierSpec và test ẩn đặt ngoài workspace agent. Secret không đưa vào record/log.
- Commit Git: code/schema/config/lock/examples/docs mới. Raw, packages và run lớn không commit; tái tải hoặc
  đóng gói riêng theo license khi nộp. Lock được cập nhật có chủ ý bằng `--update`.

## Ảnh hưởng tới giới hạn 8 giờ

Nếu bắt đầu từ repo cũ và đồng thời phải cụ thể hóa toàn bộ schema, nhập nhiều nguồn, duyệt license/harness,
làm selector và agent/verifier thật, 8 giờ trở nên rủi ro hơn ước lượng demo trước đó. Tách nền tảng đã tạo ở lượt này
khỏi phần E2E còn lại khi tính thời gian. Không tính tải toàn bộ kho là đã hoàn thành review.

Trong ca 8 giờ tiếp theo: dành tối đa 1 giờ chọn 2–3 gói và khóa schema con cần dùng; kiểm agent/model thật ngay
đầu ca; ưu tiên hai task pytest và hai nhánh selected/no_skill. Không thêm crawler, DB graph, UI, benchmark lớn,
Codex/Claude adapter hay đo cải thiện pass rate. Các chi tiết nested schema chưa chốt ghi rõ trong báo cáo.

## Giao nộp

1. Commit mã nền tảng và tài liệu; không đưa workbook đang sửa dở vào commit chung.
2. Lock nguồn và báo cáo nhập: số gói, rejected, needs_review, số valid, lý do benchmark bị chặn.
3. Khi xong E2E: hướng dẫn một lệnh chạy hai ca, report thực nghiệm ngắn và gói bằng chứng theo run ID.
4. Log ở `docs/worklog/2026-10-22.md`, ghi rõ việc đã làm, kiểm thử thực chạy và việc còn thiếu.
