# PoC 1: cấp workflow skill cho coding agent

Thực hành theo [RUNBOOK: thứ tự lệnh, kết quả kỳ vọng và vị trí bằng chứng](RUNBOOK.md).
File này giữ phần mô tả phạm vi, kiến trúc và cách hoạt động của PoC.

## Mục tiêu và trạng thái

Kiểm chứng cùng một task có thể nhận workflow skill qua đầu vào Codex CLI và mini-SWE-agent, thu trace,
và chấm bằng verifier riêng. Sau hai ca cấp trước run, thử đúng một điểm can thiệp giữa run trên mini.
Đã chuẩn bị fixture, công cụ và test không model; CHƯA có kết quả agent thật cho task mới này.
Không dùng kết quả để khẳng định tăng pass rate/giảm cost, đánh giá retrieval hoặc huấn luyện selector.

## Task và skill

Task tại `benchmarks/skill_poc/task.md`: sửa CLI tổng hợp thanh toán CSV qua ba lớp reader → report → CLI.
Không phải lỗi một dòng: giao dịch khác ID của cùng khách hàng bị bỏ sót; duplicate ID cần idempotency và
phát hiện xung đột; tính tiền phải làm tròn từng khoản theo decimal HALF_UP. Agent cần đọc đường đi dữ liệu,
thêm regression test, kiểm cả API Python và CLI. Không cần Flask, Docker, browser hay cài dependency mới.

Hai skill gốc từ Superpowers đã tải theo commit:

| Skill | Điều quan sát từ trace |
|---|---|
| systematic-debugging | Tái hiện thất bại trước sửa; nguyên nhân gắn với dữ liệu/đoạn code; regression test |
| verification-before-completion | Chạy đầy đủ test sau thay đổi cuối; chạy CLI; kết luận khớp kết quả |

`benchmarks/skill_poc/skill-review.json` ghi revision, căn cứ license MIT, phạm vi duyệt và giới hạn harness.
Giữ nguyên gói gốc và license khi copy vào run. Đây là chọn cố định theo độ phù hợp do người thực hiện rà soát,
không phải selector mới hoặc nhãn benchmark. Task được xây để thử workflow, chưa đại diện cho tác vụ thực tế.
Registry profiles vẫn needs_review, không bị âm thầm đổi valid.

## Các file mới và trách nhiệm

| Đường dẫn | Vai trò |
|---|---|
| `benchmarks/skill_poc/task.md` | Yêu cầu nghiệp vụ và tiêu chí công khai |
| `benchmarks/skill_poc/workspace/` | Mã lỗi bất biến, CSV mẫu và 3 test công khai |
| `benchmarks/skill_poc/verifier/test_acceptance.py` | 16 ca bổ sung, không copy vào workspace agent |
| `benchmarks/skill_poc/skill-review.json` | Duyệt hai gói riêng cho PoC |
| `scripts/agent_skill_poc.py` | prepare workspace/prompt/decision/manifest; verify độc lập và ghi patch/report |
| `scripts/run_mini_skill_poc.py` | Adapter nhỏ Responses, audit cấp skill và callback giữa run |
| `tests/unit/test_agent_skill_poc.py` | Kiểm fixture lỗi/đúng, verifier, trigger và preparation không model |

## 1. Chuẩn bị ca Codex, chưa gọi model

Chạy PowerShell tại repo. Dùng alias codex đã đăng nhập; đặt model đúng ID đã chạy thành công trên tài khoản.

```powershell
$codexModel = 'MODEL_ID_DA_CHAY_DUOC'
$codexRun = & .\.venv\Scripts\python.exe scripts/agent_skill_poc.py prepare --agent codex --mode pre --model $codexModel
code "$codexRun\prompt.txt"
```

Đọc task và hai khối selected_skill; kiểm tra `decision.json`, `manifest.json`. Chưa có model call ở bước này.

Chạy verifier trước sửa; KỲ VỌNG exit 1 và status fail, không phải lỗi script:

```powershell
& .\.venv\Scripts\python.exe scripts/agent_skill_poc.py verify --run $codexRun
```

Mỗi lần verify giữ một thư mục `verification/<timestamp>/`; file verifier-result.json ở gốc chỉ là bản gần nhất.

## 2. Cấp skill cho Codex CLI

Lệnh sau gọi model và thực hiện task. Sandbox vẫn được bật. Không dùng --no-daemon với exec.

```powershell
codex --version | Set-Content "$codexRun\cli-version.txt" -Encoding UTF8
Get-Content "$codexRun\prompt.txt" -Raw -Encoding UTF8 |
    codex exec -C "$codexRun\workspace" -m $codexModel --sandbox workspace-write --json `
    -o "$codexRun\final.txt" - 2> "$codexRun\stderr.log" |
    Tee-Object -FilePath "$codexRun\events.jsonl"

& .\.venv\Scripts\python.exe scripts/agent_skill_poc.py verify --run $codexRun
```

Đối chiếu event command_execution/file_change (sửa bằng shell có thể không có file_change riêng), final và
verifier.log. `model_requested` là cấu hình yêu cầu, không tự chứng minh model thực tế. Lưu lỗi và failed runs.
Codex input đã lưu/hash là bằng chứng provided; không coi đó là bản dump nguyên request gửi model.

## 3. Cấp skill cho mini-SWE-agent

```powershell
$miniModel = 'openai/gpt-5.4-mini'  # hoặc đúng model API bạn đã chạy thành công
$miniRun = & .\.venv\Scripts\python.exe scripts/agent_skill_poc.py prepare --agent mini --mode pre --model $miniModel
& .\.venv\Scripts\python.exe scripts/agent_skill_poc.py verify --run $miniRun
& .\.venv\Scripts\python.exe scripts/run_mini_skill_poc.py --run $miniRun
& .\.venv\Scripts\python.exe scripts/agent_skill_poc.py verify --run $miniRun
```

Mặc định mini chờ duyệt lệnh. Lệnh này dùng Responses như ca smoke đã thành công, không dùng Chat Completions.
Giới hạn ban đầu 35 bước / 1 USD (giới hạn chi phí được kiểm giữa các lần gọi, không phải trần thanh toán cứng)
/ 900 giây; chỉ tăng có chủ ý nếu dừng vì limit. `--unattended` bỏ duyệt từng lệnh; không cần cho lần đầu.
LocalEnvironment của mini KHÔNG phải OS sandbox; yêu cầu giới hạn thư mục là hướng dẫn, không phải cơ chế cô lập.

`delivery-events.jsonl` ghi skill text có mặt trong context ngay trước lời gọi Responses, và model trả về sau đó.
`skill_md_hash` kiểm byte file nguồn; `load_text_hash` kiểm chuỗi UTF-8 thực tế được chèn (sau chuẩn hóa newline khi đọc).
Điều này giúp phân biệt selected / context prepared / request returned; không khẳng định token được model chú ý.
Trajectory và execution.json lưu cấu hình/phiên bản/cách xác nhận lệnh. Không đổi credential hay config toàn cục.

## 4. Một điểm can thiệp giữa run: mini sau pytest thất bại đầu tiên

Chỉ làm sau khi hai ca pre đã có bằng chứng:

```powershell
$midRun = & .\.venv\Scripts\python.exe scripts/agent_skill_poc.py prepare --agent mini --mode mid --model $miniModel
& .\.venv\Scripts\python.exe scripts/run_mini_skill_poc.py --run $midRun
& .\.venv\Scripts\python.exe scripts/agent_skill_poc.py verify --run $midRun
```

Đầu run chỉ cấp systematic-debugging. Callback sau execute_actions phát hiện một lệnh pytest có exit khác 0
và output chứa failed, thêm nguyên hướng dẫn verification-before-completion thành message trước lượt model tiếp.
Đó là điểm can thiệp xác định được; chưa chọn lại skill động, chưa có Codex native hook.

Chỉ ghi **mid-run injection observed** khi cả ba bằng chứng có mặt:

1. Observation của pytest thất bại, không phải lỗi python không tồn tại.
2. Event mid_run_injection và message poc_skill_injected cùng hash skill.
3. Lời gọi model sau event đó có skill_text_present chứa verification-before-completion và trả response.

Skill deferred nằm ngoài workspace/sibling skills công bố ở đầu run; vẫn không có bảo đảm OS rằng agent không thể
đọc nó. Kiểm audit trước trigger: nếu skill đã xuất hiện sớm thì báo contamination. Nếu callback không kích hoạt
hoặc không có model call tiếp theo thì báo not observed, không sửa lại lịch sử để làm đẹp PoC.

## Bằng chứng và tiêu chí nghiệm thu

| Run | Cấp trước run | Can thiệp giữa run | Verifier | Trạng thái khởi đầu |
|---|---|---|---|---|
| Codex pre | Hai skill trong prompt đã hash | Không | 19 test + giữ nguyên test/CSV | Chưa chạy |
| mini pre | Hai skill, có audit model context | Không | Cùng bộ kiểm tra | Chưa chạy |
| mini mid | Một skill đầu run | Skill verification sau failing pytest | Cùng bộ kiểm tra | Chưa chạy |

Với mỗi run lưu: manifest, decision, prompt, skill packages/license, trace, phiên bản execution/CLI, patch,
verifier log/result và report. Chấm workflow bằng trace theo bảng skill ở trên; report tự sinh để used=unknown
đến khi người rà soát. Không dùng file agent tự viết hay lời tự báo làm bằng chứng duy nhất.

Verifier chỉ copy implementation sang thư mục kiểm tra khác, cùng test nguyên bản và acceptance suite; không chạy
test agent viết thêm để làm căn cứ thay thế acceptance. Agent vẫn nên tự chạy test thêm của mình trong public suite.
Separation này chưa phải bảo mật hidden test trước một agent có quyền đọc toàn repo. Default skill/plugin của Codex
chưa được cô lập, do đó baseline nếu dùng chỉ mang nghĩa không cấp skill bổ sung qua adapter.

Tất cả run đánh dấu purpose=feasibility_poc, eligible_for_training=false. Task pass/fail và workflow observed là hai
kết quả riêng. PoC chưa hoàn thành chỉ vì prepare thành công hoặc verifier bản chuẩn trong unit test pass.
