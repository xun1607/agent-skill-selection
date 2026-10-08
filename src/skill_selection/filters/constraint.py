"""Tier 1: drop skills that cannot run in the execution environment (OS, RAM, session blacklist).

Port of GR1 `cass.filter.constraint.ConstraintFilterStrategy` with the same decisions (checked against a recorded
oracle in tests/unit/test_constraint.py), plus a human-readable reason for every excluded skill.

Input: skills carrying `metadata["constraints"]` (`host.os`, `resources.memory`) and an `Environment`.
Output: the kept skills in input order and {skill id: reason} for the excluded ones.
The environment is passed in explicitly, never read from the host, so results do not depend on the machine.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Sequence, Tuple


@dataclass(frozen=True)
class Environment:
    os_name: str                                # "windows" | "linux" | "darwin"
    ram_mb: float                               # available RAM
    blacklist: FrozenSet[str] = frozenset()     # skills that failed earlier in the session


def parse_ram_mode(mode: str) -> int:
    """`fixed:<MB>` -> MB. Reading the host's free RAM is deliberately not supported: it breaks reproducibility."""
    kind, _, value = mode.partition(":")
    if kind != "fixed" or not value.isdigit():
        raise ValueError(f"ram mode must look like 'fixed:8192', got {mode!r}")
    return int(value)


def parse_memory_mb(value: Any) -> Optional[float]:
    """GR1 rule: "1GB" -> 1024, "128MB" / "128" -> 128, missing -> 0; anything else -> None (skill is allowed)."""
    text = str("0MB" if value is None else value).strip().upper()
    try:
        return float(text[:-2]) * 1024 if text.endswith("GB") else float(text.replace("MB", ""))
    except ValueError:
        return None


def exclusion_reason(skill_id: str, constraints: Mapping[str, Any], env: Environment) -> Optional[str]:
    """None if the skill may run in `env`, otherwise why not. Checks run in GR1's order: blacklist, OS, RAM."""
    if skill_id in env.blacklist:
        return "blacklist: failed earlier in this session"
    required_os = (constraints.get("host") or {}).get("os") or []
    if required_os and env.os_name not in required_os:
        return f"os: requires [{', '.join(required_os)}], host is {env.os_name}"
    required_mb = parse_memory_mb((constraints.get("resources") or {}).get("memory"))
    if required_mb is not None and required_mb > env.ram_mb:
        return f"ram: requires {required_mb:g} MB > {env.ram_mb:g} MB available"
    return None


def apply_constraints(skills: Sequence[Any], env: Environment) -> Tuple[List[Any], Dict[str, str]]:
    kept, reasons = [], {}
    for skill in skills:
        reason = exclusion_reason(skill.id, skill.metadata.get("constraints") or {}, env)
        if reason is None:
            kept.append(skill)
        else:
            reasons[skill.id] = reason
    return kept, reasons
