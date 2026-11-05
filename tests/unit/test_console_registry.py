import json

from skill_selection.console.registry import load_registry, read_skill


def test_registry_loads_pinned_profiles_and_skill_text(tmp_path):
    inventory = tmp_path / "inventory"
    package = tmp_path / "packages/example"
    inventory.mkdir()
    package.mkdir(parents=True)
    (package / "SKILL.md").write_text("# Example\n", encoding="utf-8")
    profile = {
        "profile_revision_id": "sha256:profile",
        "package_ref": "packages/example",
        "profile": {
            "skill_id": "source/skills/example",
            "name": "example",
            "description": "Example skill",
            "revision_id": "sha256:revision",
            "validation_status": "needs_review",
            "validation_issues": ["license_not_reviewed"],
            "source": {"repo_url": "https://example.test/repo", "commit": "abc", "path": "SKILL.md"},
            "resources": [{"path": "SKILL.md", "sha256": "sha256:file", "size_bytes": 10}],
        },
    }
    (inventory / "profiles.jsonl").write_text(json.dumps(profile) + "\n", encoding="utf-8")
    lock = {"sources": {"source": {
        "repo_url": "https://example.test/repo",
        "commit": "abc",
        "profiles": 1,
        "valid_for_selection": 0,
        "inventory_ref": "inventory",
    }}}
    (tmp_path / "config/registry").mkdir(parents=True)
    (tmp_path / "config/registry/sources.lock.json").write_text(json.dumps(lock), encoding="utf-8")

    assert load_registry(tmp_path)["sources"][0]["inventory_exists"] is True
    skill = load_registry(tmp_path)["skills"][0]
    assert skill["validation_status"] == "needs_review"
    assert read_skill(tmp_path, skill) == "# Example\n"


def test_registry_refuses_inventory_outside_repository(tmp_path):
    (tmp_path / "config/registry").mkdir(parents=True)
    lock = {"sources": {"source": {
        "repo_url": "https://example.test/repo",
        "commit": "abc",
        "profiles": 0,
        "valid_for_selection": 0,
        "inventory_ref": "../outside",
    }}}
    (tmp_path / "config/registry/sources.lock.json").write_text(json.dumps(lock), encoding="utf-8")

    try:
        load_registry(tmp_path)
    except ValueError as error:
        assert "escapes repository" in str(error)
    else:
        raise AssertionError("unsafe registry path was accepted")

