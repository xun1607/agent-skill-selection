from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
import secrets
from typing import Any

import yaml

RUN_ID = re.compile(r"^[A-Za-z0-9_.-]+$")
EVALUATOR_DATASETS = {
    "lite": "SWE-bench/SWE-bench_Lite",
    "verified": "SWE-bench/SWE-bench_Verified",
}


def utc() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    temporary.replace(path)


def load_tasks(path: Path) -> list[dict]:
    rows = yaml.safe_load(path.read_text(encoding="utf-8"))["tasks"]
    required = {"id", "instance_id", "category", "subset", "split"}
    if not rows or any(set(row) < required for row in rows):
        raise ValueError("every task needs id, instance_id, category, subset, and split")
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("duplicate task id")
    return rows


def create_run(root: Path, task: dict, model: str, mini_root: Path, cost_limit: float,
               skill_config: Path | None = None) -> Path:
    if not (0 < cost_limit <= 5):
        raise ValueError("cost limit must be between 0 and 5 USD")
    mini_root = mini_root.resolve()
    if not (mini_root / ".venv/Scripts/mini-extra.exe").is_file() or not (mini_root / ".venv/Scripts/python.exe").is_file():
        raise ValueError("mini-SWE-agent virtual environment was not found")
    if skill_config is not None and not skill_config.resolve().is_file():
        raise ValueError("skill config was not found")
    run_id = f"{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{task['id']}-{secrets.token_hex(3)}"
    if not RUN_ID.fullmatch(run_id):
        raise ValueError("unsafe run id")
    run = root / "artifacts/console" / run_id
    run.mkdir(parents=True)
    write_json(run / "manifest.json", {
        "schema_version": 1,
        "run_id": run_id,
        "created_at": utc(),
        "updated_at": utc(),
        "state": "CREATED",
        "task": task,
        "model": model,
        "cost_limit": cost_limit,
        "mini_root": str(mini_root),
        "skill_config": str(skill_config.resolve()) if skill_config else None,
    })
    return run


def read_manifest(run: Path) -> dict:
    return json.loads((run / "manifest.json").read_text(encoding="utf-8"))


def update_manifest(run: Path, **changes) -> dict:
    manifest = read_manifest(run)
    manifest.update(changes, updated_at=utc())
    write_json(run / "manifest.json", manifest)
    return manifest


def agent_command(run: Path, manifest: dict) -> list[str]:
    mini_root = Path(manifest["mini_root"])
    command = [
        str(mini_root / ".venv/Scripts/mini-extra.exe"), "swebench-single",
        "--subset", manifest["task"]["subset"],
        "--split", manifest["task"]["split"],
        "--instance", manifest["task"]["instance_id"],
        "--model", manifest["model"],
        "--config", "swebench.yaml",
    ]
    if manifest.get("skill_config"):
        command += ["--config", manifest["skill_config"]]
    return command + [
        "--config", "environment.pull_timeout=900",
        "--cost-limit", str(manifest["cost_limit"]),
        "--yolo", "--exit-immediately",
        "--output", str((run / "trajectory.json").resolve()),
    ]


def parse_trajectory(path: Path) -> dict:
    trajectory = json.loads(path.read_text(encoding="utf-8"))
    info = trajectory.get("info", {})
    stats = info.get("model_stats", {})
    messages = trajectory.get("messages", [])
    commands, failed_commands, test_commands = 0, 0, 0
    for message in messages:
        for call in message.get("tool_calls") or []:
            arguments = json.loads(call.get("function", {}).get("arguments", "{}"))
            command = str(arguments.get("command", ""))
            commands += 1
            test_commands += int(any(word in command.lower() for word in ("pytest", "tox", "unittest")))
        if message.get("role") == "tool" and "<returncode>" in str(message.get("content")):
            failed_commands += int(not re.search(r"<returncode>0</returncode>", str(message.get("content"))))
    patch = str(info.get("submission") or "")
    return {
        "exit_status": info.get("exit_status"),
        "api_calls": stats.get("api_calls"),
        "cost": stats.get("instance_cost"),
        "patch_chars": len(patch),
        "patch": patch,
        "commands": commands,
        "failed_commands": failed_commands,
        "test_commands": test_commands,
        "messages": len(messages),
    }


def trajectory_steps(path: Path) -> list[dict]:
    messages = json.loads(path.read_text(encoding="utf-8")).get("messages", [])
    steps = []
    for index, message in enumerate(messages, 1):
        commands = []
        for call in message.get("tool_calls") or []:
            arguments = json.loads(call.get("function", {}).get("arguments", "{}"))
            if arguments.get("command"):
                commands.append(arguments["command"])
        content = str(message.get("content") or "")
        match = re.search(r"<returncode>(-?\d+)</returncode>", content)
        steps.append({
            "step": index,
            "role": message.get("role"),
            "commands": commands,
            "returncode": int(match.group(1)) if match else None,
            "content": content,
        })
    return steps


def create_prediction(run: Path, manifest: dict) -> tuple[Path, str]:
    summary = parse_trajectory(run / "trajectory.json")
    if summary["exit_status"] != "Submitted" or not summary["patch"]:
        raise ValueError("trajectory has no submitted patch")
    label = "console"
    path = run / "prediction.json"
    write_json(path, [{
        "instance_id": manifest["task"]["instance_id"],
        "model_name_or_path": label,
        "model_patch": summary["patch"],
    }])
    return path, label


def evaluator_command(run: Path, manifest: dict, prediction: Path) -> tuple[list[str], str]:
    eval_id = "eval"
    python = Path(manifest["mini_root"]) / ".venv/Scripts/python.exe"
    subset = manifest["task"]["subset"]
    if subset not in EVALUATOR_DATASETS:
        raise ValueError(f"no evaluator dataset configured for subset {subset!r}")
    return [
        str(python), "-X", "utf8", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", EVALUATOR_DATASETS[subset],
        "--split", manifest["task"]["split"],
        "--instance_ids", manifest["task"]["instance_id"],
        "--predictions_path", str(prediction.resolve()),
        "--max_workers", "1", "--timeout", "1800", "--run_id", eval_id,
    ], eval_id


def tail(path: Path, lines: int = 100) -> str:
    if not path.is_file():
        return ""
    return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
