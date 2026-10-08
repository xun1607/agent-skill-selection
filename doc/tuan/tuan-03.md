# Tuần 3 (05/10 – 11/10/2026)

## Chạy được

Giao diện quan sát `streamlit run app/explorer.py`: chọn một nhiệm vụ sửa lỗi thì hiện 3 skill được chọn theo cách của GR1 (lọc ràng buộc môi trường, rồi xếp theo độ tương đồng ngữ nghĩa), kèm bảng xếp hạng đầy đủ và lý do loại.

<!-- Ảnh chụp màn hình: đặt vào doc/tuan/hinh/ và chèn ở đây -->

## Mới so với tuần trước

- Repo `agent_skill_selection` trở thành repo chính, có cả phần xử lý và giao diện; dữ liệu GR1 (41 skill, 6 nhiệm vụ) đưa vào dưới dạng snapshot có kiểm toàn vẹn.
- Mã hoá ngữ nghĩa đa ngôn ngữ chạy trên máy (Qwen3-Embedding-0.6B): mô tả nhiệm vụ tiếng Việt, skill tiếng Anh, không tốn API.
- Kiểm tra khả thi môi trường chạy đầu–cuối (mốc quyết định của tuần 3).

## Số liệu

| Hạng mục | Kết quả |
|---|---|
| Cổng kiểm định 6 nhiệm vụ nội bộ | 6/6 đạt |
| SWE-bench trên máy (flask-4045) | Qua cổng trong 122 giây; image 4.18 GB; giới hạn là RAM 8 GB |
| Tái lập | Hai lần chạy chọn cho tệp kết quả giống hệt từng byte |
| Đối chiếu với GR1 | Cùng vector: thứ hạng trùng toàn bộ 38 vị trí trên cả 6 nhiệm vụ |
| Kiểm thử tự động | 53/53 qua |
| Kịch bản testcase | 79 testcase: 64 đạt, 2 đạt một phần, 0 không đạt, 13 chưa chạy (chạy agent: giữa kỳ) |
| Tiêu chí nghiệm thu tuần (N1–N6) | 6/6 đạt |

## Phát hiện

- Thư viện skill GR1 có 1/41 skill hỏng (một trang HTML tải nhầm, không có mô tả); đã gắn cờ.
- Quan sát ban đầu (6 nhiệm vụ, nhãn còn nháp, chưa phải kết quả đánh giá): skill đọc mã nguồn chung chung luôn bị xếp thấp dù cần cho mọi nhiệm vụ; hai skill trùng chức năng cùng được chọn. Đây là động lực cho chấm điểm theo giai đoạn và tiền điều kiện (RQ1).

## So sánh với các phương pháp đã công bố (09/10)

Chi tiết: `doc/testcases/GR2_testcases_baselines.xlsx`.

| Phương pháp | Nguồn | Recall@5 trên GR1 (nhãn nháp) |
|---|---|---:|
| Ngẫu nhiên | — | 0,100 |
| BM25 | SkillRet | 0,278 |
| Cách chọn GR1 | GR1 | 0,444 |
| Qwen3-Embedding (toàn văn) | SkillRet | 0,500 |
| SkillRet-Embedding (tinh chỉnh) | SkillRet | 0,389 |
| SkillRouter (truy hồi + xếp hạng lại) | SkillRouter | 0,667 |
| Graph of Skills (bản rút gọn) | Graph of Skills | 0,222 |
| SkillReranker (bộ phân rã theo luật) | SkillReranker | 0,500 |

6 nhiệm vụ, nhãn còn nháp: chỉ để thấy xu hướng. Trên kho lớn SkillRet, BM25 của repo khớp đúng số bài báo; các mô hình còn lại sẽ chạy trên GPU.

## Hạn chế

- Embedding OpenAI (bản gốc của GR1) chưa chạy được do tài khoản API hết hạn mức.
- 6 nhiệm vụ và nhãn còn nháp: chưa đủ để kết luận về chất lượng chọn.

## Tuần 4

- Hiện song song nhiều cách chọn (từ khoá BM25, vector nhúng, kết hợp) trên cùng giao diện.
- Chốt phương án chạy đầu–cuối: SWE-bench tập con nhỏ chạy trên máy, HumanEvalFix/QuixBugs làm bộ chính.
