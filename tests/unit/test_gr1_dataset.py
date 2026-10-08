import pytest

from skill_selection.datasets.gr1 import TASK_METADATA_FIELDS, load_gr1, verify_manifest
from skill_selection.filters.constraint import Environment, apply_constraints


@pytest.fixture(scope="module")
def bench():
    return load_gr1()


def test_counts(bench):
    assert len(bench.skills) == 41
    assert len({s.id for s in bench.skills}) == 41
    assert sum(s.metadata["kind"] == "skill_md" for s in bench.skills) == 39
    assert len(bench.tasks) == 6


def test_skill_md_files(bench):
    for skill in bench.skills:
        text = bench.skill_md(skill)
        if skill.metadata["kind"] != "skill_md" or "skill_md_is_html" in skill.metadata.get("quality_flags", []):
            assert text is None
        else:
            assert text.lstrip().startswith("---")


def test_known_gr1_defects_are_flagged(bench):
    flagged = {s.id: s.metadata["quality_flags"] for s in bench.skills if s.metadata.get("quality_flags")}
    assert flagged == {"custom-imported-skill": ["skill_md_is_html", "description_is_fallback"]}


def test_html_page_content_not_republished(bench):
    skill = next(s for s in bench.skills if s.id == "custom-imported-skill")
    omitted = skill.metadata["skill_md_omitted"]
    assert len(omitted["sha256"]) == 64 and omitted["bytes"] > 0
    assert skill.body == "" and "skill_md_path" not in skill.metadata
    for path in bench.root.rglob("*"):
        if path.is_file():
            assert "<!DOCTYPE html" not in path.read_text(encoding="utf-8", errors="ignore"), path


def test_tasks_expose_no_gold(bench):
    for task in bench.tasks:
        assert set(task.metadata) <= TASK_METADATA_FIELDS
        assert task.text.strip()
        assert task.metadata["language"] in {"python", "java"}


def test_gate_snapshot(bench):
    assert set(bench.gate) == {t.id for t in bench.tasks}
    assert all(r["status"] == "passed" for r in bench.gate.values())


def test_snapshot_integrity(bench):
    assert verify_manifest(bench.root, bench.manifest) == []


def test_tier1_on_fixed_8192_windows(bench):
    kept, reasons = apply_constraints(bench.skills, Environment("windows", 8192))
    assert len(kept) == 38
    assert sorted(reasons) == ["git-history-rewriter", "java-oom-analyzer", "system-cpu-spikes-analyzer"]
    assert all(r.startswith("os:") for r in reasons.values())
