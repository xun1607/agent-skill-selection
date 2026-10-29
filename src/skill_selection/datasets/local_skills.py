"""Catalog loader for SKILL.md folders
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


def load_skill_dir(root: Path, source: str = "local") -> list[SkillRecord]:
    skills = []
    for path in sorted(root.rglob("SKILL.md")):
        text = path.read_text(encoding="utf-8")
        # Đọc YAML front matter nếu có
        metadata = {}
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) == 3:
                metadata = yaml.safe_load(parts[1]) or {}
                body = parts[2]

        # Lấy thông tin skill
        name = metadata.get("name") or path.parent.name
        constraints = metadata.get("constraints") or {}
        safety = constraints.get("safety") or {}

        skills.append(
            SkillRecord(
                id=str(name),
                name=str(name),
                description=str(metadata.get("description") or "").strip(),
                body=body.strip(),
                source=source,
                category=str(metadata.get("category") or ""),
                metadata={
                    "version": metadata.get("version"),
                    "level": metadata.get("level"),
                    "goal": metadata.get("goal"),
                    "tags": metadata.get("tags"),
                    "sub_skills": metadata.get("sub_skills"),
                    "path": path.relative_to(root).as_posix(),
                    **(
                        {"fs_access": safety["fs_access"]}
                        if "fs_access" in safety
                        else {}
                    ),
                },
            )
        )

    # Kiểm tra ID trùng
    ids = [skill.id for skill in skills]
    if len(ids) != len(set(ids)):
        raise ValueError(f"Duplicate skill IDs under {root}")
    
    return skills