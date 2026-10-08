"""Export a read-only snapshot of the GR1 internal benchmark into this repo (benchmarks/gr1_internal/).

What it does
  Reads the GR1 codebase through GR1's own objects, so names, descriptions and constraints are exactly what GR1 sees:
  the 41-skill registry (experiment_setup.build_skills + CASSBridge._to_profiles), the 6 internal testcases
  (experiment_setup.INTERNAL_TESTCASES via testcases_suite.get_testcases), and the validation gate
  (validate_testcases.validate, run now in a temporary directory). It never writes inside GR1.

Input
  --gr1   path to GR1 backend/services/skill_testing (default: the gr1-prj checkout next to this repo)
  Must be run with GR1's interpreter, e.g.
    <gr1>/../../venv/Scripts/python.exe scripts/export_gr1_snapshot.py

Output (under --out, default benchmarks/gr1_internal/)
  skills.jsonl        41 SkillRecord rows: id, name, description, body, source, category,
                      metadata {kind, constraints, folder, skill_md_path, version, level, tags, quality_flags}
                      quality_flags marks defects kept as-is for parity with GR1, e.g. a SKILL.md that is an
                      HTML page (skill_md_is_html) or GR1's fallback description (description_is_fallback)
  skills/<folder>/SKILL.md   verbatim copies of the real SKILL.md files (the 2 legacy Python skills have none; a
                      SKILL.md that is an HTML page is not copied, only its sha256 in metadata.skill_md_omitted)
  tasks.jsonl         6 QueryRecord rows: id, text (= task_desc), source, group_id,
                      metadata {title, category, language, workspace_files}. No gold information.
  gate.json           per-testcase gate verdicts from validate()
  parity/constraint.json   GR1 ConstraintFilterStrategy decisions for several environments (test oracle)
  MANIFEST.json       GR1 commit, whether the exported paths were clean, sha256 of every output file
"""
import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GR1 = REPO_ROOT.parent / "gr1-prj" / "ai-software-engineering-agent" / "backend" / "services" / "skill_testing"
# GR1 paths whose content ends up in the snapshot; MANIFEST records whether they had uncommitted changes
SOURCE_PATHS = ["skills", "legacy_skills.py", "testcases_suite.py", "experiment_setup.py", "validate_testcases.py",
                "gold_fixes", "benchmark_repos/repo_flask_api", "benchmark_repos/repo_data_processor",
                "cass/filter/constraint.py", "swe_agent/skills/markdown_skill.py"]
# Environments for the Tier-1 parity oracle: (os_name, available_ram_mb)
PARITY_ENVS = [("windows", 8192), ("linux", 8192), ("darwin", 8192), ("windows", 512), ("windows", 64)]
LANGUAGE_BY_EXT = {".py": "python", ".java": "java"}
SKIP_DIRS = {"tests", "test", "target", "__pycache__", ".git", ".pytest_cache"}


def split_front_matter(text: str) -> str:
    """Body of a SKILL.md: everything after the closing `---` of the front matter (whole text if none)."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---":
                return "\n".join(lines[i + 1:]).strip()
    return text.strip()


def workspace_files(tc: dict, gr1: Path) -> list:
    """Files visible in the workspace before the agent runs (paths only, no content)."""
    files = set(tc.get("files", {}))
    if tc.get("repo_dir"):
        root = gr1 / tc["repo_dir"]
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(d for d in dirnames if d not in {".git", "__pycache__", ".pytest_cache", "target"})
            for name in filenames:
                files.add((Path(dirpath) / name).relative_to(root).as_posix())
    return sorted(files)


def task_language(paths: list) -> str:
    """Majority language of non-test source files, e.g. tc_git_conflict edits config.py -> python."""
    counts = Counter(LANGUAGE_BY_EXT[Path(p).suffix] for p in paths
                     if Path(p).suffix in LANGUAGE_BY_EXT and not (set(Path(p).parts[:-1]) & SKIP_DIRS))
    return counts.most_common(1)[0][0] if counts else "unknown"


def git(gr1: Path, *args) -> str:
    return subprocess.run(["git", "-C", str(gr1), *args], capture_output=True, text=True, check=True).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_jsonl(rows, path: Path) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--gr1", type=Path, default=DEFAULT_GR1)
    parser.add_argument("--out", type=Path, default=REPO_ROOT / "benchmarks" / "gr1_internal")
    parser.add_argument("--skip-gate", action="store_true", help="do not run validate(); gate.json marks every task 'not_run'")
    args = parser.parse_args()
    gr1 = args.gr1.resolve()

    sys.path.insert(0, str(gr1 / "swe_agent"))
    sys.path.insert(0, str(gr1))
    os.chdir(gr1)  # GR1 modules resolve some paths relative to the working directory
    from experiment_setup import INTERNAL_TESTCASES, build_skills
    from swe_agent.cass_bridge import CASSBridge
    from testcases_suite import get_testcases
    from cass.filter.constraint import ConstraintFilterStrategy

    out = args.out.resolve()
    if out.exists():
        shutil.rmtree(out)
    (out / "skills").mkdir(parents=True)
    (out / "parity").mkdir()

    # ---- skills: registry order is GR1's order (sorted folders, then the two legacy skills)
    skills = build_skills(brain=None)
    profiles = {p["name"]: p for p in CASSBridge._to_profiles(skills)}
    rows = []
    for s in skills:
        md_path = getattr(s, "filepath", None) or getattr(s, "file_path", None)
        meta = {"kind": "legacy_python" if md_path is None else "skill_md",
                "constraints": profiles[s.name].get("constraints") or {}}
        body, flags = "", []
        if md_path:
            md_path = Path(md_path)
            folder = md_path.parent.name
            raw = md_path.read_text(encoding="utf-8")
            meta["folder"] = folder
            if raw.lstrip().lower().startswith(("<!doctype html", "<html")):
                # A scraped web page, not a skill: keep only a fingerprint, never republish its content
                flags.append("skill_md_is_html")
                meta["skill_md_omitted"] = {
                    "sha256": hashlib.sha256(md_path.read_bytes()).hexdigest(), "bytes": md_path.stat().st_size,
                    "gr1_path": md_path.relative_to(gr1).as_posix(),
                    "note": "GR1 file is an HTML page saved by mistake; content not copied into this repo"}
            else:
                (out / "skills" / folder).mkdir()
                shutil.copyfile(md_path, out / "skills" / folder / "SKILL.md")
                body = split_front_matter(raw)
                meta["skill_md_path"] = f"skills/{folder}/SKILL.md"
        else:
            meta["python_class"] = f"{type(s).__module__}.{type(s).__name__}"
        if s.description.startswith("Dynamic skill loaded from "):   # GR1's fallback when front matter has none
            flags.append("description_is_fallback")
        if flags:
            meta["quality_flags"] = flags
        for key in ("version", "level", "tags"):
            if getattr(s, key, None) not in (None, "", []):
                meta[key] = getattr(s, key)
        rows.append({"id": s.name, "name": s.name, "description": s.description, "body": body, "source": "gr1",
                     "category": str(getattr(s, "category", "") or ""), "metadata": meta})
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids):
        raise SystemExit(f"duplicate skill ids: {sorted(i for i in ids if ids.count(i) > 1)}")
    write_jsonl(rows, out / "skills.jsonl")

    # ---- tasks: only what is observable before the run; never gold fixes or oracle labels
    testcases = {tc["id"]: tc for tc in get_testcases(INTERNAL_TESTCASES)}
    tasks = []
    for tc_id in INTERNAL_TESTCASES:
        tc = testcases[tc_id]
        files = workspace_files(tc, gr1)
        tasks.append({"id": tc_id, "text": tc["task_desc"], "source": "gr1", "group_id": tc_id,
                      "metadata": {"title": tc.get("name", tc_id), "category": tc.get("category", ""),
                                   "language": task_language(files), "workspace_files": files}})
    write_jsonl(tasks, out / "tasks.jsonl")

    # ---- gate
    gate = {"tool": "validate_testcases.validate", "results": {}}
    if args.skip_gate:
        gate["results"] = {tc_id: {"status": "not_run"} for tc_id in INTERNAL_TESTCASES}
    else:
        from validate_testcases import validate
        keep = ("original_verdict", "original_test_fails", "gold_verdict", "tamper_verdict", "emptied_verdict", "ok")
        with tempfile.TemporaryDirectory(prefix="gr1_gate_") as work_root:
            for tc_id in INTERNAL_TESTCASES:
                checks = validate(testcases[tc_id], work_root)
                gate["results"][tc_id] = {"status": "passed" if checks["ok"] else "failed",
                                          **{k: checks.get(k) for k in keep}}
    write_json(gate, out / "gate.json")

    # ---- Tier-1 parity oracle
    parity = []
    for os_name, ram in PARITY_ENVS:
        context = {"environment": {"os_name": os_name, "available_ram_mb": ram}, "temporary_blacklist": []}
        kept = [p["name"] for p in ConstraintFilterStrategy().filter(list(profiles.values()), context)]
        parity.append({"os_name": os_name, "ram_mb": ram, "kept": kept})
    write_json({"oracle": "cass.filter.constraint.ConstraintFilterStrategy", "cases": parity}, out / "parity" / "constraint.json")

    # ---- manifest
    dirty = git(gr1, "status", "--porcelain", "--", *SOURCE_PATHS)
    files = sorted(p for p in out.rglob("*") if p.is_file())
    write_json({
        "gr1_path": str(gr1), "gr1_commit": git(gr1, "rev-parse", "HEAD"),
        "gr1_source_paths_clean": not dirty, "gr1_source_paths_dirty": dirty.splitlines(),
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "host_os": platform.system().lower(),
        "counts": {"skills": len(rows), "skill_md": sum(r["metadata"]["kind"] == "skill_md" for r in rows),
                   "skill_md_copied": sum("skill_md_path" in r["metadata"] for r in rows),
                   "tasks": len(tasks), "gate_passed": sum(r.get("status") == "passed" for r in gate["results"].values())},
        "files": {p.relative_to(out).as_posix(): sha256(p) for p in files},
    }, out / "MANIFEST.json")
    print(f"wrote {out}: {len(rows)} skills, {len(tasks)} tasks, gate "
          f"{sum(r.get('status') == 'passed' for r in gate['results'].values())}/{len(tasks)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
