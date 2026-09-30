"""Catalog loader for SKILL.md folders, e.g. the GR1 skill library.

A SKILL.md starts with a YAML front matter block between two `---` lines, followed by the instructions. Files without
front matter are kept, with the folder name as id and the whole file as body.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

import yaml

from ..schemas import SkillRecord

METADATA_FIELDS = ("version", "level", "goal", "tags", "sub_skills")


def split_front_matter(text: str) -> Tuple[dict, str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            meta = yaml.safe_load("\n".join(lines[1:i])) or {}
            return (meta if isinstance(meta, dict) else {}), "\n".join(lines[i + 1:])
    return {}, text


def load_skill_dir(root: Path, source: str = "local") -> List[SkillRecord]:
    skills = []
    for path in sorted(Path(root).rglob("SKILL.md")):
        meta, body = split_front_matter(path.read_text(encoding="utf-8"))
        folder = path.parent.name
        safety = ((meta.get("constraints") or {}).get("safety") or {})
        metadata = {k: meta[k] for k in METADATA_FIELDS if k in meta}
        metadata["path"] = path.relative_to(root).as_posix()
        if "fs_access" in safety:
            metadata["fs_access"] = safety["fs_access"]
        skills.append(SkillRecord(
            id=str(meta.get("name") or folder), name=str(meta.get("name") or folder),
            description=str(meta.get("description") or "").strip(), body=body.strip(),
            source=source, category=str(meta.get("category") or ""), metadata=metadata,
        ))
    ids = [s.id for s in skills]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise ValueError(f"duplicate skill ids under {root}: {dupes}")
    return skills
