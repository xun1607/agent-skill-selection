"""Skill Explorer: giao diện quan sát cách chọn skill cho bộ nhiệm vụ GR1 (Streamlit).

Làm gì
  Ba khu vực: (1) 6 nhiệm vụ kèm trạng thái cổng kiểm định, (2) 41 skill có ô tìm kiếm và xem SKILL.md,
  (3) bảng xếp hạng skill cho nhiệm vụ đang chọn: hạng, điểm tương đồng, bị loại ở tầng ràng buộc môi trường hay
  không và lý do, đánh dấu 3 skill được chọn.

Đầu vào
  Chỉ hai tệp JSON đã tính sẵn (mặc định artifacts/explorer/, đổi bằng biến môi trường SKILL_EXPLORER_DIR):
    skill_index.json       python -m skill_selection index gr1
    selection_cache.json   python -m skill_selection select gr1 --seed 0 --ram-mode fixed:8192 --os windows --k 3
  Giao diện không tính embedding, không gọi API, không chạy thuật toán chọn: mở lại không tốn tiền, không cần mạng.

Đầu ra
  Trang web chạy trên máy:  streamlit run app/explorer.py
"""
import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get("SKILL_EXPLORER_DIR", ROOT / "artifacts" / "explorer"))
GATE_LABEL = {"passed": "✅ đạt", "failed": "❌ không đạt", "not_run": "⏳ chưa kiểm"}
FLAG_LABEL = {"skill_md_is_html": "SKILL.md là trang HTML tải nhầm",
              "description_is_fallback": "không có mô tả (GR1 tự điền)"}
KIND_LABEL = {"skill_md": "SKILL.md", "legacy_python": "Python (cũ)"}
COMMANDS = ("python -m skill_selection index gr1\n"
            "python -m skill_selection select gr1 --seed 0 --ram-mode fixed:8192 --os windows --k 3")

st.set_page_config(page_title="Skill Explorer", page_icon="🧭", layout="wide")


@st.cache_data
def _read_json(path: str, mtime: float):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load(name: str):
    path = DATA_DIR / name
    return _read_json(str(path), path.stat().st_mtime) if path.exists() else None


def split_front_matter(text: str) -> str:
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:])
    return text


index, selection = load("skill_index.json"), load("selection_cache.json")
if index is None or selection is None:
    st.error(f"Chưa có dữ liệu trong `{DATA_DIR}`. Chạy hai lệnh sau ở thư mục repo:\n\n```\n{COMMANDS}\n```")
    st.stop()

skills = {s["id"]: s for s in index["skills"]}
tasks = {t["id"]: t for t in index["tasks"]}

# ---------------------------------------------------------------- sidebar: what produced the numbers
with st.sidebar:
    st.header("Lần chạy")
    runs = {r["params"]["encoder"]: r for r in selection["runs"]}
    spec = st.selectbox("Bộ mã hoá", list(runs), format_func=lambda s: s.split("@")[0], key="encoder")
    run = runs[spec]
    p = run["params"]
    st.markdown(
        f"- **Mô hình:** `{spec.split('@')[0]}`\n"
        f"- **Revision:** `{spec.split('@')[-1][:12]}`\n"
        f"- **Văn bản skill:** `{p['representation']}`\n"
        f"- **k:** {p['k']}  ·  **seed:** {p['seed']}\n"
        f"- **RAM:** `{p['ram_mode']}`  ·  **OS:** `{p['os']}`\n"
        f"- **Tầng 1 loại:** {len(p['tier1_excluded'])} skill\n"
        f"- **Snapshot GR1:** `{(selection['snapshot'].get('gr1_commit') or '?')[:8]}`\n"
        f"- **Index:** `{(selection.get('index_sha256') or '?')[:12]}`")
    st.caption(p["seed_note"])
    prompt = index["encoders"].get(spec, {}).get("info", {}).get("query_prompt")
    if prompt:
        with st.expander("Prompt cho nhiệm vụ (query)"):
            st.code(prompt, language=None)
    if selection.get("index_created_at") != index.get("created_at"):
        st.warning("Kết quả chọn được tính từ một index cũ hơn. Chạy lại lệnh `select`.")

st.title("Skill Explorer")
st.caption(f"Bộ GR1: {len(skills)} skill, {len(tasks)} nhiệm vụ sửa lỗi. "
           "Dữ liệu tính sẵn bằng script; trang này chỉ đọc kết quả.")

# ---------------------------------------------------------------- area 1: tasks
st.subheader("① Nhiệm vụ")
st.dataframe(pd.DataFrame([{
    "Mã": t["id"], "Tiêu đề": t.get("title", ""),
    "Mô tả": t["text"] if len(t["text"]) <= 90 else t["text"][:87] + "...",
    "Ngôn ngữ": t.get("language", ""), "Cổng kiểm định": GATE_LABEL.get(t["gate"].get("status"), "?")}
    for t in tasks.values()]), hide_index=True)

task_id = st.selectbox("Chọn nhiệm vụ để xem kết quả chọn skill", list(tasks), key="task",
                       format_func=lambda i: f"{i} — {tasks[i].get('title', '')}")
task = tasks[task_id]
with st.expander("Chi tiết nhiệm vụ"):
    st.markdown(f"**Mô tả đầy đủ:** {task['text']}")
    st.markdown("**Tệp trong workspace (quan sát được trước khi chạy):** "
                + ", ".join(f"`{f}`" for f in task.get("workspace_files", [])))
    st.json(task["gate"], expanded=False)

left, right = st.columns([2, 3], gap="large")

# ---------------------------------------------------------------- area 2: skill library
with left:
    st.subheader("② Thư viện skill")
    query = st.text_input("Tìm theo tên, mô tả, nhóm", key="skill_search").strip().lower()
    shown = [s for s in skills.values()
             if not query or query in f"{s['id']} {s['description']} {s['category']}".lower()]
    st.caption(f"{len(shown)}/{len(skills)} skill")
    st.dataframe(pd.DataFrame([{
        "Skill": s["id"], "Nhóm": s["category"], "Loại": KIND_LABEL.get(s["kind"], s["kind"]),
        "Cảnh báo": "⚠" if s.get("quality_flags") else ""} for s in shown],
        columns=["Skill", "Nhóm", "Loại", "Cảnh báo"]), hide_index=True, height=260)

    if not shown:
        st.info("Không có skill nào khớp.")
    else:
        skill = skills[st.selectbox("Xem nội dung skill", [s["id"] for s in shown], key="skill")]
        st.markdown(f"**{skill['name']}** · `{skill['category']}`\n\n{skill['description']}")
        host = skill["constraints"].get("host") or {}
        res = skill["constraints"].get("resources") or {}
        st.caption(f"Ràng buộc: OS {', '.join(host.get('os') or ['bất kỳ'])} · RAM {res.get('memory', '—')}")
        for flag in skill.get("quality_flags", []):
            st.warning(f"⚠ {FLAG_LABEL.get(flag, flag)}")
        if skill.get("skill_md"):
            rendered, raw = st.tabs(["Nội dung", "Nguyên văn SKILL.md"])
            with rendered:
                with st.container(height=420):
                    st.markdown(split_front_matter(skill["skill_md"]))
            with raw:
                st.code(skill["skill_md"], language="markdown")
        elif skill.get("skill_md_omitted"):
            omitted = skill["skill_md_omitted"]
            st.warning(f"Nội dung không được chép vào repo: {omitted['note']}.  \n"
                       f"Tệp gốc `{omitted['gr1_path']}`, {omitted['bytes']:,} byte, sha256 `{omitted['sha256'][:16]}…`")
        else:
            st.info(f"Skill Python cũ, không có SKILL.md (`{skill.get('python_class', '')}`).")

# ---------------------------------------------------------------- area 3: selection for the chosen task
with right:
    st.subheader("③ Kết quả chọn")
    result = run["tasks"][task_id]
    st.success("Được chọn: " + " · ".join(f"**{s}**" for s in result["selected"]))
    table = pd.DataFrame([{
        "Hạng": r["rank"], "Skill": r["skill_id"], "Điểm": r["score"],
        "Bị loại (tầng 1)": "có" if r["excluded"] else "", "Lý do loại": r["reason"] or "",
        "Được chọn": "★" if r["selected"] else "",
        "Ghi chú": "⚠ " + "; ".join(FLAG_LABEL.get(f, f) for f in skills[r["skill_id"]].get("quality_flags", []))
                   if skills[r["skill_id"]].get("quality_flags") else ""} for r in result["ranking"]])
    table["Hạng"] = table["Hạng"].astype("Int64")

    def _row_style(row):
        if row["Được chọn"]:
            return ["background-color: rgba(46, 160, 67, 0.22); font-weight: 600"] * len(row)
        if row["Bị loại (tầng 1)"]:
            return ["color: rgba(128, 128, 128, 0.9)"] * len(row)
        return [""] * len(row)

    st.dataframe(table.style.apply(_row_style, axis=1).format({"Điểm": "{:.4f}"}), hide_index=True, height=560)
    st.caption("Điểm = cosine giữa mô tả nhiệm vụ và `name: description` của skill. Skill bị loại ở tầng 1 "
               "(ràng buộc OS / RAM) vẫn hiện điểm để đối chiếu nhưng không được xếp hạng.")
