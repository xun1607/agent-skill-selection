from __future__ import annotations

import json
from pathlib import Path


def _inside(root: Path, value: str) -> Path:
    path = (root / value).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"registry path escapes repository: {value}")
    return path


def load_registry(root: Path) -> dict:
    """Load the pinned local inventory without syncing or executing skill content."""
    lock = json.loads((root / "config/registry/sources.lock.json").read_text(encoding="utf-8"))
    sources, skills = [], []
    for source_id, source in lock["sources"].items():
        inventory = _inside(root, source["inventory_ref"]) / "profiles.jsonl"
        entries = [json.loads(line) for line in inventory.read_text(encoding="utf-8").splitlines()] if inventory.exists() else []
        sources.append({"source_id": source_id, **source, "inventory_exists": inventory.exists()})
        for entry in entries:
            profile = entry["profile"]
            skills.append({
                "skill_id": profile["skill_id"],
                "name": profile["name"],
                "description": profile["description"],
                "revision_id": profile["revision_id"],
                "validation_status": profile["validation_status"],
                "validation_issues": profile.get("validation_issues", []),
                "source": profile["source"],
                "resources": profile.get("resources", []),
                "package_ref": entry["package_ref"],
            })
    return {"sources": sources, "skills": sorted(skills, key=lambda row: row["skill_id"])}


def read_skill(root: Path, skill: dict) -> str:
    return (_inside(root, skill["package_ref"]) / "SKILL.md").read_text(encoding="utf-8-sig")
