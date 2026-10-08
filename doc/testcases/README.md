# Testcase và so sánh baseline

| Tệp | Nội dung |
|---|---|
| `GR2_testcases_baselines.xlsx` | Workbook báo cáo: baseline (đầu vào, đầu ra, điều kiện chấp nhận), so sánh trên GR1 và SkillRet, danh mục testcase có đầu ra thực tế |
| `catalog.yaml` | Nội dung danh mục testcase (mã, loại, đầu vào, đầu ra mong muốn, trạng thái trung gian, nguồn bằng chứng) |

Cột "Đầu ra thực tế" và "Kết quả" trong workbook được điền tự động từ bằng chứng máy ghi (kết quả pytest, kiểm tra trên đầu ra thật của từng baseline, kết quả cổng kiểm định), không gõ tay.

Sinh lại (Windows cmd, trong thư mục repo, `.venv` đã kích hoạt):

```bat
python -m skill_selection compare gr1
python scripts\collect_skillret_reference.py
python scripts\build_testcase_workbook.py
```

Baseline so sánh: BM25 và Qwen3-Embedding (SkillRet), SkillRet-Embedding tinh chỉnh (SkillRet), SkillRouter (truy hồi + xếp hạng lại), Graph of Skills (bản rút gọn không dùng LLM), SkillReranker (lõi đồ thị trạng thái, bộ phân rã heuristic), cùng cách chọn của GR1 và phương pháp đề xuất M5.
