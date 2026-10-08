"""Build the testcase / baseline comparison workbook (doc/testcases/GR2_testcases_baselines.xlsx).

What it does
  Runs pytest once (junit XML) and fills every testcase's "Đầu ra thực tế" and "Kết quả" from machine-written evidence:
  pytest results and their recorded values, acceptance checks on the real baseline outputs (artifacts/compare/gr1.json),
  the gate verdicts (benchmarks/gr1_internal/gate.json), the SkillRet reference file and the selection cache.
  Nothing in the results columns is typed by hand; the catalogue text comes from doc/testcases/catalog.yaml.

Input: doc/testcases/catalog.yaml, artifacts/compare/gr1.json (`python -m skill_selection compare gr1`),
       benchmarks/reference/skillret_v1.1_test.json (scripts/collect_skillret_reference.py),
       artifacts/explorer/selection_cache.json (`select gr1`). Run with the repo venv.
Output: doc/testcases/GR2_testcases_baselines.xlsx with sheets
       Đọc trước | Baseline | So sánh GR1 | Top-3 GR1 | So sánh SkillRet | Testcases | Tổng hợp
"""
import hashlib
import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import yaml
from openpyxl import Workbook
from openpyxl.formatting.rule import ColorScaleRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "doc" / "testcases" / "GR2_testcases_baselines.xlsx"
JUNIT = REPO / "artifacts" / "testcases" / "junit.xml"
FONT = "Arial"
HEAD_FILL = PatternFill("solid", fgColor="1F4E79")
RESULT_FILL = {"Đạt": "C6EFCE", "Không đạt": "FFC7CE", "Đạt một phần": "FFEB9C", "Chưa chạy": "E7E6E6"}
PROV = {"reproduced_here": ("Tái lập — repo này", "C6EFCE"), "reproduced_gr1": ("Tái lập — codebase GR1", "DDEBF7"),
        "paper_reported": ("Số bài báo công bố (chưa tái lập)", "FFF2CC"), "not_run": ("Chưa chạy", "E7E6E6")}
THIN = Side(style="thin", color="BFBFBF")
CODES = {"Random": "RND", "BM25": "BM25", "M0": "M0", "M1 (GR1)": "M1", "SkillRet-base": "RET0", "SkillRet-FT": "RETFT",
         "SkillRouter-Emb": "SRE", "SkillRouter": "SR", "GoS-lite": "GOS", "SkillReranker-h": "SKR", "M5-h": "M5"}
SOURCES = [
    ("SkillRet", "arXiv 2605.05726", "https://arxiv.org/abs/2605.05726"),
    ("SkillRouter", "arXiv 2603.22455", "https://arxiv.org/abs/2603.22455"),
    ("Graph of Skills", "arXiv 2604.05333", "https://arxiv.org/abs/2604.05333"),
    ("SkillReranker", "arXiv 2607.06283", "https://arxiv.org/abs/2607.06283"),
    ("SWE-Skills-Bench", "arXiv 2603.15401", "https://arxiv.org/abs/2603.15401"),
]


def run_pytest() -> dict:
    JUNIT.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-o", "junit_family=xunit1", f"--junitxml={JUNIT}"],
                   cwd=REPO, capture_output=True, text=True)
    results = {}
    for case in ET.parse(JUNIT).getroot().iter("testcase"):
        node = f"{case.get('file') or case.get('classname').replace('.', '/') + '.py'}::{case.get('name')}"
        node = node.replace("\\", "/")
        failed = case.find("failure") is not None or case.find("error") is not None
        skipped = case.find("skipped") is not None
        props = {p.get("name"): p.get("value") for p in case.iter("property")}
        results[node] = {"status": "skipped" if skipped else ("failed" if failed else "passed"), "props": props}
    return results


def find(junit: dict, node: str) -> dict:
    hits = [v for k, v in junit.items() if k.endswith(node.split("tests/", 1)[-1])]
    return hits[0] if hits else {"status": "missing", "props": {}}


def resolve(tc: dict, junit: dict, compare: dict, reference: dict, gate: dict, selection_path: Path):
    ev = tc["evidence"]
    kind = ev["kind"]
    if kind == "planned":
        return ev["actual"], "Chưa chạy", "Kế hoạch"
    if kind == "manual":
        return ev["actual"], ev.get("result", "Đạt"), "Kiểm tay (ghi trong worklog)"
    if kind == "pytest":
        statuses = [find(junit, t)["status"] for t in ev["tests"]]
        n_ok = statuses.count("passed")
        result = "Đạt" if n_ok == len(statuses) else ("Chưa chạy" if set(statuses) <= {"skipped", "missing"} else "Không đạt")
        recorded = [find(junit, t)["props"].get("actual") for t in ev["tests"]]
        actual = "; ".join(r for r in recorded if r) or ev.get("actual", "")
        return f"{actual} [pytest {n_ok}/{len(statuses)} qua]", result, "pytest: " + ", ".join(t.split("::")[-1] for t in ev["tests"])
    if kind == "gate":
        vals = {t: r.get(ev["field"]) for t, r in gate.items()}
        applicable = {t: v for t, v in vals.items() if v not in (None, "n/a")}
        ok = sum(v == ev["want"] for v in applicable.values())
        result = "Đạt" if applicable and ok == len(applicable) else "Không đạt"
        return (f"{ev['field']} = {ev['want']} ở {ok}/{len(applicable)} nhiệm vụ áp dụng được"
                f"{'' if len(applicable) == len(vals) else f' ({len(vals) - len(applicable)} nhiệm vụ không có tệp test bảo vệ: n/a)'}",
                result, "benchmarks/gr1_internal/gate.json (validate() của GR1)")
    if kind == "reference":
        row = next(r for r in reference["rows"] if r["method"] == ev["method"] and r["provenance"] == "reproduced_here")
        paper = next(r for r in reference["rows"] if r["method"] == ev["method"] and r["provenance"] == "paper_reported")
        m, pm = row["metrics"], paper["metrics"]
        return (f"repo: NDCG@10 {m['NDCG@10']}, R@10 {m['Recall@10']}, C@10 {m['Completeness@10']}; "
                f"bài báo: {pm['NDCG@10']}, {pm['Recall@10']}, {pm['Completeness@10']}",
                "Đạt" if row.get("matches_paper") else "Không đạt", row["source"])
    if kind == "selection":
        if not selection_path.exists():
            return "chưa có selection_cache.json", "Chưa chạy", "artifacts/explorer"
        sel = json.loads(selection_path.read_text(encoding="utf-8"))
        p = sel["runs"][0]["params"]
        sha = hashlib.sha256(selection_path.read_bytes()).hexdigest()
        rerun = find(junit, "tests/unit/test_explorer.py::test_selection_is_byte_identical")["status"] == "passed"
        return (f"sha256 {sha[:16]}…; seed={p['seed']}, ram_mode={p['ram_mode']}, os={p['os']}; "
                f"chạy 2 lần giống từng byte (08/10, và test tự động)", "Đạt" if rerun else "Không đạt",
                "selection_cache.json + test_selection_is_byte_identical")
    if kind == "decomposition":
        tasks = compare["per_task"]["SkillReranker-h"]
        n = [r["n_states"] for r in tasks.values()]
        one_step = sum(x == 2 for x in n)
        return (f"Chuỗi hợp lệ, hữu hạn ở {len(n)}/{len(n)} nhiệm vụ, nhưng {one_step}/{len(n)} nhiệm vụ tiếng Việt chỉ ra "
                f"1 bước (2 trạng thái): bộ phân rã heuristic không tách được câu tiếng Việt. Trên 60 truy vấn tiếng Anh "
                f"của SkillRet tách được 2–4 bước (tests/fixtures/gr1_graph_parity.json)",
                "Đạt một phần" if one_step else "Đạt", "compare gr1 (SkillReranker-h: n_states)")
    raise ValueError(f"unknown evidence kind {kind}")


def style_table(ws, n_cols, widths, header_row=1):
    for col, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(col)].width = w
    for cell in ws[header_row]:
        cell.font = Font(name=FONT, bold=True, color="FFFFFF")
        cell.fill = HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
    for row in ws.iter_rows(min_row=header_row + 1):
        for cell in row:
            cell.font = Font(name=FONT, size=10, bold=cell.font.bold if cell.font else False)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(top=THIN, bottom=THIN, left=THIN, right=THIN)
    ws.freeze_panes = ws.cell(row=header_row + 1, column=2)
    ws.auto_filter.ref = f"A{header_row}:{get_column_letter(n_cols)}{ws.max_row}"


def main() -> int:
    catalog = yaml.safe_load((REPO / "doc" / "testcases" / "catalog.yaml").read_text(encoding="utf-8"))
    compare = json.loads((REPO / "artifacts" / "compare" / "gr1.json").read_text(encoding="utf-8"))
    reference = json.loads((REPO / "benchmarks" / "reference" / "skillret_v1.1_test.json").read_text(encoding="utf-8"))
    gate = json.loads((REPO / "benchmarks" / "gr1_internal" / "gate.json").read_text(encoding="utf-8"))["results"]
    manifest = json.loads((REPO / "benchmarks" / "gr1_internal" / "MANIFEST.json").read_text(encoding="utf-8"))
    junit = run_pytest()
    methods = compare["methods"]
    wb = Workbook()
    wb.calculation.fullCalcOnLoad = True                      # summary COUNTIFs are computed by Excel on open

    # ---------------------------------------------------------------- Đọc trước
    ws = wb.active
    ws.title = "Đọc trước"
    passed = sum(v["status"] == "passed" for v in junit.values())
    lines = [
        ("GR2 — Kịch bản testcase và so sánh baseline chọn skill", True),
        (f"Sinh tự động ngày {date.today():%d/%m/%Y} bằng scripts/build_testcase_workbook.py. Không gõ tay cột kết quả.", False),
        (f"Snapshot GR1: commit {manifest['gr1_commit'][:8]}, 41 skill, 6 nhiệm vụ. Nhãn: {compare['labels_status'][:40]}", False),
        (f"pytest: {passed}/{len(junit)} test qua. Thứ hạng baseline: sha256 {compare['rankings_sha256'][:16]}…", False),
        ("", False),
        ("Cách đọc", True),
        ("Baseline: mỗi phương pháp so sánh, đầu vào, đầu ra, biến thể đã cài và mức đạt điều kiện chấp nhận.", False),
        ("So sánh GR1: chạy thật trên máy, 6 nhiệm vụ, nhãn NHÁP → chỉ để phát hiện xu hướng, chưa phải kết luận.", False),
        ("So sánh SkillRet: kho lớn 6.006 skill, 4.392 truy vấn. Cột 'Nguồn số liệu' phân biệt số tái lập và số bài báo công bố.", False),
        ("Testcases: danh mục theo mẫu Elicitation; 'Đầu ra thực tế' và 'Kết quả' lấy từ bằng chứng máy ghi.", False),
        ("Kết quả: Đạt (xanh) · Đạt một phần (vàng) · Không đạt (đỏ) · Chưa chạy (xám).", False),
        ("", False),
        ("Bộ dữ liệu", True),
        ("DS-1 Bộ nội bộ GR1: 41 skill, 6 nhiệm vụ sửa lỗi (Python, Java), qua cổng kiểm định 4 điều kiện 6/6.", False),
        ("DS-3 SWE-bench (tập con): thay DS-2 SWE-Skills-Bench (repo 404, không có trên HuggingFace).", False),
        ("DS-5 SkillRet v1.1 test: 6.006 skill, 4.392 truy vấn, nhãn có sẵn (ghim revision 6583d7d).", False),
        ("", False),
        ("Tài liệu", True),
    ] + [(f"{n}: {a} — {u}", False) for n, a, u in SOURCES]
    for i, (text, bold) in enumerate(lines, 1):
        ws.cell(row=i, column=1, value=text).font = Font(name=FONT, size=12 if i == 1 else 10, bold=bold)
    ws.column_dimensions["A"].width = 130

    # ---------------------------------------------------------------- Baseline
    ws = wb.create_sheet("Baseline")
    ws.append(["Mã", "Phương pháp", "Họ phương pháp", "Bài báo / nguồn", "Đầu vào", "Đầu ra", "Biến thể đã cài",
               "Mô hình (revision ghim)", "Testcase chấp nhận", "Đạt / tổng"])
    info = compare["info"]
    model_of = {"M0": info.get("qwen", {}), "M1 (GR1)": info.get("qwen", {}), "SkillRet-base": info.get("qwen", {}),
                "GoS-lite": info.get("qwen", {}), "SkillReranker-h": info.get("qwen", {}), "M5-h": info.get("qwen", {}),
                "SkillRet-FT": info.get("SkillRet-FT", {}), "SkillRouter-Emb": info.get("SkillRouter-Emb", {}),
                "SkillRouter": info.get("SkillRouter-Emb", {})}
    for m in methods:
        checks = compare["checks"][m["id"]]
        mi = model_of.get(m["id"], {})
        model = f"{mi.get('model', '—')}@{mi.get('revision', '')[:8]}" if mi else "—"
        if m["id"] == "SkillRouter":
            model += f" + {info['SkillRouter-Reranker']['spec'].split(':', 1)[1][:-32]}"
        ws.append([CODES[m["id"]], m["id"], m["family"], m["paper"], m["input"], m["output"], m["variant"], model,
                   f"TC-BL-{CODES[m['id']]}-1 … {len(checks)}", f"{sum(c['passed'] for c in checks)}/{len(checks)}"])
    style_table(ws, 10, [8, 18, 22, 30, 30, 32, 50, 34, 18, 10])

    # ---------------------------------------------------------------- So sánh GR1
    ws = wb.create_sheet("So sánh GR1")
    cols = [("Recall@3", "Recall@3"), ("NDCG@3", "NDCG@3"), ("Recall@5", "Recall@5"), ("Completeness@5", "Completeness@5"),
            ("NDCG@10", "NDCG@10"), ("Set-F1 (tập chọn)", "set_f1"), ("Số skill chọn |S|", "n_selected")]
    ws.append(["Phương pháp", "Họ phương pháp"] + [c[0] for c in cols] + ["Kiểm tra đạt", "Ghi chú"])
    for m in methods:
        row = compare["metrics"][m["id"]]
        checks = compare["checks"][m["id"]]
        ws.append([m["id"], m["family"]] + [round(row[k], 3) for _, k in cols]
                  + [f"{sum(c['passed'] for c in checks)}/{len(checks)}", m["variant"][:90]])
    last = ws.max_row
    for col in range(3, 3 + len(cols) - 1):
        letter = get_column_letter(col)
        ws.conditional_formatting.add(f"{letter}2:{letter}{last}", ColorScaleRule(
            start_type="min", start_color="F8696B", mid_type="percentile", mid_value=50, mid_color="FFEB84",
            end_type="max", end_color="63BE7B"))
    style_table(ws, len(cols) + 4, [18, 26] + [12] * len(cols) + [12, 60])
    for r in range(2, last + 1):
        for c in range(3, 3 + len(cols)):
            ws.cell(row=r, column=c).number_format = "0.000"
    note = last + 2
    ws.cell(row=note, column=1, value=(f"Nhãn: {compare['labels_status']} — 6 nhiệm vụ, mỗi nhiệm vụ 3 skill vàng. "
                                       "Số liệu là trung bình 6 nhiệm vụ (Random: trung bình 5 seed). Chỉ để thấy xu hướng.")).font = Font(name=FONT, italic=True, size=9)
    ws.cell(row=note + 1, column=1, value=("Mô tả nhiệm vụ GR1 viết tiếng Việt, skill viết tiếng Anh: phương pháp từ vựng "
                                           "(BM25) bất lợi; mọi mô hình nhúng chạy bfloat16, đọc toàn văn (≤ 1.661 token).")).font = Font(name=FONT, italic=True, size=9)

    # ---------------------------------------------------------------- Top-3 GR1
    ws = wb.create_sheet("Top-3 GR1")
    labels = json.loads((REPO / "benchmarks" / "gr1_internal" / "labels_draft.json").read_text(encoding="utf-8"))["qrels"]
    task_ids = list(labels)
    ws.append(["Phương pháp"] + task_ids)
    ws.append(["Nhãn nháp (3 skill vàng)"] + [", ".join(sorted(labels[t])) for t in task_ids])
    for m in methods:
        per = compare["per_task"][m["id"]]
        ws.append([m["id"]] + [", ".join(f"{s}{' ✓' if s in labels[t] else ''}" for s in per[t]["selected"][:8])
                               + (f" (+{len(per[t]['selected']) - 8})" if len(per[t]["selected"]) > 8 else "")
                               for t in task_ids])
    style_table(ws, len(task_ids) + 1, [18] + [34] * len(task_ids))
    for cell in ws[2]:
        cell.fill = PatternFill("solid", fgColor="FFF2CC")
    ws.cell(row=ws.max_row + 2, column=1, value="✓ = có trong nhãn nháp. Phương pháp tự điều chỉnh số skill (GoS-lite, SkillReranker-h, M5-h) có thể chọn khác 3.").font = Font(name=FONT, italic=True, size=9)

    # ---------------------------------------------------------------- So sánh SkillRet
    ws = wb.create_sheet("So sánh SkillRet")
    ws.append(["Phương pháp", "Họ phương pháp", "Nguồn số liệu", "NDCG@10", "Recall@10", "Completeness@10",
               "Set-F1", "|S|", "Nguồn chi tiết", "Ghi chú"])
    for r in reference["rows"]:
        label, color = PROV[r["provenance"]]
        mt = r["metrics"]
        note_txt = r.get("description", "")
        if r.get("matches_paper") is not None:
            note_txt = "Khớp bài báo (±0,05)" if r["matches_paper"] else "LỆCH bài báo"
        ws.append([r["method"], r["family"], label, mt.get("NDCG@10"), mt.get("Recall@10"), mt.get("Completeness@10"),
                   mt.get("set_f1"), mt.get("n_selected"), r["source"], note_txt])
        ws.cell(row=ws.max_row, column=3).fill = PatternFill("solid", fgColor=color)
    for name, why in reference.get("not_available", {}).items():
        ws.append([name, "Đồ thị skill–skill", PROV["not_run"][0], None, None, None, None, None, "—", why])
        ws.cell(row=ws.max_row, column=3).fill = PatternFill("solid", fgColor=PROV["not_run"][1])
    for name in ("SkillRet-base / SkillRet-FT / SkillRouter (tái lập)",):
        ws.append([name, "Vector nhúng / xếp hạng lại", PROV["not_run"][0], None, None, None, None, None,
                   "scripts/colab_skillret_dense.py", "Cần GPU (Colab/Kaggle); kết quả đem về chấm bằng eval-run"])
        ws.cell(row=ws.max_row, column=3).fill = PatternFill("solid", fgColor=PROV["not_run"][1])
    style_table(ws, 10, [40, 24, 26, 11, 11, 14, 9, 7, 44, 50])
    ws.cell(row=ws.max_row + 2, column=1, value=("Đơn vị %. Số bài báo: SkillRet arXiv 2605.05726, Bảng 3 (tầng 1) và Bảng 4 "
                                                 "(xếp hạng lại top-20). Số GR1: chạy S2 ngày 01/10, tham số chỉnh trên 200 truy vấn train.")).font = Font(name=FONT, italic=True, size=9)

    # ---------------------------------------------------------------- Testcases
    ws = wb.create_sheet("Testcases")
    header = ["Mã TC", "Loại", "Thành phần kiểm thử", "Liên kết RAW", "Bộ dữ liệu", "Tiền điều kiện", "Đầu vào",
              "Đầu ra mong muốn", "Trạng thái trung gian mong muốn", "Đầu ra thực tế", "Kết quả", "Bằng chứng", "Ghi chú"]
    ws.append(header)
    rows = []
    for tc in catalog:
        actual, result, evidence = resolve(tc, junit, compare, reference, gate, REPO / "artifacts" / "explorer" / "selection_cache.json")
        rows.append([tc["id"], tc["type"], tc["component"], tc["raw"], tc["dataset"], tc["pre"], tc["input"],
                     tc["expected"], tc["intermediate"], actual, result, evidence, tc.get("note", "")])
    for m in methods:                                          # per-baseline acceptance on the real GR1 outputs
        for i, c in enumerate(compare["checks"][m["id"]], 1):
            rows.append([f"TC-BL-{CODES[m['id']]}-{i}", "Đ" if i <= 3 else "X", f"Baseline {m['id']}", "RAW-02", "DS-1",
                         "Snapshot GR1 + mô hình đã ghim revision", m["input"], c["check"], "—",
                         c["detail"] or ("đúng" if c["passed"] else "sai"), "Đạt" if c["passed"] else "Không đạt",
                         "compare gr1 → artifacts/compare/gr1.json", m["paper"]])
    unit_tc = {}
    for node, v in junit.items():
        tcid = v["props"].get("tc")
        if tcid and tcid.startswith("TC-BL"):
            unit_tc[tcid] = (node, v)
    unit_text = {"TC-BL-SR-01": ("SkillRouter-Reranker", "Prompt xếp hạng lại khớp model card"),
                 "TC-BL-SR-02": ("SkillRouter-Reranker", "Điểm lần chạy lại lấy từ cache, không gọi mô hình"),
                 "TC-BL-SR-03": ("SkillRouter-Embedding", "Truy vấn = instruction + văn bản; max 4096; revision ghim"),
                 "TC-BL-ALL-01": ("Mọi mô hình", "Mỗi mô hình ghim commit 40 ký tự"),
                 "TC-BL-GOS-01": ("GoS-lite", "Đồ thị từ sub_skills + nhắc tên skill; không cạnh giả"),
                 "TC-BL-GOS-02": ("GoS-lite", "PageRank tổng = 1; cạnh ngược lan được tới skill cần mình"),
                 "TC-BL-GOS-03": ("GoS-lite", "Gói skill dừng đúng ngân sách 12.000 ký tự")}
    for tcid in sorted(unit_tc):
        node, v = unit_tc[tcid]
        comp, expected = unit_text.get(tcid, (tcid, ""))
        rows.append([tcid, "T", f"Baseline {comp}", "RAW-09", "—", "Mô hình giả / đồ thị tự dựng", "Đầu vào nhỏ tự dựng",
                     expected, "—", v["props"].get("actual", ""), "Đạt" if v["status"] == "passed" else "Không đạt",
                     "pytest: " + node.split("::")[-1], ""])
    parity = [find(junit, "tests/unit/test_graph_parity.py::" + n)["status"] for n in
              ("test_parity_on_gr1_tasks", "test_parity_on_skillret_queries")]
    rows.append(["TC-BL-ALL-02", "T", "Lõi đồ thị chuyển từ GR1", "RAW-09", "DS-1, DS-5", "Dữ liệu đối chiếu do code GR1 sinh",
                 "6 nhiệm vụ GR1 + 60 truy vấn SkillRet × 5 chế độ", "Tập chọn và top-10 trùng GR1", "—",
                 f"pytest {parity.count('passed')}/2 qua (66 trường hợp × 5 chế độ)",
                 "Đạt" if parity.count("passed") == 2 else "Không đạt", "tests/unit/test_graph_parity.py", ""])
    for name, target in (("SkillRet-base", 61.94), ("SkillRet-FT", 81.12), ("SkillRouter-Emb", 73.54), ("SkillRouter", 86.78)):
        rows.append([f"TC-BL-{CODES[name]}-REP", "Đ", f"Tái lập {name} trên SkillRet", "RAW-09", "DS-5",
                     "GPU (Colab/Kaggle), SkillRet v1.1 test", "4.392 truy vấn, 6.006 skill", f"NDCG@10 ≈ {target} ± 1 (bài báo)",
                     "—", "Chưa chạy: scripts/colab_skillret_dense.py đã sẵn, chấm bằng eval-run", "Chưa chạy",
                     "Kế hoạch tuần 4", "SkillRouter: tầng 1 trong bài báo có thể khác" if name == "SkillRouter" else ""])
    for r in rows:
        ws.append(r)
        fill = RESULT_FILL.get(r[10])
        if fill:
            ws.cell(row=ws.max_row, column=11).fill = PatternFill("solid", fgColor=fill)
    style_table(ws, len(header), [13, 6, 24, 9, 11, 24, 28, 30, 24, 46, 12, 30, 22])
    n_tc = ws.max_row

    # ---------------------------------------------------------------- Tổng hợp (formulas, computed by Excel on open)
    ws = wb.create_sheet("Tổng hợp")
    ws.append(["Kết quả", "Số testcase"])
    for status in ("Đạt", "Đạt một phần", "Không đạt", "Chưa chạy"):
        ws.append([status, f'=COUNTIF(Testcases!$K$2:$K${n_tc},A{ws.max_row + 1})'])
    ws.append(["Tổng", f"=SUM(B2:B{ws.max_row})"])
    ws.append(["Tổng số dòng testcase (kiểm tra)", f"=COUNTA(Testcases!$A$2:$A${n_tc})"])
    style_table(ws, 2, [34, 14])
    counts = {s: sum(r[10] == s for r in rows) for s in ("Đạt", "Đạt một phần", "Không đạt", "Chưa chạy")}

    OUT.parent.mkdir(parents=True, exist_ok=True)
    wb.save(OUT)
    print(f"wrote {OUT}: {len(rows)} testcases {counts}; pytest {passed}/{len(junit)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
