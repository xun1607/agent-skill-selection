"""Validate GR2 exchange records using bundled, offline JSON Schemas."""
from __future__ import annotations

import json
from importlib.resources import files
from typing import Any, Mapping

CONTRACTS = (
    "skill-profile", "skill-relation", "registry-snapshot", "task-request",
    "selection-decision", "verifier-spec", "verifier-result",
)


def load_schema(name: str) -> dict:
    if name not in (*CONTRACTS, "common"):
        raise ValueError(f"unknown contract: {name}")
    return json.loads(files(__package__).joinpath(f"schemas/v1/{name}.schema.json").read_text(encoding="utf-8"))


def validate_record(name: str, record: Mapping[str, Any]) -> None:
    """Raise ValueError for an invalid contract; never retrieve schemas over HTTP.

    Cross-record policy, dependency closure and execution permissions need a
    separate selector/registry service; a shape-valid profile is not permission.
    """
    from jsonschema import Draft202012Validator, FormatChecker
    from referencing import Registry, Resource

    resources = [load_schema(n) for n in (*CONTRACTS, "common")]
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s)) for s in resources)
    validator = Draft202012Validator(load_schema(name), registry=registry, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(dict(record)), key=lambda e: str(list(e.absolute_path)))
    if errors:
        raise ValueError("; ".join(f"{'.'.join(map(str, e.absolute_path)) or '$'}: {e.message}" for e in errors))
    if name == "task-request":
        repo = record["repo_ref"]
        if not repo["commit"] and not repo["snapshot_id"]:
            raise ValueError("repo_ref needs a pinned commit or immutable snapshot_id")
    if name == "skill-profile":
        paths = [r["path"] for r in record["resources"]]
        if "SKILL.md" not in paths or len(paths) != len(set(paths)):
            raise ValueError("resources must contain SKILL.md and unique relative paths")
        if record["validation_status"] == "valid" and record["validation_issues"]:
            raise ValueError("valid profiles cannot have unresolved validation_issues")
        if record["validation_status"] == "valid" and not record["source"]["license"]:
            raise ValueError("valid profiles need a reviewed source license")
    if name == "selection-decision":
        pairs = [(s["skill_id"], s["revision_id"]) for s in record["selected"]]
        if len(set(s[0] for s in pairs)) != len(pairs):
            raise ValueError("selected skill IDs must be unique")
        if [s["position"] for s in record["selected"]] != list(range(len(pairs))):
            raise ValueError("selected positions must be contiguous and zero based")
