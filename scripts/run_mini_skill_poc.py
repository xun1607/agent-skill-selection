"""Run an already prepared file-based pre-run PoC with mini Responses.

This command calls the configured model. It asks for tool confirmation by default.
"""
from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
from pathlib import Path
import sys

import yaml

from agent_skill_poc import digest, text_hash, utc, write, validate_prepared, exposure, observe_read, verify, summarize


def failed_pytest(message: dict, observations: list[dict]) -> bool:
    actions = (message.get("extra") or {}).get("actions", [])
    if not any("pytest" in a.get("command", "").lower() for a in actions):
        return False
    return any((m.get("extra") or {}).get("returncode") not in (None, 0)
               and "failed" in str((m.get("extra") or {}).get("raw_output", "")).lower()
               for m in observations)


def append_event(run: Path, event: dict) -> None:
    with (run / "delivery-events.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"at": utc(), **event}, ensure_ascii=False) + "\n")


def text_values(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from text_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from text_values(child)


def run_mini(run: Path, unattended: bool = False) -> dict:
    run = run.resolve()
    manifest, decision = validate_prepared(run, "mini")
    # Imports load mini's existing credential configuration. Never print secrets.
    from minisweagent import package_dir
    if unattended:
        from minisweagent.agents.default import DefaultAgent as AgentBase
    else:
        from minisweagent.agents.interactive import InteractiveAgent as AgentBase
    from minisweagent.environments.local import LocalEnvironment
    from minisweagent.models.litellm_response_model import LitellmResponseModel

    config = yaml.safe_load((package_dir / "config/mini.yaml").read_text(encoding="utf-8"))
    class AuditedResponses(LitellmResponseModel):
        def _query(self, messages, **kwargs):
            exposure(run, "model_request_attempt", agent="mini")
            response = super()._query(messages, **kwargs)
            exposure(run, "model_response_returned", model_returned=getattr(response, "model", None))
            return response

    class WorkflowAgent(AgentBase):
        def execute_actions(self, message):
            observations = super().execute_actions(message)
            actions = (message.get("extra") or {}).get("actions", [])
            for action, observation in zip(actions, observations):
                extra = observation.get("extra") or {}
                observe_read(run, action.get("command", ""), str(extra.get("raw_output", "")),
                             extra.get("returncode"), f"trajectory.json:step-{self.n_calls}")
            return observations

    agent_config = dict(config["agent"])
    agent_config.pop("agent_class", None)
    if not unattended:
        agent_config.update(mode="confirm", confirm_exit=False)
    agent_config.update(step_limit=20, cost_limit=0.5, wall_time_limit_seconds=300,
                        output_path=run / "trajectory.json")
    model_config = dict(config.get("model", {}))
    model_config.pop("model_class", None)
    model_config["model_name"] = manifest["model_requested"]
    model_config["model_kwargs"] = dict(model_config.get("model_kwargs", {}), timeout=30, num_retries=0)
    os.environ.setdefault("MSWEA_MODEL_RETRY_STOP_AFTER_ATTEMPT", "1")
    model = AuditedResponses(**model_config)
    env = LocalEnvironment(cwd=str(run / "workspace"), timeout=60)
    agent = WorkflowAgent(model, env, **agent_config)
    write(run / "execution.json", {"started_at": utc(), "mini_version": importlib.metadata.version("mini-swe-agent"),
                                   "litellm_version": importlib.metadata.version("litellm"), "backend": "litellm_response",
                                   "model_requested": manifest["model_requested"], "mode": "unattended" if unattended else "confirm",
                                   "step_limit": 20, "cost_limit_usd": 0.5,
                                   "wall_time_limit_seconds": 300,
                                   "local_environment_is_os_sandbox": False})
    exposure(run, "agent_started", agent="mini", workspace=str(run / "workspace"))
    result, error = {}, None
    try:
        result = agent.run((run / "prompt.txt").read_text(encoding="utf-8"))
    except Exception as exc:
        error = type(exc).__name__ + ": " + str(exc)
    finally:
        agent.save(run / "trajectory.json")
        exposure(run, "execution_finished")
    write(run / "agent-result.json", result)
    completed = result.get("exit_status") == "Submitted"
    write(run / "agent-status.json", {"completed": completed, "exit_code": 0 if completed else 1,
          "exit_status": result.get("exit_status"), "error": error,
          "trace_available": (run / "trajectory.json").exists(), "finished_at": utc()})
    (run / "stderr.log").write_text(error or "", encoding="utf-8")
    verify(run)
    return summarize(run)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--unattended", action="store_true", help="Execute without per-command confirmation")
    args = parser.parse_args()
    result = run_mini(args.run, args.unattended)
    raise SystemExit(0 if result["integration"] == "PASS" else 1)


if __name__ == "__main__":
    main()
