# Kho skill và hợp đồng dữ liệu GR2

Ngày bắt đầu: 22/10/2026. Đây là phần nền tảng của demo; chưa có selector mới, adapter agent hay verifier thực thi.

## Đọc ở đâu trước?

- [Kế hoạch triển khai và danh sách file](implementation-plan.md).
- [Ánh xạ Google Sheets sang JSON Schema](schema-mapping.md).
- `config/registry/schema-source.snapshot.json`: bản đọc nguồn A1:N100 của 7 tab Sheets ngày 22/10/2026.
- `config/registry/sources.yaml`: nguồn, chính sách nhập và shortlist cần duyệt.
- `config/registry/sources.lock.json`: commit/hash và đường dẫn inventory của lần nhập thành công gần nhất.
- `src/skill_selection/registry/schemas/v1/`: 7 contract và định nghĩa con dùng chung.
- `examples/registry/`: dữ liệu giả để minh họa cấu trúc, không phải kết quả chạy thật.

## Cài và tải lại

Chạy PowerShell tại thư mục gốc repo, dùng Python của dự án:

```powershell
.\.venv\Scripts\python.exe -m pip install -e '.[dev,registry]'
.\.venv\Scripts\python.exe scripts/sync_skill_sources.py --source obra-superpowers
.\.venv\Scripts\python.exe scripts/sync_skill_sources.py --source anthropics-skills
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_registry.py
```

Chạy các lệnh nhập tuần tự. Lần đầu chưa có lock thì resolve `main` thành commit đầy đủ. Khi có lock, lệnh mặc định
dùng lại commit đó, xác minh cache rồi nhập lại; không tự trôi theo nhánh. Chỉ dùng `--update` khi muốn chủ động
nhập bản upstream mới. Lock chỉ cập nhật sau khi nhập thành công; revision và inventory cũ được giữ lại.

Công cụ có `config/registry/sync.lock` để tránh hai tiến trình ghi đè lock của nhau. Khi tiến trình bị kill/crash,
chỉ xóa guard còn sót sau khi xác nhận không còn lần sync nào đang chạy; không xóa `sources.lock.json`.

`sync_skill_sources.py` dùng GitHub API và codeload qua HTTPS, có timeout và giới hạn dung lượng. Không yêu cầu
token GitHub cho kho public; lỗi mạng/rate limit phải được giải quyết trước khi tải lại, không biến thành kho rỗng.
Không chạy installer, hook, script hoặc plugin upstream; không ghi vào thư viện skill cá nhân của Codex/Claude.

## Lưu trữ

```text
config/registry/                         # commit Git: nguồn, lock, bản đọc schema nguồn
src/skill_selection/registry/schemas/v1/ # commit Git: contract máy đọc
examples/registry/                       # commit Git: ví dụ tổng hợp
data/raw/skill_sources/
  <source_id>/<commit>/
    SOURCE.json                         # URL, commit, archive hash, hash cây file
    repository/                         # nội dung gốc, gồm license/notices
data/processed/registry/
  packages/<source_id>/<skill-path>/<revision-hex>/
    SKILL.md                            # nguyên bản, không chỉnh trực tiếp
    scripts/, references/, assets/, ... # giữ mọi file trong gói nếu có
  imports/<source_id>/<commit>/<import-hash>/
    profiles.jsonl                      # envelope: profile_revision_id, package_ref, profile
    rejections.jsonl                    # gói không parse/validate được và lý do
```

`data/raw/` và `data/processed/` đã được Git bỏ qua; tái tải theo lock hoặc đóng gói riêng để giao nộp.
Tài liệu và nhật ký mới trong `docs/registry/`, `docs/worklog/2026-10-22.md` được mở theo dõi riêng;
các tài liệu riêng tư cũ trong `docs/` tiếp tục bị bỏ qua.

Gói được hash theo danh sách file có đường dẫn POSIX tương đối, sắp xếp phân biệt hoa/thường, SHA-256 từng file
và số byte. `revision_id = sha256(canonical_json(resources))`; JSON chuẩn hóa UTF-8, sort_keys, compact separators,
ensure_ascii=False, không NaN. `profile_revision_id` hash toàn bộ profile, tách khỏi revision nội dung gói.
`import_id` hash profiles và rejections; cùng nguồn với cùng importer cho cùng inventory.

Không ghi manifest vào trong gói đã hash. Metadata đặt cạnh gói hoặc trong inventory. Gói đã tồn tại được xác minh
thay vì ghi đè. Bản gốc không bị sửa để phù hợp harness; nếu cần sửa, tạo nguồn dẫn xuất có provenance riêng.

## Duyệt trước khi chọn

Nhập tự động chỉ tạo `needs_review`, license `null`, taxonomy/requirements chưa được xác nhận; không tạo snapshot
`ready`. Dữ liệu gói hợp lệ về cấu trúc chưa đồng nghĩa phù hợp task, có đủ tool hoặc được phép thực thi.

1. Đọc license ở gói và cấp repo, giữ notice và ghi bằng chứng. Anthropic có cả gói Apache-2.0 lẫn gói source-available;
   không áp một license chung cho toàn bộ kho.
2. Rà soát hướng dẫn, file được tham chiếu ngoài gói, quyền, runtime, tên tool và giả định harness.
3. Gán `task_types`, `capabilities`, applicability và requirements với provenance.
4. Trích quan hệ dưới dạng `proposed`; người duyệt xác nhận trước khi dùng làm ràng buộc hard.
5. Tạo profile revision mới, đóng snapshot chỉ chứa revision được duyệt; rồi mới đưa vào selector.

Các bước duyệt/đóng snapshot và giao diện nối retrieval là phần tiếp theo, chưa được script này thực hiện.

## Nguồn

- [obra/superpowers](https://github.com/obra/superpowers): nguồn workflow phát triển phần mềm; repo công bố MIT.
- [anthropics/skills](https://github.com/anthropics/skills): nguồn gói có scripts/references/assets; license cần kiểm theo gói.
- [SWE-Skills-Bench](https://arxiv.org/abs/2603.15401): nguồn benchmark và phương pháp đánh giá. Liên kết tác giả
  [GeniusHTX/SWE-Skills-Bench](https://github.com/GeniusHTX/SWE-Skills-Bench) trả 404 khi kiểm tra ngày 22/10/2026.
  Chưa tải skill từ nguồn này; không suy kho kỹ năng từ nội dung bài báo hay thay bằng repo không xác minh.
- [Bảng thiết kế được cung cấp](https://docs.google.com/spreadsheets/d/1tzEWjN_VH00tNJHIX0SF4zYMeRgEMrC6WE2OwUfGOcw/edit).
