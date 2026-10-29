import copy
import importlib.util
import io
import json
from pathlib import Path
import zipfile

import pytest

from skill_selection.registry.contracts import CONTRACTS, load_schema, validate_record
from skill_selection.registry.packages import content_id, file_manifest, preserve_package, profile_package

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("sync_skill_sources", ROOT / "scripts" / "sync_skill_sources.py")
SYNC = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SYNC)


@pytest.mark.parametrize("contract", CONTRACTS)
def test_examples_match_bundled_contracts(contract):
    from jsonschema import Draft202012Validator
    Draft202012Validator.check_schema(load_schema(contract))
    example = json.loads((ROOT / "examples" / "registry" / f"{contract}.json").read_text(encoding="utf-8"))
    validate_record(contract, example)


def decision():
    return json.loads((ROOT / "examples" / "registry" / "selection-decision.json").read_text(encoding="utf-8"))


def test_no_skill_and_selector_error_are_distinct():
    record = decision()
    record["status"] = "error"
    with pytest.raises(ValueError):
        validate_record("selection-decision", record)
    record["error"] = {"code": "REGISTRY_ERROR", "message": "snapshot unavailable"}
    validate_record("selection-decision", record)
    record["status"] = "no_skill"
    with pytest.raises(ValueError):
        validate_record("selection-decision", record)


def test_selected_requires_a_unique_positioned_revision():
    record = decision()
    record["status"] = "selected"
    with pytest.raises(ValueError):
        validate_record("selection-decision", record)
    record["selected"] = [{"skill_id": "demo/testing", "revision_id": "sha256:" + "a" * 64, "position": 0}]
    validate_record("selection-decision", record)
    record["selected"].append(copy.deepcopy(record["selected"][0]))
    with pytest.raises(ValueError):
        validate_record("selection-decision", record)


def test_request_rejects_gold_fields_unpinned_repo_and_negative_budget():
    record = json.loads((ROOT / "examples" / "registry" / "task-request.json").read_text(encoding="utf-8"))
    for field, value in [("gold_patch", "answer"), ("hidden_tests", [])]:
        with pytest.raises(ValueError):
            validate_record("task-request", {**record, field: value})
    unpinned = copy.deepcopy(record)
    unpinned["repo_ref"] = {"url": None, "commit": None, "snapshot_id": None}
    with pytest.raises(ValueError):
        validate_record("task-request", unpinned)
    record["budgets"]["max_load_tokens"] = -1
    with pytest.raises(ValueError):
        validate_record("task-request", record)


def package(tmp_path):
    root = tmp_path / "skill"
    (root / "references").mkdir(parents=True)
    (root / "SKILL.md").write_text("---\nname: testing\ndescription: Run Python tests\n---\nRead references/help.md", encoding="utf-8")
    (root / "references" / "help.md").write_text("Run pytest", encoding="utf-8")
    return root


def profile(root):
    return profile_package(root, source_id="demo", repo_url="https://github.com/example/demo",
                           commit="a" * 40, source_path="skills/testing/SKILL.md")


def test_resource_change_creates_new_revision_and_import_requires_review(tmp_path):
    root = package(tmp_path)
    before = profile(root)
    assert before["validation_status"] == "needs_review"
    assert before["source"]["license"] is None
    assert len(before["resources"]) == 2
    (root / "references" / "help.md").write_text("Run pytest -q", encoding="utf-8")
    assert profile(root)["revision_id"] != before["revision_id"]
    assert content_id({"b": 2, "a": 1}) == content_id({"a": 1, "b": 2})


def test_existing_revision_cannot_be_overwritten(tmp_path):
    root = package(tmp_path)
    manifest = file_manifest(root)
    target = tmp_path / "immutable"
    preserve_package(root, target, manifest)
    preserve_package(root, target, manifest)
    (target / "SKILL.md").write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        preserve_package(root, target, manifest)


@pytest.mark.parametrize("name", ["repo/../../outside", "repo/C:/outside", "repo/CON.txt", "repo/a\\b"])
def test_archive_rejects_unsafe_paths(tmp_path, name):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        # ZipInfo's constructor normalizes backslashes on Windows; preserve the
        # hostile raw name explicitly to test the extractor rather than writer.
        member = zipfile.ZipInfo("placeholder")
        member.filename = name
        archive.writestr(member, "bad")
    with pytest.raises(ValueError):
        SYNC.extract_archive(stream.getvalue(), tmp_path / "out")
    assert not (tmp_path / "outside").exists()


def test_archive_preserves_resources(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("repo/skills/testing/SKILL.md", "instructions")
        archive.writestr("repo/skills/testing/references/help.md", "reference")
        archive.writestr("repo/LICENSE", "license")
    SYNC.extract_archive(stream.getvalue(), tmp_path)
    assert (tmp_path / "skills/testing/references/help.md").read_text() == "reference"
    assert (tmp_path / "LICENSE").exists()


def test_sync_is_reproducible_and_does_not_replace_lock_on_tampering(tmp_path, monkeypatch):
    config = tmp_path / "config" / "registry"
    config.mkdir(parents=True)
    (config / "sources.yaml").write_text(
        "sources:\n- source_id: demo\n  kind: github\n  repo_url: https://github.com/example/demo\n  ref: main\n  skills_root: skills\n",
        encoding="utf-8")
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("repo/skills/testing/SKILL.md", "---\nname: testing\ndescription: Run Python tests\n---\nRun pytest")
        archive.writestr("repo/LICENSE", "MIT")
    calls = []

    def fake_fetch(url, limit=0):
        calls.append(url)
        return json.dumps({"sha": "a" * 40}).encode() if "api.github.com" in url else stream.getvalue()

    monkeypatch.setattr(SYNC, "ROOT", tmp_path)
    monkeypatch.setattr(SYNC, "fetch", fake_fetch)
    first = SYNC.sync("demo")
    lock_before = (config / "sources.lock.json").read_bytes()
    assert SYNC.sync("demo") == first
    assert len(calls) == 2  # second run uses pinned, verified local cache
    assert (config / "sources.lock.json").read_bytes() == lock_before
    raw = tmp_path / "data/raw/skill_sources/demo" / ("a" * 40) / "repository/LICENSE"
    raw.write_text("tampered", encoding="utf-8")
    with pytest.raises(ValueError, match="changed"):
        SYNC.sync("demo")
    assert (config / "sources.lock.json").read_bytes() == lock_before
    assert not (config / "sync.lock").exists()


def test_sync_guard_prevents_lost_lock_updates(tmp_path, monkeypatch):
    config = tmp_path / "config/registry"
    config.mkdir(parents=True)
    guard = config / "sync.lock"
    guard.write_text("another-process", encoding="utf-8")
    monkeypatch.setattr(SYNC, "ROOT", tmp_path)
    with pytest.raises(ValueError, match="another sync"):
        SYNC.sync("demo")
    assert guard.read_text() == "another-process"
