import json

import pytest

from skill_selection.datasets.gr1 import DEFAULT_ROOT, load_gr1
from skill_selection.filters.constraint import (Environment, apply_constraints, exclusion_reason, parse_memory_mb,
                                                parse_ram_mode)


def test_parse_ram_mode():
    assert parse_ram_mode("fixed:8192") == 8192
    for bad in ("host", "fixed:", "fixed:abc", "8192", "fixed:-1"):
        with pytest.raises(ValueError):
            parse_ram_mode(bad)


def test_parse_memory_like_gr1():
    assert parse_memory_mb("128MB") == 128
    assert parse_memory_mb(" 1gb ") == 1024
    assert parse_memory_mb("512") == 512
    assert parse_memory_mb(None) == 0          # GR1 default "0MB"
    assert parse_memory_mb("1.5TB") is None     # unparseable -> GR1 lets the skill through


def test_exclusion_reasons():
    env = Environment(os_name="windows", ram_mb=512, blacklist=frozenset({"banned"}))
    assert exclusion_reason("ok", {"host": {"os": ["windows"]}, "resources": {"memory": "512MB"}}, env) is None
    assert exclusion_reason("ok", {}, env) is None                                  # no constraints at all
    assert exclusion_reason("ok", {"host": {"os": []}}, env) is None                # empty os list = any os
    assert exclusion_reason("ok", {"resources": {"memory": "lots"}}, env) is None   # unparseable memory allowed
    assert exclusion_reason("banned", {}, env).startswith("blacklist")
    assert exclusion_reason("x", {"host": {"os": ["linux"]}}, env) == "os: requires [linux], host is windows"
    assert exclusion_reason("x", {"resources": {"memory": "1GB"}}, env) == "ram: requires 1024 MB > 512 MB available"


def test_apply_keeps_input_order():
    class S:
        def __init__(self, id, os):
            self.id, self.metadata = id, {"constraints": {"host": {"os": os}}}
    skills = [S("b", ["windows"]), S("a", ["linux"]), S("c", [])]
    kept, reasons = apply_constraints(skills, Environment("windows", 8192))
    assert [s.id for s in kept] == ["b", "c"]
    assert set(reasons) == {"a"}


def test_parity_with_gr1_constraint_filter():
    """Same decisions and order as cass.filter.constraint.ConstraintFilterStrategy, recorded by the export script."""
    bench = load_gr1()
    cases = json.loads((DEFAULT_ROOT / "parity" / "constraint.json").read_text(encoding="utf-8"))["cases"]
    assert len(cases) >= 4
    for case in cases:
        kept, _ = apply_constraints(bench.skills, Environment(case["os_name"], case["ram_mb"]))
        assert [s.id for s in kept] == case["kept"], (case["os_name"], case["ram_mb"])
