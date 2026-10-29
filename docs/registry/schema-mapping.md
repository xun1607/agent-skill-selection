# Ánh xạ schema nguồn vào repo

Nguồn: [GR2_interface_schemas_and_data_flow](https://docs.google.com/spreadsheets/d/1tzEWjN_VH00tNJHIX0SF4zYMeRgEMrC6WE2OwUfGOcw/edit).
Đã đọc metadata và A1:N100 trên toàn bộ 7 tab ngày 22/10/2026; bảng nguồn không bị sửa.
Bản đọc nguyên giá trị và sheet ID: `config/registry/schema-source.snapshot.json`.

## File hợp đồng

| Tab Sheets | File tại `src/skill_selection/registry/schemas/v1/` | Vai trò |
|---|---|---|
| SkillProfile | `skill-profile.schema.json` | Hồ sơ chuẩn hóa của một revision gói |
| SkillRelation | `skill-relation.schema.json` | Quan hệ giữa hai revision, có bằng chứng và trạng thái duyệt |
| TaskRequest | `task-request.schema.json` | Đầu vào selector, tách khỏi dữ liệu đánh giá |
| RegistrySnapshot | `registry-snapshot.schema.json` | Danh sách revision profile/skill/relation bất biến |
| SelectionDecision | `selection-decision.schema.json` | selected/no_skill/error và liên kết request/snapshot/policy |
| Verifier, các dòng SPEC | `verifier-spec.schema.json` | Cấu hình bộ chấm, chỉ runner đọc |
| Verifier, các dòng RESULT | `verifier-result.schema.json` | Kết quả sau run; tách lỗi hạ tầng khỏi task fail |
| Luồng trao đổi | Tài liệu luồng, không tạo schema thông điệp thứ tám | Phân quyền dữ liệu và selected/loaded/used |
| Các cấu trúc dùng chung | `common.schema.json` | Condition, requirement, resource, evidence, usage, revision ref |

Giữ tên trường, enum và required/optional ở cấp trường như Sheets; `[]` là ký hiệu phần tử mảng trong bảng,
không phải một phần tên khóa JSON. Dùng `load_estimate` đúng tên bảng, không dùng tên cũ `token_estimate`.
`load_estimate` và `budgets.selector_latency_ms` là tùy chọn; các trường bắt buộc kiểu nullable vẫn phải hiện diện.
`profile_revision_id` nằm trong tham chiếu snapshot/envelope, không thêm vào nội dung SkillProfile nguồn.

## Những chi tiết là đề xuất triển khai, chưa phải thiết kế đã chốt trên Sheets

Bảng mô tả một số trường là object/condition/evidence mà chưa liệt kê toàn bộ trường con. Định nghĩa hiện tại
là bản cụ thể hóa v1.0 để bắt đầu code; cần rà soát trước khi khóa giao diện cho agent:

- Condition: `key`, `op`, `value`, `enforcement`, `evidence`, `verification_status`.
- Requirement: `kind`, `name`, `value`, `enforcement`, `verification_status`, `evidence`.
- Resource: `path`, `sha256`, `size_bytes`; bao gồm mọi file trong gói.
- Evidence: `file`, `start_line`, `end_line`, `content_hash`, `truncated`, `text`.
- Repo ref: `url`, `commit`, `snapshot_id`; ít nhất commit hoặc snapshot_id phải được ghim.
- Load estimate: `tokens`, `tokenizer`, `tokenizer_version`, `scope`; chưa có profiler, dùng null.
- Usage: `elapsed_ms`, `input_tokens`, `output_tokens`, `cost_usd`; chưa đo được thì null, không ghi 0 giả.
- Selected item: `skill_id`, `revision_id`, `position`; position bắt đầu 0 và liên tiếp.
- Error: `code`, `message`; check của verifier: `check_id`, `status`, `message` tùy chọn.
- `repo_metadata`, `context_limits`, `provenance` giữ object mở vì taxonomy/context extractor chưa chốt.
  Caller phải giới hạn nội dung; JSON Schema chưa thể phát hiện đáp án bị giấu trong văn bản/metadata.

Các datetime lưu RFC3339 UTC với hậu tố Z. Hash dùng `sha256:` và 64 ký tự hex. Các schema có `$id` dưới
`https://gr2.local/schemas/v1/` chỉ để định danh nội bộ; validator resolve từ file đóng gói, không truy cập mạng.
Tên schema `v1.0` được giữ theo bảng; mức hoàn thiện hiện tại vẫn là bản nháp triển khai.

## Kiểm tra đã có và chưa có

`contracts.validate_record()` kiểm shape, enum, required, date/time, hash, path; kiểm tra no_skill khác error,
selected phải có revision và vị trí duy nhất, repo có định danh ghim, profile valid không còn issue/license null.
TaskRequest cấm trường top-level ngoài contract, gồm gold_patch/hidden_tests.

Chưa có kiểm tra chéo request ↔ decision ↔ snapshot, điều kiện satisfied/violated/unknown, đóng requires,
đối xứng conflicts_with, budget sau đóng phụ thuộc, hash nội dung snapshot, hoặc môi trường verifier thực tế.
Đây là trách nhiệm của registry/selector/runner tiếp theo, không thể suy là đã chạy chỉ vì JSON hợp schema.

`examples/registry/` là fixture tổng hợp với hash minh họa; không phải snapshot thực, patch, hay bằng chứng agent
đã sửa lỗi. Ví dụ snapshot rỗng minh họa nhánh NO_MATCH; chưa có snapshot ready từ skill upstream.

Không sửa `src/skill_selection/schemas.py` trong bước này để tránh phá các baseline đã có. Lớp chuyển đổi
SkillProfile → SkillRecord sẽ dùng body từ đúng package revision, giữ nguyên namespace và provenance.
