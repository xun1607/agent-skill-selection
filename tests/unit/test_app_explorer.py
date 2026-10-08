import ast
import json
from pathlib import Path

import pytest

pytest.importorskip("streamlit")
from streamlit.testing.v1 import AppTest  # noqa: E402

APP = Path(__file__).resolve().parents[2] / "app" / "explorer.py"
FORBIDDEN = {"torch", "sentence_transformers", "transformers", "openai", "skill_selection"}


def test_app_only_reads_json():
    """The UI must not load models, call APIs or run the selection itself."""
    imported = set()
    for node in ast.walk(ast.parse(APP.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert not imported & FORBIDDEN, imported & FORBIDDEN


def _app(monkeypatch, directory):
    monkeypatch.setenv("SKILL_EXPLORER_DIR", str(directory))
    return AppTest.from_file(str(APP), default_timeout=60).run()


def _frame(at, column):
    return next(df.value for df in at.dataframe if column in df.value.columns)


def test_missing_artifacts_show_instructions(monkeypatch, tmp_path):
    at = _app(monkeypatch, tmp_path)
    assert not at.exception
    assert any("index gr1" in e.value for e in at.error)


def test_stale_selection_is_refused(monkeypatch, explorer_dir, tmp_path):
    (tmp_path / "skill_index.json").write_bytes((explorer_dir / "skill_index.json").read_bytes())
    selection = json.loads((explorer_dir / "selection_cache.json").read_text(encoding="utf-8"))
    selection["runs"][0]["tasks"].pop("tc_java_npe")              # e.g. computed from an older index
    (tmp_path / "selection_cache.json").write_text(json.dumps(selection), encoding="utf-8")
    at = _app(monkeypatch, tmp_path)
    assert not at.exception
    assert any("select gr1" in e.value for e in at.error)


def test_three_areas(monkeypatch, explorer_dir):
    at = _app(monkeypatch, explorer_dir)
    assert not at.exception
    tasks = _frame(at, "Cổng kiểm định")                          # area 1
    assert len(tasks) == 6
    assert set(tasks["Ngôn ngữ"]) == {"python", "java"}

    assert len(at.selectbox(key="skill").options) == 41            # area 2
    at.text_input(key="skill_search").input("git").run()
    options = at.selectbox(key="skill").options
    skills = {s["id"]: s for s in json.loads((explorer_dir / "skill_index.json").read_text(encoding="utf-8"))["skills"]}
    assert 0 < len(options) < 41
    assert all("git" in f"{o} {skills[o]['description']} {skills[o]['category']}".lower() for o in options)
    at.selectbox(key="skill").set_value(options[0]).run()
    assert not at.exception

    at.selectbox(key="task").set_value("tc_java_npe").run()       # area 3
    ranking = _frame(at, "Hạng")
    assert len(ranking) == 41
    assert (ranking["Được chọn"] == "★").sum() == 3
    excluded = ranking[ranking["Bị loại (tầng 1)"] == "có"]
    assert len(excluded) == 3 and excluded["Lý do loại"].str.startswith("os:").all()
