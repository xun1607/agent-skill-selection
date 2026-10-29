"""Validate fixture and callback plumbing without a model call."""
from pathlib import Path
import shutil
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import agent_skill_poc as poc
from run_mini_skill_poc import failed_pytest


def run_fixture(tmp_path):
    run = tmp_path / "run"
    shutil.copytree(poc.FIXTURE / "workspace", run / "workspace")
    poc.write(run / "workspace-before.json", poc.workspace_manifest())
    poc.write(run / "manifest.json", {"run_id": "test-fixture", "agent": "fake", "mode": "pre", "model_requested": "none", "task_id": "payment-reconciliation-v1"})
    return run


def test_verifier_detects_the_seeded_bugs(tmp_path):
    run = run_fixture(tmp_path)
    result = poc.verify(run)
    assert result["status"] == "fail"
    assert "FAILED" in (run / "verifier.log").read_text(encoding="utf-8")


def test_verifier_accepts_a_correct_implementation(tmp_path):
    run = run_fixture(tmp_path)
    # Test oracle only; this implementation is never copied into agent inputs.
    (run / "workspace/settlement/report.py").write_text('''from decimal import Decimal, ROUND_HALF_UP

def summarize(payments):
    seen, customers = {}, {}
    for p in payments:
        payload = (p.customer_id, Decimal(p.amount), p.status)
        if p.txn_id in seen:
            if seen[p.txn_id] != payload:
                raise ValueError("conflicting transaction")
            continue
        seen[p.txn_id] = payload
        if p.status == "settled":
            cents = Decimal(p.amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            customers[p.customer_id] = customers.get(p.customer_id, Decimal("0")) + cents
    return {"customers": {k: f"{v:.2f}" for k, v in sorted(customers.items())},
            "total": f"{sum(customers.values(), Decimal('0')):.2f}"}
''', encoding="utf-8")
    result = poc.verify(run)
    assert result["status"] == "pass"
    assert "19 passed" in (run / "verifier.log").read_text(encoding="utf-8")
    assert "return" in (run / "patch.diff").read_text(encoding="utf-8")
    (run / "workspace/test_settlement.py").write_text("# tampered", encoding="utf-8")
    tampered = poc.verify(run)
    assert tampered["status"] == "fail"
    assert len(list((run / "verification").glob("*/verifier-result.json"))) == 2


def test_callback_needs_an_actual_failing_pytest_observation():
    message = {"extra": {"actions": [{"command": "python -m pytest -q"}]}}
    assert failed_pytest(message, [{"extra": {"returncode": 1, "raw_output": "2 failed, 1 passed"}}])
    assert not failed_pytest(message, [{"extra": {"returncode": 0, "raw_output": "3 passed"}}])
    assert not failed_pytest(message, [{"extra": {"returncode": 1, "raw_output": "python not found"}}])
    assert not failed_pytest({"extra": {"actions": [{"command": "echo failed"}]}}, [{"extra": {"returncode": 1, "raw_output": "failed"}}])


A = "obra-superpowers/skills/systematic-debugging"
B = "obra-superpowers/skills/verification-before-completion"
CASES = [[], [A], [B], [A, B]]


@pytest.mark.parametrize("agent", ["codex", "mini"])
@pytest.mark.parametrize("ids", CASES)
def test_preparation_matrix(tmp_path, agent, ids):
    import json
    from skill_selection.selectors.mock_selector import MockSelector
    calls = []
    class Tracked(MockSelector):
        def select(self, query, k):
            calls.append("select")
            return super().select(query, k)
    run = poc.prepare(agent, "pre", "fake", tmp_path, selector=Tracked(ids))
    assert calls == ["select"]
    _, decision = poc.validate_prepared(run, agent)
    assert decision["result"]["skill_ids"] == ids
    assert [r["skill_id"] for r in decision["selected"]] == ids
    prompt = (run / "prompt.txt").read_text(encoding="utf-8")
    assert "<selected_skill" not in prompt
    assert "# Systematic Debugging" not in prompt
    assert "# Verification Before Completion" not in prompt
    assert not list((run / "workspace").rglob("test_acceptance.py"))
    assert not (run / "workspace/.poc_skills").exists() if not ids else True
    assert poc.digest(poc.FIXTURE / "task.md") == json.loads((run / "manifest.json").read_text(encoding="utf-8"))["task_hash"]
    assert all(poc.digest(run / "workspace" / r["path"]) == r["skill_md_hash"] for r in decision["selected"])


@pytest.mark.parametrize("agent", ["codex", "mini"])
def test_invalid_id_fails_before_workspace_or_agent(tmp_path, monkeypatch, agent):
    monkeypatch.setattr(poc.subprocess, "run", lambda *a, **kw: pytest.fail("agent/process must not start"))
    with pytest.raises(ValueError, match="unknown skill ID"):
        poc.prepare(agent, "pre", "fake", tmp_path, skill_ids=["invalid"])
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("ids", CASES)
def test_codex_adapter_without_llm(tmp_path, monkeypatch, ids):
    import json
    from types import SimpleNamespace
    run = poc.prepare("codex", "pre", "fake", tmp_path, skill_ids=ids)
    real_subprocess = poc.subprocess.run
    def fake(command, **kwargs):
        if command[-1] == "--version":
            return SimpleNamespace(stdout="fake-codex", returncode=0)
        if "exec" not in command:
            return real_subprocess(command, **kwargs)
        assert command[command.index("-C")+1] == str(run / "workspace")
        decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
        for r in decision["selected"]:
            item = {"type": "command_execution", "command": "Get-Content " + r["path"],
                    "exit_code": 0, "aggregated_output": (run / "workspace" / r["path"]).read_text(encoding="utf-8")}
            kwargs["stdout"].write(json.dumps({"type": "item.completed", "item": item}) + "\n")
        kwargs["stdout"].write('{"type":"turn.completed"}\n')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(poc.subprocess, "run", fake)
    result = poc.run_codex(run)
    assert result["integration"] == "PASS"
    assert result["provided"] == ids
    assert result["task_passed"] is False  # fake agent did not repair task


@pytest.mark.parametrize("ids", CASES)
def test_mini_adapter_without_llm(tmp_path, monkeypatch, ids):
    import json
    from minisweagent.models.litellm_response_model import LitellmResponseModel
    from run_mini_skill_poc import run_mini
    run = poc.prepare("mini", "pre", "openai/fake", tmp_path, skill_ids=ids)
    decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
    commands = ["type " + r["path"].replace("/", "\\") for r in decision["selected"]]
    commands.append("echo COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT")
    def fake_query(self, messages, **kwargs):
        command = commands.pop(0)
        return {"role": "assistant", "content": "", "extra": {
            "actions": [{"command": command}], "cost": 0.0}}
    monkeypatch.setattr(LitellmResponseModel, "query", fake_query)
    result = run_mini(run, unattended=True)
    assert result["integration"] == "PASS"
    assert result["provided"] == ids
    assert result["task_passed"] is False


def test_unselected_or_tampered_resource_blocks_launch(tmp_path):
    run = poc.prepare("codex", "pre", "fake", tmp_path, skill_ids=[A])
    (run / "workspace/.poc_skills/unselected").mkdir()
    with pytest.raises(ValueError, match="unselected"):
        poc.validate_prepared(run, "codex")


def test_mid_rejected(tmp_path):
    with pytest.raises(ValueError, match="only pre-run"):
        poc.prepare("mini", "mid", "fake", tmp_path)


def test_read_requires_success_and_document_output(tmp_path):
    run = poc.prepare("mini", "pre", "fake", tmp_path, skill_ids=[A])
    import json
    r = json.loads((run / "decision.json").read_text(encoding="utf-8"))["selected"][0]
    command = "type " + r["path"]
    text = (run / "workspace" / r["path"]).read_text(encoding="utf-8")
    poc.observe_read(run, command, text, 1, "fake-failed")
    poc.observe_read(run, command, "permission denied", 0, "fake-no-content")
    poc.write(run / "agent-status.json", {"completed": True, "trace_available": True})
    result = poc.summarize(run)
    assert result["integration"] == "NOT_VERIFIED"
    assert result["read_status"][A] == "not_observed"


@pytest.mark.parametrize("agent", ["mini", "codex"])
def test_invalid_decision_blocks_adapter_before_process(tmp_path, monkeypatch, agent):
    import json
    run = poc.prepare(agent, "pre", "fake", tmp_path)
    decision = json.loads((run / "decision.json").read_text(encoding="utf-8"))
    decision["result"]["skill_ids"] = ["invalid"]
    poc.write(run / "decision.json", decision)
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    manifest["decision_hash"] = poc.digest(run / "decision.json")
    poc.write(run / "manifest.json", manifest)
    monkeypatch.setattr(poc.subprocess, "run", lambda *a, **kw: pytest.fail("process must not run"))
    with pytest.raises(ValueError, match="unknown skill ID"):
        if agent == "codex":
            poc.run_codex(run)
        else:
            from run_mini_skill_poc import run_mini
            run_mini(run, True)
