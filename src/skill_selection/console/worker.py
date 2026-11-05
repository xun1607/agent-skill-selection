from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess

from .swebench import (
    agent_command,
    create_prediction,
    evaluator_command,
    parse_trajectory,
    read_manifest,
    update_manifest,
)


def _run(command: list[str], cwd: Path, log: Path) -> int:
    with log.open("w", encoding="utf-8", newline="\n") as output:
        return subprocess.run(
            command,
            cwd=cwd,
            env={**os.environ, "PYTHONUNBUFFERED": "1", "PYTHONIOENCODING": "utf-8"},
            stdout=output,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
        ).returncode


def run_agent(run: Path) -> None:
    manifest = read_manifest(run)
    command = agent_command(run, manifest)
    update_manifest(run, state="AGENT_RUNNING", agent_command=command)
    returncode = _run(command, Path(manifest["mini_root"]), run / "agent.log")
    try:
        summary = parse_trajectory(run / "trajectory.json")
    except (OSError, ValueError, json.JSONDecodeError) as error:
        update_manifest(run, state="AGENT_FAILED", agent_returncode=returncode, error=str(error))
        return
    submitted = returncode == 0 and summary["exit_status"] == "Submitted" and summary["patch_chars"]
    update_manifest(
        run,
        state="AGENT_SUBMITTED" if submitted else "AGENT_FAILED",
        agent_returncode=returncode,
        trajectory_summary=summary,
    )


def run_evaluator(run: Path) -> None:
    manifest = read_manifest(run)
    prediction, label = create_prediction(run, manifest)
    command, eval_id = evaluator_command(run, manifest, prediction)
    update_manifest(
        run,
        state="EVALUATOR_RUNNING",
        evaluator_command=command,
        evaluator_run_id=eval_id,
        prediction=str(prediction),
        model_label=label,
    )
    returncode = _run(command, run, run / "evaluator.log")
    report = run / f"{label}.{eval_id}.json"
    if not report.is_file():
        update_manifest(
            run,
            state="EVALUATOR_ERROR",
            evaluator_returncode=returncode,
            error="evaluator report was not created",
        )
        return
    result = json.loads(report.read_text(encoding="utf-8"))
    if returncode != 0 or result.get("error_instances", 0):
        state = "EVALUATOR_ERROR"
    elif result.get("infra_failure_instances", 0):
        state = "INFRA_FAILURE"
    elif result.get("ambiguous_failure_instances", 0):
        state = "AMBIGUOUS_FAILURE"
    elif manifest["task"]["instance_id"] in result.get("resolved_ids", []):
        state = "RESOLVED"
    else:
        state = "UNRESOLVED"
    update_manifest(
        run,
        state=state,
        evaluator_returncode=returncode,
        report=str(report),
        evaluator_summary=result,
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("agent", "evaluator"))
    parser.add_argument("--run", type=Path, required=True)
    args = parser.parse_args()
    run = args.run.resolve()
    lock = run / f".{args.stage}.lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError:
        raise SystemExit(f"{args.stage} stage was already launched") from None
    try:
        {"agent": run_agent, "evaluator": run_evaluator}[args.stage](run)
    except Exception as error:
        state = "AGENT_FAILED" if args.stage == "agent" else "EVALUATOR_ERROR"
        update_manifest(run, state=state, error=f"{type(error).__name__}: {error}")
        raise


if __name__ == "__main__":
    main()
