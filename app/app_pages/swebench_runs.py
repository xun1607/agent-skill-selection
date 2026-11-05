from __future__ import annotations

import json
import os
from pathlib import Path
import re
import subprocess
import sys

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from skill_selection.console.swebench import (  # noqa: E402
    create_run,
    load_tasks,
    read_manifest,
    tail,
    trajectory_steps,
)

RUNS = ROOT / "artifacts/console"
TASKS = ROOT / "config/console/tasks.yaml"
RUNNING = {"AGENT_RUNNING", "EVALUATOR_RUNNING"}
EVALUATED = {"RESOLVED", "UNRESOLVED", "EVALUATOR_ERROR", "INFRA_FAILURE", "AMBIGUOUS_FAILURE"}
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def launch(stage: str, run: Path) -> None:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    with (run / "worker.log").open("a", encoding="utf-8") as output:
        subprocess.Popen(
            [sys.executable, "-m", "skill_selection.console.worker", stage, "--run", str(run)],
            cwd=ROOT,
            env=env,
            stdout=output,
            stderr=subprocess.STDOUT,
            creationflags=flags,
            start_new_session=os.name != "nt",
        )


def stage_badges(state: str) -> None:
    agent_done = state not in {"CREATED", "AGENT_RUNNING", "AGENT_FAILED"}
    evaluator_done = state in EVALUATED
    with st.container(horizontal=True):
        st.badge("1 · Configure", color="green")
        st.badge("2 · Agent complete" if agent_done else "2 · Agent", color="green" if agent_done else "blue")
        st.badge("3 · Evaluate" if not evaluator_done else "3 · Evaluation complete",
                 color="green" if evaluator_done else "gray")


def run_history() -> tuple[Path | None, dict | None]:
    manifests = sorted(RUNS.glob("*/manifest.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not manifests:
        return None, None
    entries = {path.parent.name: read_manifest(path.parent) for path in manifests}
    run_id = st.selectbox(
        "Run",
        list(entries),
        key="existing_run",
        format_func=lambda value: f"{entries[value]['state']} · {entries[value]['task']['instance_id']} · {value}",
    )
    run = RUNS / run_id
    return run, entries[run_id]


def test_counts(text: str) -> dict[str, int]:
    result = {}
    for label in ("passed", "failed", "skipped", "errors"):
        matches = re.findall(rf"(\d+)\s+{label}", text, flags=re.IGNORECASE)
        if matches:
            result[label] = int(matches[-1])
    return result


def status_banner(state: str) -> None:
    if state == "RESOLVED":
        st.success("Resolved — the submitted patch passed the SWE-bench evaluator.", icon=":material/check_circle:")
    elif state == "UNRESOLVED":
        st.error("Unresolved — evaluation completed, but one or more required tests failed.", icon=":material/cancel:")
    elif state in RUNNING:
        st.info(f"{state.replace('_', ' ').title()} — refresh this page to update the evidence.", icon=":material/pending:")
    elif state == "AGENT_FAILED":
        return
    elif state in {"EVALUATOR_ERROR", "INFRA_FAILURE", "AMBIGUOUS_FAILURE"}:
        st.warning(state.replace("_", " ").title(), icon=":material/warning:")
    else:
        st.info(state.replace("_", " ").title(), icon=":material/info:")


@st.fragment(run_every="2s")
def live_trace(run: Path) -> None:
    state = read_manifest(run)["state"]
    if state not in RUNNING:
        st.rerun()
    agent_stage = state == "AGENT_RUNNING"
    log = run / ("agent.log" if agent_stage else "evaluator.log")
    st.subheader("Live agent output" if agent_stage else "Live evaluator output", icon=":material/terminal:")
    st.caption("Output cập nhật tự động mỗi 2 giây. Trajectory JSON được lưu sau khi agent kết thúc." if agent_stage
               else "Evaluator đang chạy Docker; log cập nhật tự động mỗi 2 giây.")
    st.code(ANSI.sub("", tail(log, 120)) or "Đang khởi động tiến trình...", language=None, height=360)


def trajectory_view(run: Path, summary: dict) -> None:
    trajectory = run / "trajectory.json"
    if not trajectory.is_file():
        st.info("Trajectory is not available yet.", icon=":material/pending:")
        return
    steps = trajectory_steps(trajectory)
    with st.container(horizontal=True):
        st.metric("Commands", summary.get("commands", 0), border=True)
        st.metric("Failed commands", summary.get("failed_commands", 0), border=True)
        st.metric("Test commands", summary.get("test_commands", 0), border=True)
        st.metric("Patch size", f"{summary.get('patch_chars', 0):,} chars", border=True)

    initial = [step for step in steps if step["role"] in {"system", "user"}]
    execution = [step for step in steps if step["role"] not in {"system", "user"}]
    with st.expander("Initial context", icon=":material/description:"):
        for step in initial:
            st.markdown(f"**{step['role'].title()} message**")
            st.code(step["content"][-8000:], language=None)

    mode = st.pills(
        "Show steps",
        ["All", "Commands", "Failures", "Tests", "Submission"],
        default="All",
        selection_mode="single",
        key=f"trajectory_filter_{run.name}",
    )
    for step in execution:
        commands = step["commands"]
        is_failure = step["returncode"] not in (None, 0) or "<exception>" in step["content"]
        is_test = any(any(word in command.lower() for word in ("pytest", "tox", "unittest")) for command in commands)
        is_submission = step["role"] == "exit"
        if mode == "Commands" and not commands:
            continue
        if mode == "Failures" and not is_failure:
            continue
        if mode == "Tests" and not is_test:
            continue
        if mode == "Submission" and not is_submission:
            continue
        label = f"Step {step['step']} · {step['role']}"
        if step["returncode"] is not None:
            label += f" · return code {step['returncode']}"
        with st.expander(label, icon=":material/terminal:"):
            for command in commands:
                st.code(command, language="bash")
            if step["content"]:
                st.code(step["content"][-6000:], language=None)


def evaluation_view(run: Path, manifest: dict) -> None:
    state = manifest["state"]
    if state == "AGENT_SUBMITTED":
        with st.container(border=True):
            st.subheader("Patch ready for evaluation", icon=":material/fact_check:")
            st.caption("The evaluator uses Docker and does not call the model API.")
            if st.button("Run evaluator", type="primary", icon=":material/play_arrow:", key=f"evaluate-{run.name}"):
                launch("evaluator", run)
                st.rerun()
        return
    if state not in EVALUATED and state != "EVALUATOR_RUNNING":
        st.info("Evaluation becomes available after the agent submits a non-empty patch.", icon=":material/lock:")
        return

    report = manifest.get("evaluator_summary", {})
    if report:
        with st.container(horizontal=True):
            st.metric("Resolved", report.get("resolved_instances", 0), border=True)
            st.metric("Unresolved", report.get("unresolved_instances", 0), border=True)
            st.metric("Infrastructure failures", report.get("infra_failure_instances", 0), border=True)
            st.metric("Errors", report.get("error_instances", 0), border=True)

    test_outputs = sorted(run.rglob("test_output.txt"), key=lambda path: path.stat().st_mtime, reverse=True)
    if test_outputs:
        output = test_outputs[0].read_text(encoding="utf-8", errors="replace")
        counts = test_counts(output)
        if counts:
            with st.container(horizontal=True):
                for label in ("passed", "failed", "skipped", "errors"):
                    if label in counts:
                        st.metric(label.title(), counts[label], border=True)
        lines = st.select_slider("Test output tail", options=[50, 100, 200, 500], value=100)
        st.code("\n".join(output.splitlines()[-lines:]), language=None)
    else:
        st.caption("No `test_output.txt` is available for this run.")

    with st.expander("Evaluator log", icon=":material/terminal:"):
        st.code(tail(run / "evaluator.log", 200) or "Evaluator log has not been created yet.", language=None)
    if report:
        with st.expander("Full evaluator report", icon=":material/data_object:"):
            st.json(report, expanded=False)


st.caption("Run curated coding-agent tasks, inspect trajectory evidence, and evaluate submitted patches.")
st.info("Agent runs call the configured model API. Evaluator runs use Docker and no model tokens.", icon=":material/info:")

tasks = load_tasks(TASKS)
by_id = {task["id"]: task for task in tasks}
configs = sorted((ROOT / "experiments/configs").glob("*.yaml"))
config_options = {"No skill overlay": None, **{path.name: path for path in configs}}

st.header("Configure an agent run", icon=":material/tune:")
with st.form("create_agent_run", border=True):
    task_id = st.selectbox(
        "Task",
        list(by_id),
        format_func=lambda value: f"{by_id[value]['category']} — {by_id[value]['instance_id']}",
    )
    st.caption(by_id[task_id]["description"])
    left, right = st.columns(2)
    with left:
        model = st.text_input("Model", value="openai/gpt-5.4-mini")
        config_name = st.selectbox("Skill condition", list(config_options))
    with right:
        mini_root = st.text_input(
            "mini-SWE-agent root",
            value=os.environ.get("MINI_SWE_AGENT_ROOT", ""),
            placeholder=r"D:\path\to\mini-swe-agent",
        )
        cost_limit = st.number_input("Cost limit (USD)", min_value=0.01, max_value=5.0, value=0.5, step=0.05)
    confirmed = st.checkbox("I understand that this stage calls the configured model API and may incur cost.")
    submitted = st.form_submit_button(
        "Run agent",
        type="primary",
        icon=":material/play_arrow:"
        )

if submitted:
    if not confirmed:
        st.error("Confirm the API cost before running.")
    else:
        try:
            run = create_run(ROOT, by_id[task_id], model, Path(mini_root), cost_limit, config_options[config_name])
            launch("agent", run)
        except (OSError, ValueError) as error:
            st.error(str(error), icon=":material/error:")
        else:
            st.session_state.existing_run = run.name
            st.rerun()

st.header("Run history", icon=":material/history:")
run, manifest = run_history()
if run is None or manifest is None:
    st.info("No console runs exist yet. Configure the first agent run above.", icon=":material/science:")
    st.stop()

stage_badges(manifest["state"])
status_banner(manifest["state"])
if manifest["state"] in RUNNING:
    live_trace(run)
elif manifest["state"] == "AGENT_FAILED":
    if (run / "trajectory.json").is_file():
        exit_status = manifest.get("trajectory_summary", {}).get("exit_status", "unknown")
        st.warning(f"Agent đã lưu trajectory nhưng không nộp patch. Exit status: {exit_status}.")
        if exit_status == "RepeatedFormatError":
            st.caption("Model liên tiếp trả phản hồi không có tool call; lượt này không thể đưa vào evaluator.")
    else:
        st.error("Agent dừng trước khi lưu trajectory. Xem log cuối bên dưới.")
        st.code(ANSI.sub("", tail(run / "agent.log", 35)) or manifest.get("error", "Không có agent log."),
                language=None, height=240)

summary = manifest.get("trajectory_summary", {})
with st.container(horizontal=True):
    st.metric("Exit status", summary.get("exit_status", "—"), border=True)
    st.metric("API calls", summary.get("api_calls", "—"), border=True)
    cost = summary.get("cost")
    st.metric("Cost", f"${cost:.5f}" if cost is not None else "—", border=True)
    st.metric("Patch", f"{summary.get('patch_chars', 0):,} chars" if summary else "—", border=True)

st.caption(
    f"Task `{manifest['task']['instance_id']}` · model `{manifest['model']}` · "
    f"skill `{Path(manifest['skill_config']).name if manifest.get('skill_config') else 'none'}`"
)
with st.container(horizontal=True):
    if st.button("Refresh", icon=":material/refresh:", key=f"refresh-{run.name}"):
        st.rerun()

overview, trajectory_tab, evaluation_tab, artifacts_tab = st.tabs(["Overview", "Trajectory", "Evaluation", "Artifacts"])
with overview:
    st.table({
        ":material/tag: Run ID": manifest["run_id"],
        ":material/category: Category": manifest["task"]["category"],
        ":material/smart_toy: Model": manifest["model"],
        ":material/attach_money: Cost limit": f"${manifest['cost_limit']:.2f}",
        ":material/schedule: Created": manifest["created_at"],
    }, border="horizontal", width="content")
    if summary.get("patch"):
        with st.expander("Submitted patch", icon=":material/difference:"):
            st.code(summary["patch"], language="diff")
    with st.expander("Agent log", icon=":material/terminal:"):
        st.code(tail(run / "agent.log", 200) or "Agent log has not been created yet.", language=None)
    if (run / "worker.log").is_file():
        with st.expander("Worker diagnostics", icon=":material/build:"):
            st.code(tail(run / "worker.log", 100), language=None)
with trajectory_tab:
    trajectory_view(run, summary)
with evaluation_tab:
    evaluation_view(run, manifest)
with artifacts_tab:
    files = [path for path in run.rglob("*") if path.is_file()]
    st.dataframe(
        [{"File": path.relative_to(run).as_posix(), "Bytes": path.stat().st_size} for path in files],
        hide_index=True,
        width="stretch",
        column_config={
            "File": st.column_config.TextColumn(pinned=True),
            "Bytes": st.column_config.NumberColumn(format="localized"),
        },
        alt=f"Files recorded for run {manifest['run_id']}",
    )
