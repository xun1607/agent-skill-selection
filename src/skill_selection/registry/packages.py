"""Inventory and preserve skill packages without executing their instructions."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path, PurePosixPath
from typing import Any

from ..datasets.local_skills import split_front_matter
from .contracts import validate_record


def content_id(value: Any) -> str:
    """Canonical JSON hash: UTF-8, sorted keys, compact separators, no NaN."""
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    return "sha256:" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def file_manifest(package: Path) -> list[dict]:
    if package.is_symlink():
        raise ValueError("symlink package is not supported")
    result = []
    for path in sorted(package.rglob("*"), key=lambda p: p.relative_to(package).as_posix()):
        if path.is_symlink():
            raise ValueError(f"symlink resource is not supported: {path.name}")
        if path.is_file():
            rel = path.relative_to(package).as_posix()
            if "\\" in rel or ":" in rel or ".." in PurePosixPath(rel).parts:
                raise ValueError(f"unsafe resource path: {rel}")
            data = path.read_bytes()
            result.append({"path": rel, "sha256": "sha256:" + hashlib.sha256(data).hexdigest(),
                           "size_bytes": len(data)})
    return result


def profile_package(package: Path, *, source_id: str, repo_url: str, commit: str,
                    source_path: str) -> dict:
    manifest = file_manifest(package)
    meta, body = split_front_matter((package / "SKILL.md").read_text(encoding="utf-8-sig"))
    if not isinstance(meta.get("name"), str) or not meta["name"].strip():
        raise ValueError("missing or invalid frontmatter name")
    if not isinstance(meta.get("description"), str) or not meta["description"].strip():
        raise ValueError("missing or invalid frontmatter description")
    if not body.strip():
        raise ValueError("empty skill instructions")
    skill_path = PurePosixPath(source_path).parent.as_posix()
    profile = {
        "schema_version": "v1.0", "skill_id": f"{source_id}/{skill_path}",
        "revision_id": content_id(manifest), "name": meta["name"], "description": meta["description"].strip(),
        "source": {"repo_url": repo_url, "path": source_path, "commit": commit, "license": None},
        "declared_version": str(meta["version"]) if meta.get("version") is not None else None,
        "task_types": [], "capabilities": [], "applicability": [], "requirements": [],
        "resources": manifest, "load_estimate": None,
        "validation_status": "needs_review",
        "validation_issues": ["license_not_reviewed", "applicability_and_requirements_not_reviewed"],
        "provenance": {"name": "author_declared", "description": "author_declared",
                       "resources": "importer_sha256", "task_types": "not_reviewed",
                       "requirements": "not_reviewed", "license": "not_reviewed",
                       "upstream_license_declaration": meta.get("license")},
    }
    validate_record("skill-profile", profile)
    return profile


def preserve_package(package: Path, target: Path, expected_manifest: list[dict]) -> None:
    """Existing revisions are verified, never silently overwritten."""
    if target.exists():
        if file_manifest(target) != expected_manifest:
            raise ValueError(f"existing immutable package changed: {target}")
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(package, target)
    if file_manifest(target) != expected_manifest:
        raise ValueError(f"package copy failed verification: {target}")
