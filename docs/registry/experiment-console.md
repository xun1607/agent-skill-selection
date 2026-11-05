# Local experiment console

`app/control_panel.py` is a local Streamlit dashboard for two bounded workflows:

1. Inspect the pinned registry inventory, package revisions, validation issues, `SKILL.md`, and resource manifests.
2. Run a curated SWE-bench task, inspect its trajectory, create a prediction, run the Docker evaluator, and inspect
   the report and test-output tail.

The registry page is read-only. A revision hash establishes package identity and integrity; it does not establish
correctness, safety, applicability, or benefit.

## Start

```powershell
Set-Location 'D:\PROJECT_GIT\agent_skill_selection'
$env:MINI_SWE_AGENT_ROOT = 'D:\path\to\mini-swe-agent'
& '.\.venv\Scripts\streamlit.exe' run app/control_panel.py
```

The app also accepts the mini-SWE-agent root in the run form. API credentials stay in the environment used by
mini-SWE-agent and are never copied into the console manifest.

## Run states

```text
CREATED
  -> AGENT_RUNNING
  -> AGENT_SUBMITTED | AGENT_FAILED
  -> EVALUATOR_RUNNING
  -> RESOLVED | UNRESOLVED | EVALUATOR_ERROR
```

- `AGENT_RUNNING` calls the configured model API and therefore requires explicit UI confirmation.
- The evaluator button is only shown for a non-empty submitted patch.
- `EVALUATOR_RUNNING` calls the SWE-bench harness with `python -X utf8`, one worker, and Docker. It does not call the
  model API.
- Every run receives a new directory under `artifacts/console/`; existing runs are not overwritten.

The worker writes stdout and stderr to stage-specific UTF-8 logs. The Streamlit process launches the worker with an
argument list rather than a shell command, and task IDs come from `config/console/tasks.yaml`.

## Verification without API or Docker

```powershell
& '.\.venv\Scripts\python.exe' -m pytest -q `
    tests/unit/test_console_registry.py `
    tests/unit/test_console_swebench.py
```

These tests cover registry path confinement, profile loading, task configuration, command construction, trajectory
summaries, prediction generation, evaluator arguments, and output tails. They create fake executable paths but never
launch them.
