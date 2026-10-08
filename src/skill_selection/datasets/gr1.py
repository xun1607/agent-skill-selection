"""Loader for the GR1 internal benchmark snapshot (benchmarks/gr1_internal/, written by scripts/export_gr1_snapshot.py).

Input: the snapshot folder: skills.jsonl (41 skills), tasks.jsonl (6 bug-fix tasks), gate.json, MANIFEST.json and
skills/<folder>/SKILL.md copies.
Output: a GR1Benchmark with SkillRecord / QueryRecord lists, the gate verdict per task and the manifest.
Tasks carry only what is observable before the run (description, language, workspace file names): no gold skills.
By default the sha256 of every snapshot file is checked against MANIFEST.json, so a hand-edited snapshot fails loudly.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from ..io import read_jsonl
from ..schemas import QueryRecord, SkillRecord

DEFAULT_ROOT = Path(__file__).resolve().parents[3] / "benchmarks" / "gr1_internal"
TASK_METADATA_FIELDS = frozenset({"title", "category", "language", "workspace_files"})


@dataclass(frozen=True)
class GR1Benchmark:
    root: Path
    skills: List[SkillRecord]
    tasks: List[QueryRecord]
    gate: Dict[str, dict]           # task id -> {"status": "passed" | "failed" | "not_run", ...verdicts}
    manifest: dict

    def skill_md(self, skill: SkillRecord) -> Optional[str]:
        """Verbatim SKILL.md, or None for the legacy Python skills that have no SKILL.md."""
        rel = skill.metadata.get("skill_md_path")
        return (self.root / rel).read_text(encoding="utf-8") if rel else None


def verify_manifest(root: Path, manifest: dict) -> List[str]:
    """Snapshot files whose sha256 differs from MANIFEST.json, or that are missing / not listed."""
    listed = manifest.get("files", {})
    on_disk = {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name != "MANIFEST.json"}
    bad = sorted(on_disk ^ set(listed))
    for rel in sorted(on_disk & set(listed)):
        if hashlib.sha256((root / rel).read_bytes()).hexdigest() != listed[rel]:
            bad.append(rel)
    return bad


def load_gr1(root: Path = DEFAULT_ROOT, verify: bool = True) -> GR1Benchmark:
    root = Path(root)
    if not (root / "MANIFEST.json").exists():
        raise FileNotFoundError(f"no GR1 snapshot in {root}; run scripts/export_gr1_snapshot.py with GR1's python")
    manifest = json.loads((root / "MANIFEST.json").read_text(encoding="utf-8"))
    if verify:
        bad = verify_manifest(root, manifest)
        if bad:
            raise ValueError(f"GR1 snapshot does not match MANIFEST.json: {bad}")
    skills = [SkillRecord.from_dict(row) for row in read_jsonl(root / "skills.jsonl")]
    tasks = [QueryRecord.from_dict(row) for row in read_jsonl(root / "tasks.jsonl")]
    for task in tasks:
        extra = set(task.metadata) - TASK_METADATA_FIELDS
        if extra:
            raise ValueError(f"task {task.id} exposes unexpected fields {sorted(extra)}")
    gate = json.loads((root / "gate.json").read_text(encoding="utf-8"))["results"]
    return GR1Benchmark(root=root, skills=skills, tasks=tasks, gate=gate, manifest=manifest)
