import json
from pathlib import Path

from skill_selection.console.swebench import (
    agent_command,
    create_prediction,
    create_run,
    evaluator_command,
    load_tasks,
    parse_trajectory,
    read_manifest,
    tail,
    trajectory_steps,
)


TASK = {
    "id": "example",
    "instance_id": "owner__repo-1",
    "category": "Medium",
    "subset": "verified",
    "split": "test",
}


def mini_root(tmp_path):
    root = tmp_path / "mini"
    scripts = root / ".venv/Scripts"
    scripts.mkdir(parents=True)
    (scripts / "mini-extra.exe").touch()
    (scripts / "python.exe").touch()
    return root


def trajectory(path):
    value = {
        "info": {
            "exit_status": "Submitted",
            "model_stats": {"api_calls": 3, "instance_cost": 0.012},
            "submission": "diff --git a/a.py b/a.py\n",
        },
        "messages": [
            {"role": "assistant", "content": None, "tool_calls": [{
                "function": {"arguments": json.dumps({"command": "python -m pytest -q"})}
            }]},
            {"role": "tool", "content": "<returncode>1</returncode><output>failed</output>"},
        ],
    }
    path.write_text(json.dumps(value), encoding="utf-8")


def test_task_config_requires_unique_complete_rows(tmp_path):
    path = tmp_path / "tasks.yaml"
    path.write_text("tasks:\n  - id: one\n    instance_id: owner__repo-1\n    category: Easy\n    subset: verified\n    split: test\n", encoding="utf-8")
    assert load_tasks(path) == [{**TASK, "id": "one", "category": "Easy"}]


def test_run_commands_prediction_and_trajectory_summary(tmp_path):
    skill = tmp_path / "skill.yaml"
    skill.write_text("agent: {}\n", encoding="utf-8")
    mini = mini_root(tmp_path)
    run = create_run(tmp_path, TASK, "openai/test", mini, 0.5, skill)
    manifest = read_manifest(run)
    command = agent_command(run, manifest)
    assert command[command.index("--instance") + 1] == "owner__repo-1"
    assert command[command.index("--model") + 1] == "openai/test"
    assert str(skill.resolve()) in command

    trajectory(run / "trajectory.json")
    summary = parse_trajectory(run / "trajectory.json")
    assert summary | {"patch": None} == {
        "exit_status": "Submitted",
        "api_calls": 3,
        "cost": 0.012,
        "patch_chars": 25,
        "patch": None,
        "commands": 1,
        "failed_commands": 1,
        "test_commands": 1,
        "messages": 2,
    }
    assert trajectory_steps(run / "trajectory.json")[1]["returncode"] == 1

    prediction, label = create_prediction(run, manifest)
    row = json.loads(prediction.read_text(encoding="utf-8"))[0]
    assert row["instance_id"] == "owner__repo-1"
    assert row["model_patch"].startswith("diff --git")
    evaluator, eval_id = evaluator_command(run, manifest, prediction)
    assert evaluator[:4] == [str(mini / ".venv/Scripts/python.exe"), "-X", "utf8", "-m"]
    assert eval_id == "eval"
    assert label == "console"


def test_tail_handles_missing_and_limits_lines(tmp_path):
    path = tmp_path / "output.txt"
    assert tail(path, 2) == ""
    path.write_text("one\ntwo\nthree\n", encoding="utf-8")
    assert tail(path, 2) == "two\nthree"


def test_curated_marshmallow_uses_lite_dev_for_agent_and_evaluator(tmp_path):
    root = Path(__file__).resolve().parents[2]
    task = next(row for row in load_tasks(root / "config/console/tasks.yaml") if row["id"] == "marshmallow-easy")
    run = create_run(tmp_path, task, "openai/test", mini_root(tmp_path), 0.5)
    manifest = read_manifest(run)
    command = agent_command(run, manifest)
    evaluator, _ = evaluator_command(run, manifest, run / "prediction.json")
    assert command[command.index("--subset") + 1:command.index("--subset") + 2] == ["lite"]
    assert command[command.index("--split") + 1:command.index("--split") + 2] == ["dev"]
    assert evaluator[evaluator.index("--dataset_name") + 1:evaluator.index("--dataset_name") + 2] == ["SWE-bench/SWE-bench_Lite"]
    assert evaluator[evaluator.index("--split") + 1:evaluator.index("--split") + 2] == ["dev"]
