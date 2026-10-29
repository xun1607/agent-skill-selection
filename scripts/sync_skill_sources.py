"""Fetch pinned GitHub archives, inventory SKILL.md packages, retain all resources.

Usage: python scripts/sync_skill_sources.py --source obra-superpowers
       python scripts/sync_skill_sources.py --source anthropics-skills
       python scripts/sync_skill_sources.py --source obra-superpowers --update

No upstream instructions, hooks, scripts or plugins are executed or installed.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tempfile
from urllib.request import Request, urlopen
import zipfile

import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from skill_selection.io import write_json, write_jsonl  # noqa: E402
from skill_selection.registry.packages import content_id, file_manifest, preserve_package, profile_package  # noqa: E402

MAX_ARCHIVE_BYTES = 50 * 1024 * 1024
MAX_EXTRACTED_BYTES = 150 * 1024 * 1024
MAX_FILE_BYTES = 20 * 1024 * 1024


def fetch(url: str, limit: int = MAX_ARCHIVE_BYTES) -> bytes:
    request = Request(url, headers={"User-Agent": "GR2-skill-registry", "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=60) as response:
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("upstream response exceeds configured size limit")
    return data


def extract_archive(data: bytes, destination: Path) -> None:
    """Reject traversal, symlinks, Windows path aliases and zip bombs."""
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        members = archive.infolist()
        if len(members) > 20000 or sum(m.file_size for m in members) > MAX_EXTRACTED_BYTES:
            raise ValueError("archive extraction budget exceeded")
        names = set()
        roots = set()
        for member in members:
            # zipfile normalizes separators on Windows; validate the original
            # header name so a hostile backslash cannot disappear before checks.
            name = member.orig_filename
            path = PurePosixPath(name)
            if path.is_absolute() or "\\" in name or ":" in name or ".." in path.parts:
                raise ValueError("unsafe archive path")
            roots.add(path.parts[0])
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError("archive symlinks are not supported")
            if member.file_size > MAX_FILE_BYTES:
                raise ValueError("archive member too large")
            for part in path.parts:
                stem = part.split(".")[0].upper()
                if part.endswith((" ", ".")) or stem in {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}:
                    raise ValueError("unsupported Windows archive path")
            relative = Path(*path.parts[1:])
            if not path.parts[1:]:
                continue
            key = relative.as_posix().casefold()
            if key in names:
                raise ValueError("duplicate or case-colliding archive path")
            names.add(key)
            target = destination / relative
            target.resolve().relative_to(destination.resolve())
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(archive.read(member))
        if len(roots) != 1:
            raise ValueError("expected a single GitHub archive root")


def sync(source_id: str, update: bool = False) -> dict:
    config_dir = ROOT / "config" / "registry"
    guard = config_dir / "sync.lock"
    try:
        with guard.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError as error:
        raise ValueError("another sync is active (config/registry/sync.lock); run imports sequentially") from error
    try:
        return _sync(source_id, update)
    finally:
        guard.unlink()


def _sync(source_id: str, update: bool = False) -> dict:
    # Windows' legacy MAX_PATH can be exceeded by commit + revision + resource
    # paths. Use the native extended path prefix for IO, portable refs in JSON.
    root = ROOT.resolve()
    if os.name == "nt" and not str(root).startswith("\\\\?\\"):
        root = Path("\\\\?\\" + str(root))
    config_dir = root / "config" / "registry"
    config = yaml.safe_load((config_dir / "sources.yaml").read_text(encoding="utf-8"))
    source = next((s for s in config["sources"] if s["source_id"] == source_id), None)
    if source is None or source["kind"] != "github":
        raise ValueError("source is unknown or blocked; only configured GitHub skill repositories can be fetched")
    match = re.fullmatch(r"https://github.com/([\w.-]+)/([\w.-]+)", source["repo_url"])
    if not match:
        raise ValueError("unsupported GitHub repository URL")
    owner, repo = match.groups()
    lock_path = config_dir / "sources.lock.json"
    lock = json.loads(lock_path.read_text(encoding="utf-8")) if lock_path.exists() else {"schema_version": "v1.0", "sources": {}}
    previous = lock["sources"].get(source_id)
    if previous and not update:
        commit = previous["commit"]
    else:
        commit = json.loads(fetch(f"https://api.github.com/repos/{owner}/{repo}/commits/{source['ref']}", 1024 * 1024))["sha"]
    if not re.fullmatch("[0-9a-f]{40}", commit):
        raise ValueError("expected a full immutable Git commit")
    raw = root / "data" / "raw" / "skill_sources" / source_id / commit
    repo_dir = raw / "repository"
    if not raw.exists():
        archive_url = f"https://codeload.github.com/{owner}/{repo}/zip/{commit}"
        archive = fetch(archive_url)
        digest = "sha256:" + hashlib.sha256(archive).hexdigest()
        if previous and previous["commit"] == commit and previous["archive_sha256"] != digest:
            raise ValueError("downloaded archive does not match source lock")
        raw.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".download-", dir=raw.parent) as temporary:
            stage = Path(temporary)
            extract_archive(archive, stage / "repository")
            write_json({"source_id": source_id, "repo_url": source["repo_url"], "commit": commit,
                        "archive_url": archive_url, "archive_sha256": digest,
                        "repository_manifest_hash": content_id(file_manifest(stage / "repository"))}, stage / "SOURCE.json")
            os.replace(stage, raw)
    metadata = json.loads((raw / "SOURCE.json").read_text(encoding="utf-8"))
    if metadata["commit"] != commit or metadata["repo_url"] != source["repo_url"]:
        raise ValueError("raw cache source identity mismatch")
    if content_id(file_manifest(repo_dir)) != metadata["repository_manifest_hash"]:
        raise ValueError("raw cache repository files changed")
    if previous and previous["commit"] == commit and previous["archive_sha256"] != metadata["archive_sha256"]:
        raise ValueError("cached source does not match source lock")
    if previous and previous["commit"] == commit and previous["repository_manifest_hash"] != metadata["repository_manifest_hash"]:
        raise ValueError("cached repository manifest does not match source lock")
    skills_root = repo_dir / source["skills_root"]
    if not skills_root.is_dir():
        raise ValueError("configured skills directory is missing")
    entries, rejections = [], []
    processed = root / "data" / "processed" / "registry"
    for skill_md in sorted(skills_root.rglob("SKILL.md")):
        relative = skill_md.relative_to(repo_dir).as_posix()
        try:
            profile = profile_package(skill_md.parent, source_id=source_id, repo_url=source["repo_url"],
                                      commit=commit, source_path=relative)
        except (ValueError, UnicodeError, yaml.YAMLError) as error:
            rejections.append({"source_path": relative, "error": str(error)})
            continue
        target = processed / "packages" / source_id / skill_md.parent.relative_to(skills_root) / profile["revision_id"][7:]
        preserve_package(skill_md.parent, target, profile["resources"])
        entries.append({"profile_revision_id": content_id(profile), "package_ref": target.relative_to(root).as_posix(), "profile": profile})
    if not entries and not rejections:
        raise ValueError("no skill packages found; refuse an empty successful import")
    inventory = processed / "imports" / source_id / commit
    # Inventories are immutable too: updates to the importer produce a new import hash.
    import_id = content_id({"profiles": entries, "rejections": rejections})[7:]
    output = inventory / import_id
    if output.exists():
        actual_entries = [json.loads(line) for line in (output / "profiles.jsonl").read_text(encoding="utf-8").splitlines()]
        actual_rejections = [json.loads(line) for line in (output / "rejections.jsonl").read_text(encoding="utf-8").splitlines()]
        if actual_entries != entries or actual_rejections != rejections:
            raise ValueError("existing immutable inventory changed")
    else:
        inventory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=".import-", dir=inventory) as temporary:
            stage = Path(temporary)
            write_jsonl(entries, stage / "profiles.jsonl")
            write_jsonl(rejections, stage / "rejections.jsonl")
            os.replace(stage, output)
    summary = {**metadata, "import_id": "sha256:" + import_id, "profiles": len(entries),
               "rejections": len(rejections), "valid_for_selection": 0,
               "inventory_ref": output.relative_to(root).as_posix()}
    lock["sources"][source_id] = summary
    # Replace the lock only after the import succeeds.
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=config_dir, suffix=".tmp", delete=False) as handle:
        json.dump(lock, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        lock_temporary = Path(handle.name)
    os.replace(lock_temporary, lock_path)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--update", action="store_true", help="Explicitly resolve a new upstream commit")
    args = parser.parse_args()
    print(json.dumps(sync(args.source, args.update), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
