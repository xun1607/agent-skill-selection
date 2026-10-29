# PoC A — Pre-run integration với MockSelector

Luồng: `Selector.fit(catalog)` → `select(query, k)` → resolve và kiểm tra hash package → cấp file vào workspace → chạy agent → kiểm tra log và verifier. Đây là **file-based context provisioning**, không phải native skill loading. MockSelector kiểm tra tích hợp, không đánh giá relevance.

## 1. Test không cần LLM

Chạy tại repo trong PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_agent_skill_poc.py tests/unit/test_selectors.py tests/unit/test_registry.py --junitxml artifacts/poc-a-tests.xml
```

Bốn quyết định được kiểm tra trên cả prepare và hai adapter: `[]`, `[A]`, `[B]`, `[A,B]`.

- A: `obra-superpowers/skills/systematic-debugging`
- B: `obra-superpowers/skills/verification-before-completion`

Fake model/process không sửa task, nên integration có thể PASS trong khi verifier task FAIL. Các test khác kiểm tra ID sai trước agent, resource thừa, thiếu bằng chứng đọc, và verifier với implementation sai/đúng. Không gọi LLM trong bộ test.

## 2. Prepare — chưa gọi model

Ví dụ chọn B, sử dụng model khả dụng với tài khoản:

```powershell
.\.venv\Scripts\python.exe scripts/agent_skill_poc.py prepare --agent codex --model gpt-6-luna --skill-id obra-superpowers/skills/verification-before-completion
```

Script in đường dẫn run mới. Gán `$run` bằng đường dẫn đó. Chọn A bằng cách thay ID; chọn cả hai bằng hai `--skill-id`; no-skill bỏ toàn bộ `--skill-id`. Không có hai skill mặc định. `--mode baseline` yêu cầu quyết định rỗng; `pre` cũng hỗ trợ rỗng.

```powershell
$run = 'D:/PROJECT_GIT/agent_skill_selection/artifacts/skill-poc/<run-id>'
Get-Content "$run/decision.json"
Get-Content "$run/prompt.txt"
Get-Content "$run/exposure.jsonl"
Get-ChildItem "$run/workspace/.poc_skills" -Recurse
```

Chỉ package được chọn có trong `workspace/.poc_skills/`, cùng license. No-skill không tạo thư mục này; lệnh Get-ChildItem khi đó báo không tồn tại là bình thường. Prompt chứa task gốc và tham chiếu ngắn, không ghép toàn văn SKILL.md. Metadata ghi source commit, revision, hash. `readable_by_runner` chưa chứng minh agent đọc được.

## 3. Execution thật — có thể tiêu tốn quota/API

Codex CLI:

```powershell
codex login status
.\.venv\Scripts\python.exe scripts/agent_skill_poc.py run-codex --run $run
```

Nếu chỉ có alias PowerShell, truyền executable thực bằng `--codex 'C:/path/to/codex.exe'`.

Mini: prepare run mới với `--agent mini --model openai/gpt-5.4-mini` hoặc đúng model đã xác minh khả dụng, sau đó:

```powershell
.\.venv\Scripts\python.exe scripts/run_mini_skill_poc.py --run $run --unattended
```

Unattended dùng DefaultAgent của mini để tránh yêu cầu Windows console. Bỏ flag dùng InteractiveAgent để xác nhận từng lệnh. Giới hạn mini: 20 bước, ngưỡng cost $0.50, 300 giây theo vòng lặp, request timeout 30 giây; mặc định không retry request. Cost limit không phải hard billing cap. LocalEnvironment không phải OS sandbox.

Codex dùng workspace-write, timeout wrapper mặc định 600 giây. Timeout không bảo đảm mọi process con đều dừng. Một run chỉ được execution một lần; tạo run mới sau khi sửa cấu hình. Không tự retry nhiều run để tìm kết quả đẹp.

## 4. Artifact và kết luận

| File | Nội dung |
|---|---|
| decision.json | SelectionResult và resources |
| manifest.json | Agent/model yêu cầu/workspace/hash task, prompt, decision |
| exposure.jsonl | selected → provided → agent_started → read_observed nếu có |
| prompt.txt | Task và đường dẫn ngắn |
| execution.json | Phiên bản và cấu hình/lệnh |
| events.jsonl / trajectory.json | Log Codex / mini |
| stderr.log, agent-status.json | Lỗi, exit status |
| verifier-result.json, verifier.log, patch.diff | Kết quả task độc lập; lịch sử trong verification/ |
| summary.json, summary.md | Integration và task success tách riêng |

`read_observed` yêu cầu command thành công có tên resource/SKILL.md và full document trong output. Đây là tiêu chí bảo thủ: wildcard, output bị cắt hoặc cơ chế đọc khác có thể chưa đủ bằng chứng. Thiếu trace → unknown; có trace nhưng thiếu bằng chứng → not_observed. Không suy từ task pass hoặc lời tự nhận của agent; không fallback nhét nội dung vào prompt.

Integration PASS khi execution hoàn thành và mọi skill đã cấp có read_observed; no-skill không cần đọc skill. NOT_VERIFIED khi chưa chạy, lỗi backend hoặc thiếu bằng chứng. ID/hash/resource sai bị chặn trước execution. Task pass/fail do verifier quyết định riêng. Default skills chưa được cô lập; no-skill chỉ có nghĩa wrapper không cấp external skills.

## 5. Native loading — công việc tiếp theo

Xác minh discovery path/explicit invocation trên đúng phiên bản mỗi agent; ánh xạ quyết định selector vào cơ chế đó; cô lập default skills; bổ sung test selected/unselected và log discovery. Mini adapter hiện không có native skill loader. Không triển khai hooks hoặc mid-run trong PoC này.

Tham khảo OpenAI Docs về event log: https://developers.openai.com/blog/eval-skills
