import dataclasses

from skill_selection.datasets import skillret
from skill_selection.datasets.local_skills import load_skill_dir
from skill_selection.io import write_jsonl
from skill_selection.schemas import QueryRecord

SKILLS = [
    {"id": "k1", "name": "pytest-runner", "description": "Run pytest", "skill_md": "## Steps\nrun it",
     "major": "dev", "sub": "testing", "stars": 3},
    {"id": "k2", "name": "notes", "description": "Take notes", "skill_md": "", "major": "docs"},
]
QUERIES = [
    {"id": "q1", "original_id": "o1", "query": "run my tests", "skill_ids": ["k1"], "skill_names": ["pytest-runner"],
     "k": 1, "generator_model": "m"},
    {"id": "q2", "original_id": "o1", "query": "tests and notes", "skill_ids": ["k1", "k2"], "k": 2,
     "generator_model": "m"},
]
QRELS = [{"query_id": "q1", "skill_id": "k1", "relevance": 1},
         {"query_id": "q2", "skill_id": "k1", "relevance": 1}]          # q2 lacks k2 on purpose


def write_split(root):
    paths = skillret.split_paths("test", root)
    write_jsonl(SKILLS, paths["skills"])
    write_jsonl(QUERIES, paths["queries"])
    write_jsonl(QRELS, paths["qrels"])


def test_skillret_loader_never_exposes_gold(tmp_path):
    write_split(tmp_path)
    skills, queries, qrels = skillret.load_split("test", tmp_path)
    assert [s.id for s in skills] == ["k1", "k2"]
    assert skills[0].category == "dev/testing"
    assert skills[1].body == "Take notes"                   # empty skill_md falls back to the description
    assert qrels == {"q1": {"k1": 1}, "q2": {"k1": 1}}
    fields = {f.name for f in dataclasses.fields(QueryRecord)}
    for query in queries:
        exposed = fields | set(query.metadata)
        assert not exposed & skillret.GOLD_QUERY_FIELDS
    assert queries[0].group_id == "o1"


def test_skillret_stats_flags_label_mismatch(tmp_path):
    write_split(tmp_path)
    stats = skillret.split_stats("test", tmp_path)
    assert stats["n_skills"] == 2 and stats["n_queries"] == 2 and stats["n_qrels"] == 2
    assert stats["query_label_mismatches"] == 1
    assert stats["positives_per_query"] == {1: 2}
    assert stats["n_query_groups"] == 1 and stats["max_queries_per_group"] == 2


def test_missing_files_raise(tmp_path):
    try:
        skillret.load_split("test", tmp_path)
    except FileNotFoundError as e:
        assert "download" in str(e)
    else:
        raise AssertionError("expected FileNotFoundError")


def test_local_skill_dir(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "SKILL.md").write_text(
        "---\nname: suggest-fix\ndescription: Suggest a fix\ncategory: python/debugging\nlevel: atomic\n"
        "constraints:\n  safety:\n    fs_access: read-only\n---\n\n## Instructions\nDo it.\n", encoding="utf-8")
    (tmp_path / "plain").mkdir()
    (tmp_path / "plain" / "SKILL.md").write_text("Just text", encoding="utf-8")
    skills = {s.id: s for s in load_skill_dir(tmp_path, source="gr1")}
    assert skills["suggest-fix"].category == "python/debugging"
    assert skills["suggest-fix"].metadata["fs_access"] == "read-only"
    assert skills["suggest-fix"].body.startswith("## Instructions")
    assert skills["plain"].body == "Just text"
