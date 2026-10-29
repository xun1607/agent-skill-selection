# Lời thuyết trình GR2 — 23/10/2026

Đề tài: Task-aware Skill Selector for Coding Agents. 6 slides, thời lượng dự kiến 8 phút 45 giây. Thời lượng là ước tính theo kịch bản, chưa diễn tập với người trình bày. Nội dung này cũng nằm trong speaker notes của PPTX.

## Slide 1 — Bài toán (90 giây)

Kính thưa thầy cô, đề tài GR2 của em là Task-aware Skill Selector for Coding Agents. Trong phạm vi đồ án, skill là một gói hướng dẫn có thể gồm SKILL.md và các tài nguyên hỗ trợ, chẳng hạn quy trình điều tra lỗi hoặc kiểm chứng trước khi kết luận hoàn thành. Skill khác với một tool: tool thực hiện thao tác, còn skill mô tả kiến thức hoặc quy trình để agent vận dụng tool đó.

Khi kho skill mở rộng, bài toán không chỉ là tìm một tài liệu giống câu hỏi nhất. Một task có thể cần nhiều skill; giữa chúng có thể có phụ thuộc, bổ trợ hoặc xung đột. Cũng cần cho phép không cấp skill nếu không có tài nguyên phù hợp. Đây là mục tiêu nghiên cứu của đồ án; phần lựa chọn theo quan hệ và quyết định no-skill chính xác chưa được kiểm chứng trong tuần này.

Tuần này em tập trung vào hai câu hỏi có thể đo được. Thứ nhất, một selector bên ngoài có điều khiển được danh sách tài nguyên đưa cho coding agent trước khi chạy hay không? Thứ hai, pipeline đánh giá offline có tái lập được các baseline trên benchmark cố định hay không? Hai câu hỏi này được kiểm chứng riêng. Integration cho biết kết nối và cấp tài nguyên có hoạt động; offline evaluation đo mức phù hợp của ranking với nhãn benchmark. Chưa dùng hai kết quả đó để kết luận skill làm tăng chất lượng giải task.

## Slide 2 — Kiến trúc (90 giây)

Sơ đồ này mô tả các module và hợp đồng giữa module, không phải thứ tự chạy. Ở trung tâm là Selector Core với interface fit trên catalog và select theo query, k. Hiện có Random, BM25 và MockSelector. MockSelector dùng cho kiểm tra tích hợp; nó trả quyết định đã cấu hình, không phải thuật toán lựa chọn theo task.

Nhóm data schemas dùng QueryRecord, SkillRecord và SelectionResult. Task trong PoC được biểu diễn thành QueryRecord; em không tạo thêm một lớp Task riêng để mô tả phần code chưa tồn tại. Registry và package loader giữ metadata nguồn, revision và hash của tài nguyên. Adapter nhận quyết định để chuẩn bị đầu vào cho mini-SWE-agent hoặc Codex CLI. Registry ở đây là các contract và tiện ích package, chưa phải một dịch vụ quản lý kho hoàn chỉnh.

Ở nhánh thực nghiệm offline, runner gọi cùng interface selector rồi chuyển ranking cho evaluator. Qrels chỉ đi vào evaluator; gold skill IDs không được đưa vào QueryRecord của selector. Reporting xuất metrics và báo cáo cùng cấu hình chạy. Nhánh offline không gọi agent adapter và không yêu cầu có model API.

Điểm chính của thiết kế là code selector không phụ thuộc runtime của coding agent. Có thể bổ sung một phương pháp mới tuân theo interface để đưa vào pipeline, trong khi tái sử dụng loader, evaluator và reporting. Đây là khả năng thay thế về mặt thiết kế phần mềm; chưa có tuyên bố mọi phương pháp mới tự động đạt chất lượng tốt.

## Slide 3 — Integration (90 giây)

PoC A kiểm chứng đường cấp tài nguyên trước execution. Task được đưa vào MockSelector; kết quả lựa chọn được tạo trước khi resolve package. Loader chỉ copy package được chọn vào workspace của agent, kiểm tra revision và hash, rồi adapter truyền task kèm đường dẫn ngắn. Đây là file-based context provisioning, không gọi là native skill loading.

Bộ kiểm tra đã lưu có 51 pytest cases pass, gồm 26 test của PoC cùng test selector và registry. Bốn quyết định rỗng, A, B và A cộng B được kiểm tra không cần LLM cho cả hai adapter. A là systematic-debugging, B là verification-before-completion. Nhánh rỗng chứng minh wrapper không cấp external skill; chưa chứng minh selector biết khi nào nên chọn rỗng.

Ví dụ trên slide lấy từ một run mini thật. Decision chứa đúng ID skill B. Trong trajectory, agent gọi type tới SKILL.md trong workspace; observation trả returncode bằng không và chứa nội dung skill. Exposure log ghi read_observed sau đó. Các đoạn ở đây là trích từ artifact, không phải trace mô phỏng.

Vì vậy, mini đã có bằng chứng selected, provided và read_observed. Codex wrapper đã qua kiểm tra logic; lượt live mới đã kết nối model và hoàn thành turn nhưng Windows executor chưa chạy được lệnh đọc, nên live read vẫn NOT_VERIFIED. Kết quả task là trục riêng: mini selected chỉ đạt 9 trên 19 test, no-skill đạt 14 trên 19. Hai lượt nhỏ này không phải thí nghiệm hiệu quả, không đủ để so sánh pass rate giữa hai điều kiện.

## Slide 4 — Offline evaluation (90 giây)

PoC B dùng đúng SkillRet v1.1 test split, với 6.006 skills, 4.392 queries và 7.187 qrels. Cả Random và BM25 chạy trên cùng corpus và toàn bộ query, không lấy mẫu và không tuning bằng test labels. Random dùng seed không; BM25 giữ tham số mặc định. Mỗi phương pháp trả top 15 và được đánh giá tại các cutoff 5, 10 và 15.

Biểu đồ và bảng này trình bày ba metric tại cutoff 10 theo tỷ lệ từ không đến một, không phải phần trăm. NDCG đo chất lượng thứ tự ranking; Recall đo tỷ lệ positive skills tìm được; Completeness chỉ bằng một nếu lấy đủ mọi positive skill của query trong top 10. Vì có query nhiều positive, Recall khá cao vẫn chưa đồng nghĩa skill set đầy đủ.

BM25 có NDCG khoảng 0,517, Recall khoảng 0,594 và Completeness khoảng 0,446. Random có các giá trị rất nhỏ nhưng khác không, được giữ đầy đủ trong bảng. Không đổi trục sang log hoặc làm tròn Random thành không để nhấn mạnh chênh lệch.

Quan trọng hơn, lượt chạy mới tái lập chính xác ranking, scores và mọi metric so với artifact v1.1 cũ. Hai file metrics.json và per_query.csv khớp từng byte. Có 12 test evaluator, selector và runner pass cùng 49 kiểm tra hậu nghiệm. Hash dữ liệu, config và trạng thái source được lưu. Đây là bằng chứng reproducibility của pipeline retrieval trong repo, không phải tuyên bố tái lập độc lập bảng số liệu paper hay chứng minh task completion của agent.

## Slide 5 — Giới hạn (75 giây)

Các giới hạn ở đây gắn trực tiếp với câu hỏi nghiên cứu tiếp theo. Thứ nhất, kết quả hiện tại chủ yếu dựa trên relevance của từng skill. Completeness đánh giá lấy đủ positive labels, nhưng vẫn chưa mô hình hóa dependency, complementarity hoặc conflict giữa các skill. Bộ ranking tốt chưa chắc đã là một skill set tối ưu cho task cụ thể.

Thứ hai, mọi query trong SkillRet test đang dùng đều có ít nhất một positive label. Vì vậy benchmark này chưa đủ để đánh giá quyết định no-skill. Nhánh rỗng trong integration chỉ là kiểm tra cơ chế cấp tài nguyên, không phải một bộ đánh giá no-skill chính xác.

Thứ ba, em chưa chứng minh skill làm tăng pass rate hoặc giảm chi phí. Hai lượt mini có task verifier fail và không đủ số lượng để suy ra hiệu quả hay tác hại của skill. Em tách selected, provided, read_observed và task_passed để không gộp các mức bằng chứng này thành một kết luận thành công chung.

Cuối cùng, phạm vi live integration hiện đã kiểm chứng trên mini-SWE-agent. Codex kết nối model được, nhưng đọc skill qua tool chưa được xác minh vì executor Windows. Do đó phần này được ghi NOT_VERIFIED. Các giới hạn này giúp xác định dữ liệu và protocol phải bổ sung, thay vì thay đổi số liệu hoặc dùng task pass để thay thế bằng chứng đọc tài nguyên.

## Slide 6 — Kế hoạch (90 giây)

Trong tuần tới, em dự kiến năm đầu ra cụ thể. Đầu tiên là một embedding retrieval baseline chạy trên cùng split, cùng corpus và các metric đã có, để so sánh công bằng với BM25. Đây là phần kế hoạch, chưa phải kết quả đã triển khai trong báo cáo hôm nay.

Thứ hai là phân tích sâu nhóm query cần nhiều skill, chẳng hạn đối chiếu độ đầy đủ của ranking theo số positive. Thống kê sơ bộ đã có 2.143 query một positive, 1.703 query hai và 546 query ba. Đầu ra mới cần đi xa hơn đếm số lượng: tìm ví dụ và phân tích lỗi lựa chọn tập skill.

Thứ ba là một bản thiết kế Task-aware Skill Set Selection với dynamic-k: mô tả đầu vào, đầu ra, tiêu chí chọn số skill và các giả thuyết cần đánh giá. Chưa vội coi một score threshold là bằng chứng quyết định no-skill đúng.

Thứ tư là annotation guideline cho quan hệ skill và no-skill, kèm một tập task mẫu đã rà soát. Guideline cần làm rõ bằng chứng, mức không chắc chắn và cách xử lý bất đồng nhãn. Thứ năm là protocol end-to-end so sánh no-skill với selected-skill trên workspace và điều kiện tương đương, ghi task success, skill read, thời gian và cost theo khả năng quan sát.

Sau tuần này, nền tảng cần thiết đã có: interface độc lập, một integration có live evidence và pipeline offline tái lập được. Trọng tâm nghiên cứu tiếp theo là lựa chọn một tập skill phù hợp với task, thay vì chỉ xếp hạng từng skill theo relevance.
