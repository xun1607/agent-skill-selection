"""Prepare and independently verify the payment reconciliation PoC.

No model calls are made by prepare/verify. Agent execution is a separate step.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skill_selection.registry.packages import content_id, file_manifest  # noqa: E402
from skill_selection.schemas import SkillRecord, QueryRecord
from skill_selection.selectors.mock_selector import MockSelector

FIXTURE = ROOT / "benchmarks" / "skill_poc"



def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def digest(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def workspace_manifest() -> list[dict]:
    return [entry for entry in file_manifest(FIXTURE / "workspace")
            if not {"__pycache__", ".pytest_cache"}.intersection(Path(entry["path"]).parts)]


def catalog_entries() -> list[dict]:
    lock = json.loads((ROOT / "config/registry/sources.lock.json").read_text(encoding="utf-8"))
    source = lock["sources"]["obra-superpowers"]
    return [json.loads(line) for line in (ROOT / source["inventory_ref"] / "profiles.jsonl").read_text(encoding="utf-8").splitlines()]


def selected_packages(skill_ids: list[str]) -> list[dict]:
    if not skill_ids:
        return []
    entries = {e["profile"]["skill_id"]: e for e in catalog_entries()}
    review = json.loads((FIXTURE / "skill-review.json").read_text(encoding="utf-8"))
    reviewed = {s["name"]: s for s in review["skills"]}
    result = []
    for skill_id in skill_ids:
        if skill_id not in entries:
            raise ValueError(f"unknown skill ID: {skill_id}")
        entry = entries[skill_id]
        profile = entry["profile"]
        if (profile["name"] not in reviewed or profile["source"]["commit"] != review["source_commit"]
                or profile["revision_id"] != reviewed[profile["name"]]["revision_id"]):
            raise ValueError(f"unreviewed skill revision: {skill_id}")
        if content_id(file_manifest(ROOT / entry["package_ref"])) != profile["revision_id"]:
            raise ValueError(f"skill package changed: {skill_id}")
        result.append(entry)
    return result


def exposure(run: Path, event: str, **fields):
    with (run / "exposure.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": utc(), "event": event, **fields}, ensure_ascii=False) + "\n")


def prepare(agent: str, mode: str, model: str, out_root: Path | None = None, skill_ids=(), selector=None) -> Path:
    if mode not in ("pre", "baseline"):
        raise ValueError("only pre-run provisioning is supported")
    if mode == "baseline" and skill_ids:
        raise ValueError("baseline requires an empty selection")
    task = (FIXTURE / "task.md").read_text(encoding="utf-8")
    selector = selector if selector is not None else MockSelector(skill_ids)
    selector.fit([SkillRecord(e["profile"]["skill_id"], e["profile"]["name"],
                             e["profile"]["description"], "", "obra-superpowers") for e in catalog_entries()])
    result = selector.select(QueryRecord("payment-reconciliation-v1", task, "skill-poc"), k=2)
    # Selection happens before package resolution, copying, or execution.
    entries = selected_packages(result.skill_ids)
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%S%fZ}-{agent}-{mode}"
    run = ((out_root or ROOT / "artifacts/skill-poc") / run_id).resolve()
    workspace = run / "workspace"
    shutil.copytree(FIXTURE / "workspace", workspace, ignore=shutil.ignore_patterns("__pycache__", ".pytest_cache"))
    subprocess.run(["git", "init", "-q", str(workspace)], check=True, capture_output=True)
    write(run / "workspace-before.json", workspace_manifest())
    exposure(run, "selected", result=result.to_dict())
    selected = []
    for entry in entries:
        profile = entry["profile"]
        target = workspace / ".poc_skills" / profile["name"]
        shutil.copytree(ROOT / entry["package_ref"], target)
        if content_id(file_manifest(target)) != profile["revision_id"]:
            raise ValueError("copied package hash mismatch")
        resource = {"skill_id": profile["skill_id"], "revision_id": profile["revision_id"],
                    "name": profile["name"], "source": profile["source"], "license": "MIT",
                    "path": (target / "SKILL.md").relative_to(workspace).as_posix(),
                    "skill_md_hash": digest(target / "SKILL.md"), "delivery": "pre"}
        selected.append(resource)
        exposure(run, "provided", **resource, readable_by_runner=os.access(target / "SKILL.md", os.R_OK))
    if selected:
        lock = json.loads((ROOT / "config/registry/sources.lock.json").read_text(encoding="utf-8"))
        source = lock["sources"]["obra-superpowers"]
        shutil.copyfile(ROOT / "data/raw/skill_sources/obra-superpowers" / source["commit"] / "repository/LICENSE",
                        workspace / ".poc_skills/UPSTREAM-LICENSE.txt")
        task += "\nExternal file-based context provisioning (not native skill loading). Read these selected SKILL.md files before working; apply relevant guidance with available tools:\n"
        task += "".join(f"- {r['path']}\n" for r in selected)
        task += "References to other skills do not provision or authorize them.\n"
    python = Path(sys.executable).resolve()
    task += (f"\nWork only in {workspace}. Python executable: {python}\n"
             "Do not inspect the enclosing repository or runner-only verifier. Do not install packages, access secrets, use network, delegate, or commit.\n"
             "Do not modify supplied tests or sample data. Run tests with python -m pytest -q -p no:cacheprovider .\n")
    task += "Shell: PowerShell; use & before a quoted executable.\n" if agent == "codex" else "Shell: cmd.exe; do not assume Unix utilities.\n"
    (run / "prompt.txt").write_text(task, encoding="utf-8")
    write(run / "decision.json", {"kind": "mock_selector_poc", "status": "selected" if selected else "no_skill",
                                  "result": result.to_dict(), "selected": selected})
    write(run / "manifest.json", {"run_id": run_id, "created_at": utc(), "purpose": "feasibility_poc",
          "eligible_for_training": False, "agent": agent, "mode": mode, "model_requested": model,
          "decision_hash": digest(run / "decision.json"), "python": str(python), "workspace": str(workspace), "task_id": "payment-reconciliation-v1",
          "task_hash": digest(FIXTURE / "task.md"), "prompt_hash": digest(run / "prompt.txt"),
          "workspace_manifest_hash": content_id(workspace_manifest()), "provisioning": "file-based",
          "default_skills_controlled": False})
    summarize(run)
    print(run)
    return run


def validate_prepared(run: Path, agent: str):
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    if manifest["agent"] != agent or manifest.get("provisioning") != "file-based":
        raise ValueError("prepare a fresh file-based run for this agent")
    if (run / "agent-status.json").exists() or (run / "execution.json").exists():
        raise ValueError("execution already attempted; prepare a fresh run")
    if digest(run / "prompt.txt") != manifest["prompt_hash"]:
        raise ValueError("prompt changed")
    if digest(run / "decision.json") != manifest["decision_hash"]:
        raise ValueError("decision changed")
    decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
    entries = selected_packages(decision["result"]["skill_ids"])
    if [e["profile"]["skill_id"] for e in entries] != [r["skill_id"] for r in decision["selected"]]:
        raise ValueError("decision/resources mismatch")
    expected = set()
    for entry, resource in zip(entries, decision["selected"]):
        canonical = ".poc_skills/" + entry["profile"]["name"] + "/SKILL.md"
        if resource["path"] != canonical or resource["revision_id"] != entry["profile"]["revision_id"]:
            raise ValueError("resource metadata changed")
        target = run / "workspace" / canonical
        if digest(target) != resource["skill_md_hash"] or content_id(file_manifest(target.parent)) != resource["revision_id"]:
            raise ValueError("provided package changed")
        expected.add(target.parent.name)
    folder = run / "workspace/.poc_skills"
    actual = {p.name for p in folder.iterdir() if p.is_dir()} if folder.exists() else set()
    if actual != expected or (not expected and folder.exists()):
        raise ValueError("unselected resources present")
    if folder.exists():
        expected_files = {"UPSTREAM-LICENSE.txt"}
        for entry in entries:
            expected_files.update(entry["profile"]["name"] + "/" + f["path"] for f in file_manifest(ROOT / entry["package_ref"]))
        if {f["path"] for f in file_manifest(folder)} != expected_files:
            raise ValueError("unselected resource files present")
    return manifest, decision


def summarize(run: Path):
    decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
    events = [json.loads(line) for line in (run / "exposure.jsonl").read_text(encoding="utf-8").splitlines()]
    status_path = run / "agent-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8")) if status_path.exists() else {}
    observed = {e["skill_id"] for e in events if e["event"] == "read_observed"}
    verification = run / "verifier-result.json"
    verdict = json.loads(verification.read_text(encoding="utf-8"))["status"] if verification.exists() else "not_run"
    summary = {"selected": decision["result"]["skill_ids"],
               "provided": [e["skill_id"] for e in events if e["event"] == "provided"],
               "read_status": {r["skill_id"]: "read_observed" if r["skill_id"] in observed else
                               "not_observed" if status.get("trace_available") else "unknown" for r in decision["selected"]},
               "execution": status, "task_passed": True if verdict == "pass" else False if verdict == "fail" else None,
               "integration": "PASS" if status.get("completed") and all(r["skill_id"] in observed for r in decision["selected"]) else "NOT_VERIFIED",
               "limits": "Read observation does not establish skill use, benefit, or native loading."}
    write(run / "summary.json", summary)
    (run / "summary.md").write_text("# Pre-run integration\n\n```json\n" + json.dumps(summary, indent=2) + "\n```\n", encoding="utf-8")
    return summary


def observe_read(run: Path, command: str, output: str, returncode: int, evidence_ref: str):
    if returncode != 0:
        return
    decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
    for resource in decision["selected"]:
        path = run / "workspace" / resource["path"]
        if not path.is_file() or digest(path) != resource["skill_md_hash"]:
            exposure(run, "read_unverified", skill_id=resource["skill_id"], reason="resource changed or missing")
            continue
        text = path.read_text(encoding="utf-8")
        # Conservative: successful command names the resource and returns its full text.
        if resource["name"] in command and "SKILL.md" in command and text.replace("\r\n", "\n").strip() in output.replace("\r\n", "\n"):
            exposure(run, "read_observed", skill_id=resource["skill_id"], evidence_ref=evidence_ref,
                     command=command, criterion="successful command plus full document output")


def run_codex(run: Path, executable="codex", timeout=600):
    run = run.resolve()
    manifest, _ = validate_prepared(run, "codex")
    command = [executable, "exec", "-C", str(run / "workspace"), "--sandbox", "workspace-write",
               "--json", "-m", manifest["model_requested"], "-o", str(run / "final.txt"), "-"]
    version = subprocess.run([executable, "--version"], capture_output=True, text=True).stdout.strip()
    write(run / "execution.json", {"started_at": utc(), "command": command, "cli_version": version})
    exposure(run, "agent_started", agent="codex", workspace=str(run / "workspace"))
    completed, error, exit_code = False, None, None
    try:
        with (run / "events.jsonl").open("w", encoding="utf-8") as stdout, (run / "stderr.log").open("w", encoding="utf-8") as stderr:
            process = subprocess.run(command, input=(run / "prompt.txt").read_text(encoding="utf-8"),
                                     stdout=stdout, stderr=stderr, text=True, encoding="utf-8", timeout=timeout)
        exit_code = process.returncode
    except (OSError, subprocess.TimeoutExpired) as exc:
        error = type(exc).__name__ + ": " + str(exc)
    for index, line in enumerate((run / "events.jsonl").read_text(encoding="utf-8").splitlines()):
        try:
            event = json.loads(line)
        except ValueError:
            continue
        completed |= event.get("type") == "turn.completed"
        item = event.get("item", {})
        if event.get("type") == "item.completed" and item.get("type") == "command_execution":
            observe_read(run, item.get("command", ""), item.get("aggregated_output", ""), item.get("exit_code"), f"events.jsonl:{index+1}")
    write(run / "agent-status.json", {"exit_code": exit_code, "completed": completed and exit_code == 0,
          "error": error, "trace_available": (run / "events.jsonl").stat().st_size > 0, "finished_at": utc()})
    verify(run)
    return summarize(run)


def verify(run: Path) -> dict:
    run = run.resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    before = json.loads((run / "workspace-before.json").read_text(encoding="utf-8"))
    workspace = run / "workspace"
    integrity = all((workspace / e["path"]).is_file() and digest(workspace / e["path"]) == e["sha256"]
                    for e in before if e["path"] in {"test_settlement.py", "example.csv"})
    checks = [{"check_id": "supplied_tests_and_sample_unchanged", "status": "pass" if integrity else "fail"}]
    start = datetime.now(timezone.utc)
    verification_dir = run / "verification" / start.strftime("%Y%m%dT%H%M%S%fZ")
    verification_dir.mkdir(parents=True)
    # Failures, including failed public tests, remain in the evidence. The
    # independent suite is never placed in the agent's original workspace.
    temporary_root = ROOT / "artifacts/skill-poc/_verifier_tmp"
    temporary_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="check-", dir=temporary_root) as directory:
        stage = Path(directory)
        (stage / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        shutil.copytree(workspace / "settlement", stage / "settlement", ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(FIXTURE / "workspace/example.csv", stage / "example.csv")
        shutil.copyfile(FIXTURE / "workspace/test_settlement.py", stage / "test_settlement.py")
        shutil.copyfile(FIXTURE / "verifier/test_acceptance.py", stage / "test_acceptance.py")
        env = dict(os.environ, PYTHONPATH=str(stage), PYTEST_DISABLE_PLUGIN_AUTOLOAD="1")
        env.pop("PYTEST_ADDOPTS", None)
        command = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-c", str(stage / "pytest.ini"),
                   "--rootdir", str(stage), "test_settlement.py", "test_acceptance.py"]
        try:
            completed = subprocess.run(command, cwd=stage, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
            log = completed.stdout + "\n" + completed.stderr
            status = "pass" if completed.returncode == 0 else "fail" if completed.returncode == 1 else "error"
            checks.append({"check_id": "public_and_independent_acceptance", "status": status, "message": f"pytest exit code {completed.returncode}"})
        except subprocess.TimeoutExpired as error:
            status = "timeout"
            log = str(error)
            checks.append({"check_id": "public_and_independent_acceptance", "status": "timeout"})
    (run / "verifier.log").write_text(log, encoding="utf-8")
    (verification_dir / "verifier.log").write_text(log, encoding="utf-8")
    if status == "pass" and not integrity:
        status = "fail"
    version = content_id({"acceptance": file_manifest(FIXTURE / "verifier"),
                          "public_test_hash": digest(FIXTURE / "workspace/test_settlement.py")})
    result = {"schema_version": "v1.0", "result_id": "vres-" + manifest["run_id"] + "-" + verification_dir.name, "run_id": manifest["run_id"],
              "task_id": manifest["task_id"], "verifier_id": "payment-reconciliation-pytest", "verifier_version": version,
              "status": status, "checks": checks, "evidence_ref": str(verification_dir / "verifier.log"),
              "environment_ref": f"python-{sys.version.split()[0]}-pytest-{__import__('pytest').__version__}",
              "duration_ms": int((datetime.now(timezone.utc) - start).total_seconds() * 1000), "started_at": start.isoformat().replace("+00:00", "Z")}
    from skill_selection.registry.contracts import validate_record
    validate_record("verifier-result", result)
    write(run / "verifier-result.json", result)
    write(verification_dir / "verifier-result.json", result)
    patches = []
    for original in sorted((FIXTURE / "workspace").rglob("*.py")):
        rel = original.relative_to(FIXTURE / "workspace")
        changed = workspace / rel
        patches.extend(difflib.unified_diff(original.read_text(encoding="utf-8").splitlines(True),
                       changed.read_text(encoding="utf-8-sig").splitlines(True) if changed.exists() else [],
                       fromfile="before/" + rel.as_posix(), tofile="after/" + rel.as_posix()))
    (run / "patch.diff").write_text("".join(patches), encoding="utf-8")
    (verification_dir / "patch.diff").write_text("".join(patches), encoding="utf-8")
    (run / "report.md").write_text(f"# PoC {manifest['run_id']}\n\nAgent: {manifest['agent']}; mode: {manifest['mode']}; requested model: {manifest['model_requested']}.\n\nIndependent verifier: **{status}**. See verifier.log.\n\nSkill use: **unknown pending trace review**. A passing verifier does not establish skill benefit or workflow compliance.\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prep = commands.add_parser("prepare")
    prep.add_argument("--agent", choices=["codex", "mini"], required=True)
    prep.add_argument("--mode", choices=["pre", "baseline"], default="pre")
    prep.add_argument("--model", required=True, help="Explicit requested model ID; not proof of actual model")
    prep.add_argument("--skill-id", action="append", default=[], help="Full registry ID; repeat for two skills")
    execute = commands.add_parser("run-codex")
    execute.add_argument("--run", type=Path, required=True)
    execute.add_argument("--codex", default="codex")
    check = commands.add_parser("verify")
    check.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare(args.agent, args.mode, args.model, skill_ids=args.skill_id)
    elif args.command == "run-codex":
        result = run_codex(args.run, args.codex)
        raise SystemExit(0 if result["integration"] == "PASS" else 1)
    else:
        result = verify(args.run)
        raise SystemExit(0 if result["status"] == "pass" else 1)


if __name__ == "__main__":
    main()
