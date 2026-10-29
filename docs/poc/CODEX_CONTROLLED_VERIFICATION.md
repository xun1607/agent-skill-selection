# Codex — Một lượt xác minh có kiểm soát

Ngày 23/10/2026 (run ID dùng UTC ngày 22). Không đổi kiến trúc/source PoC, task, fixture hoặc verifier; không commit. Có hai probe tối thiểu ở hai môi trường và **đúng một execution task selected [B]**. Không retry task sau khi phát hiện blocker.

## Chẩn đoán ban đầu

- CLI: `codex-cli 0.162.0-alpha.17.2`, executable đi kèm extension VS Code `openai.chatgpt-26.1007.21434-win32-x64`.
- Config và model yêu cầu: `gpt-6-luna`. Không thay model hoặc global config.
- Run cũ `artifacts/poc-a-live/20261022T175127351935Z-codex-pre` có `invalid peer certificate: UnknownIssuer`, retry WebSocket rồi HTTPS, không có command execution event. Python wrapper hết timeout 90 giây trong lúc CLI đang kết nối model; không phải timeout chờ tool.
- Trong parent tool sandbox: `login status` exit 1, báo Not logged in; file auth có metadata ChatGPT, không in/copy token. Probe model tối thiểu gặp cùng lỗi TLS, bị dừng sau 35 giây. Authentication qua CLI trong môi trường đó chưa hoạt động, không suy thành tài khoản của người dùng đã logout.
- Ngoài parent tool sandbox, vẫn giữ Codex `read-only`: cùng executable/model, `login status` exit 0, Logged in using ChatGPT; minimal exec trả `OK`, có turn.completed, exit 0 sau khoảng 4.437 giây. Không tắt TLS verification, không chuyển sang API key hoặc sửa credential.

Sự khác biệt môi trường đã được quan sát trực tiếp. Cơ chế cụ thể gây hạn chế certificate/auth trong parent sandbox chưa được cô lập sâu hơn. Không dùng lỗi 90 giây làm bằng chứng tích hợp không khả thi.

## Lượt task duy nhất

Sau minimal PASS, chuẩn bị workspace mới bằng chính `prepare(..., skill_ids=[B])`; chạy `run_codex(..., timeout=300)` ngoài parent tool sandbox. Wrapper vẫn dùng `--sandbox workspace-write`. Guard mở file với mode x ngăn gọi task lần thứ hai.

| Thành phần | Kết quả | Bằng chứng |
|---|---|---|
| MockSelector trả B | PASS | decision.result.skill_ids chỉ có obra-superpowers/skills/verification-before-completion |
| Wrapper cấp đúng B | PASS | workspace/.poc_skills/verification-before-completion/SKILL.md; revision/hash khớp package khóa |
| Model/CLI hoàn thành turn | PASS | CLI exit 0, có turn.completed |
| Agent thực sự đọc skill | NOT_VERIFIED | Hai lệnh đọc đều lỗi trước khi tạo process; không read_observed |
| Tool executor chạy được | FAIL | Cả 3 command, bao gồm pwd, exit -1 với helper_unknown_error: setup refresh had errors |
| Task verifier | FAIL | 10 passed, 9 failed, tổng 19 |
| Source/task/verifier/fixture không đổi | PASS | So sánh hash trước/sau; patch.diff rỗng |
| Integration end-to-end | NOT_VERIFIED | Cấp tài nguyên đúng nhưng chưa có đọc thành công |

Đây không còn là timeout model hoặc wrapper: agent nhận phản hồi, yêu cầu tool rồi kết thúc khi executor không khởi tạo được. Có command execution events nhưng đó là **attempt thất bại**, không phải bằng chứng đọc skill. CLI exit 0 chỉ phản ánh turn hoàn thành, không phải task thành công.

Blocker hiện tại: Windows unified-exec helper không tạo được process (`setup refresh had errors`), kể cả `pwd`. Nguyên nhân sâu hơn của helper setup chưa xác định. Cảnh báo Consensus MCP auth vẫn có nhưng không ngăn model trả lời; không đủ bằng chứng coi nó là nguyên nhân lỗi helper. Các helper binaries có trong thư mục CLI, nên chưa kết luận package thiếu file.

## Artifact

Root: `artifacts/codex-controlled/20261022T180909990579Z/`.

- [Verification tổng hợp](../../artifacts/codex-controlled/20261022T180909990579Z/verification.json)
- [Manifest chẩn đoán](../../artifacts/codex-controlled/20261022T180909990579Z/diagnostic-manifest.json)
- [Minimal trong sandbox](../../artifacts/codex-controlled/20261022T180909990579Z/minimal-status.json)
- [Minimal ngoài sandbox](../../artifacts/codex-controlled/20261022T180909990579Z/outside-status.json)
- [Task summary](../../artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/summary.md)
- [Task events](../../artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/events.jsonl): command failures tại dòng 5, 7 và 9.
- [Task stderr](../../artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/stderr.log)
- [Verifier](../../artifacts/codex-controlled/20261022T180909990579Z/task-runs/20261022T181059716980Z-codex-pre/verifier-result.json)

Task run còn có decision.json, manifest.json, exposure.jsonl, prompt.txt, execution.json, agent-status.json, final.txt, verifier.log và verification/. `task-control.json` lưu hashes trước chạy; `task-execution-guard.json` ghi nhận ngân sách một task đã dùng. Không sửa artifact cũ.

## Lệnh đã thực thi và tái lập

Hai driver chẩn đoán nằm trong artifact, không phải framework/source PoC mới:

```powershell
.\.venv\Scripts\python.exe artifacts/codex-controlled/20261022T180909990579Z/probe_outside.py
# Driver exit 0; minimal Codex exit 0.

.\.venv\Scripts\python.exe artifacts/codex-controlled/20261022T180909990579Z/run_once.py
# Driver exit 1 vì integration NOT_VERIFIED; Codex CLI bên trong exit 0.
```

Guard của run_once đã tồn tại nên không gọi lại task trong cùng đợt. Để kiểm tra minimal thủ công trong terminal người dùng, dùng executable thực nếu codex chỉ là alias:

```powershell
codex --version
codex login status
codex exec -C 'D:/PROJECT_GIT/agent_skill_selection/artifacts/codex-controlled/20261022T180909990579Z/minimal-workspace' --skip-git-repo-check --sandbox read-only --json -m gpt-6-luna 'Reply with exactly OK. Do not run any tools or modify any files.'
```

Sau khi khắc phục helper và có một đợt task mới được phép, cách tái lập bằng code hiện có là:

```powershell
.\.venv\Scripts\python.exe scripts/agent_skill_poc.py prepare --agent codex --model gpt-6-luna --skill-id obra-superpowers/skills/verification-before-completion
# Gán $run bằng đường dẫn mới vừa in.
.\.venv\Scripts\python.exe scripts/agent_skill_poc.py run-codex --run $run --codex 'C:/Users/Nguyen Xuan/.vscode/extensions/openai.chatgpt-26.1007.21434-win32-x64/bin/windows-x86_64/codex.exe'
```

Lệnh CLI run-codex dùng timeout mặc định 600 giây; lượt có kiểm soát này gọi cùng hàm qua driver với timeout 300 giây, thực tế không chạm timeout. Không tự chạy các lệnh task thêm trong lượt này.

Tiếp theo chỉ cần điều tra log/runtime của Windows helper và môi trường launch Codex CLI; không có bằng chứng yêu cầu thay kiến trúc selector/provisioning hoặc verifier. Chưa khẳng định native skill loading, skill use hoặc hiệu quả skill.

Tham khảo OpenAI Docs về `exec --json`: https://developers.openai.com/blog/eval-skills
