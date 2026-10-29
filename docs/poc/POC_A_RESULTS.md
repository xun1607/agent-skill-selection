# PoC A — Kết quả pre-run integration với MockSelector


## Phạm vi và thay đổi

External MockSelector dùng Selector.fit/select và SelectionResult hiện có. Quyết định có trước resolve package. Loader chỉ chấp nhận ID đã review, nguồn/revision khóa trong registry; kiểm tra hash nguồn và bản copy. Chỉ package đã chọn có trong workspace/.poc_skills. Prompt dùng đường dẫn ngắn, không chứa toàn văn skill. Adapter kiểm tra decision/prompt/package và resource thừa trước execution.

Source thay đổi:

- src/skill_selection/selectors/mock_selector.py — mới, quyết định cấu hình; không retrieval.
- scripts/agent_skill_poc.py — selection độc lập, provisioning, validation, wrapper Codex, evidence và summary; giữ verifier.
- scripts/run_mini_skill_poc.py — giữ Python API/Responses/LocalEnvironment, bỏ execution mid-run; kiểm tra đầu vào và đọc file; unattended dùng DefaultAgent để chạy khi không có console.
- tests/unit/test_agent_skill_poc.py — ma trận và kiểm tra lỗi; fake model/process, không LLM.

Tài liệu: RUNBOOK.md và báo cáo này; log công việc tại docs/worklog/2026-10-23.md.

## Tests không cần LLM

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_agent_skill_poc.py tests/unit/test_selectors.py tests/unit/test_registry.py --basetemp artifacts/poc-a-tests-final-tmp --junitxml artifacts/poc-a-tests-final.xml
```

Kết quả cuối: **51 passed in 63.87s**. Bằng chứng: artifacts/poc-a-tests-final.xml và artifacts/poc-a-tests-final.log. Bộ PoC chiếm 26 tests, còn lại là selector và registry. Vòng đầu có lỗi encoding UTF-8 trong fake log và mini interactive không có console; đã sửa và chạy lại. Không coi vòng lỗi đầu là pass.

A = systematic-debugging; B = verification-before-completion. Full ID có tiền tố obra-superpowers/skills/.

| Mock decision | Prepare Codex/mini | Codex fake execution | Mini fake execution |
|---|---|---|---|
| [] | PASS: không tạo .poc_skills | PASS | PASS |
| [A] | PASS: chỉ A | PASS | PASS |
| [B] | PASS: chỉ B | PASS | PASS |
| [A,B] | PASS: đúng A,B | PASS | PASS |

Fake execution chỉ đọc tài nguyên rồi hoàn thành; verifier task cố ý FAIL vì không sửa bug. Test riêng kiểm tra invalid ID trước process/model, unselected resource bị chặn, output đọc lỗi/không đầy đủ không được tính read_observed, verifier bắt bug và oracle đúng đạt 19/19.

## Execution thật

Artifact root: artifacts/poc-a-live/.

| Run ID | Decision | Execution | Integration | Task verifier |
|---|---|---|---|---|
| 20261022T175004388037Z-mini-pre | [B] | Submitted, exit 0 | PASS, read_observed | FAIL: 9 passed, 10 failed |
| 20261022T175245063986Z-mini-pre | [] | Submitted, exit 0 | PASS, provided=[] | FAIL: 14 passed, 5 failed |
| 20261022T175127351935Z-codex-pre | [B] | Timeout 90 giây, lỗi kết nối | NOT_VERIFIED | FAIL trên workspace chưa hoàn thành |

Mini returned model: gpt-5.4-mini-2026-03-17. Requested model openai/gpt-5.4-mini. Selected run có 12 API calls và chi phí mini ghi nhận $0.0478575; no-skill có 13 calls, $0.0643386. Tổng khoảng $0.1122 theo cost tracking, không phải hóa đơn provider.

Selected mini run được prepare trước khi bổ sung decision_hash vào manifest. Nó vẫn có prompt/package hashes và decision/exposure/trajectory để đối chiếu; các run prepare sau và code cuối có thêm kiểm tra decision_hash. Không sửa lại artifact selected để làm như đã có kiểm tra đó từ đầu.

Codex requested model gpt-6-luna; không xác minh model thực tế. CLI login status trong phiên công cụ trả Not logged in; stderr execution có lỗi kết nối và retry nội bộ CLI trước timeout. Không kết luận chỉ auth là nguyên nhân. Không retry wrapper và không chạy Codex no-skill khi backend chưa khả dụng. Codex thực tế còn NOT_VERIFIED; fake adapter tests không thay thế execution thật.

## Bằng chứng selected → provided → read_observed

Selected mini run:

1. exposure.jsonl ghi selected lúc 17:50:04.534242Z với skill B.
2. provided lúc 17:50:04.542862Z: path .poc_skills/verification-before-completion/SKILL.md, source commit b739a8af570e10a95898f2bdf6cec97467fa6c12, revision sha256:5eeb7d00c1d12c39155f4452da37a7ed354d69d5b2b250412f9dcdb39578bcf6.
3. agent_started lúc 17:50:27.599297Z, đúng workspace của run.
4. read_observed lúc 17:50:31.524982Z: command type .poc_skills\verification-before-completion\SKILL.md ở trajectory step 1, returncode 0, full document trong observation khớp file đã cấp.

No-skill mini run: decision.result.skill_ids=[], summary.provided=[], không tạo workspace/.poc_skills. Không cấp external skill từ wrapper; default skills/config của agent chưa được cô lập.

Mỗi run có decision.json, manifest.json, exposure.jsonl, prompt.txt, execution.json, agent-status.json, verifier-result.json, verifier.log, summary.json/md và patch.diff. Mini có trajectory.json, Codex có events.jsonl; stderr.log lưu lỗi. Xem verification/ để lấy bản verifier theo timestamp. Không có read_observed của Codex. Thiếu file final.txt sau timeout không được hiểu là hoàn thành.

## Kết luận có thể báo cáo

PASS: external selector điều khiển đúng tài nguyên cấp trước execution qua file-based context provisioning; cả bốn quyết định được kiểm tra không LLM cho hai adapter; mini selected và no-skill chạy thật và có evidence.

NOT_VERIFIED: execution thật của Codex và native skill loading. FAIL: task success trong cả hai lượt mini. Không suy skill đã được áp dụng chỉ vì đã đọc, không chứng minh hiệu quả skill hoặc chênh lệch chất lượng giữa hai lượt. Không sửa acceptance tests, không chạy thêm lượt để che kết quả task fail.

## Việc tiếp theo cho native skill loading

Trước hết khắc phục auth/kết nối Codex và chạy selected/no-skill trên workspace mới. Sau đó xác minh discovery path và explicit invocation của đúng phiên bản agent, ánh xạ decision vào native loader, kiểm soát default skills, ghi log discovery/read và test không nạp unselected skills. Mini cần xác minh có native loader phù hợp hay không; UNKNOWN hiện tại. Không cần hooks hoặc mid-run để hoàn thành pre-run PoC.
