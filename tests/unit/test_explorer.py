import json
import os
import socket
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from skill_selection.datasets.gr1 import load_gr1
from skill_selection.encoders import parse_encoder_spec
from skill_selection.encoders.base import CachedEncoder, EmbeddingCache
from skill_selection.encoders.st_encoder import SentenceTransformerEncoder
from skill_selection.explorer import build_index, select_all, skill_text, write_json_stable
from skill_selection.filters.constraint import Environment
from skill_selection.selectors.dense import rank_by_cosine

from conftest import FakeEncoder


@pytest.fixture(scope="module")
def bench():
    return load_gr1()


@pytest.fixture(scope="module")
def index(bench):
    return build_index(bench, [FakeEncoder()])


def test_rank_by_cosine_by_hand():
    ids = ["a", "b", "c", "d"]
    m = np.array([[1, 0], [0, 1], [0.6, 0.8], [1, 0]], dtype=np.float32)
    order, scores = rank_by_cosine(np.array([1, 0], dtype=np.float32), m)
    assert [ids[i] for i in order] == ["a", "d", "c", "b"]      # tie a/d keeps catalog order
    assert scores.tolist() == pytest.approx([1.0, 0.0, 0.6, 1.0])


def test_encoder_normalises_and_caches(tmp_path):
    enc = CachedEncoder(FakeEncoder(), EmbeddingCache(tmp_path / "c.json"))
    v = enc.encode(["x", "y"], "document")
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-6)
    enc.encode(["x", "y"], "document")
    assert len(enc.inner.calls) == 1                            # second call served from cache
    enc.encode(["x"], "query")
    assert len(enc.inner.calls) == 2                            # kind is part of the key
    again = CachedEncoder(FakeEncoder(), EmbeddingCache(tmp_path / "c.json"))
    assert np.array_equal(again.encode(["x", "y"], "document"), v)
    assert again.inner.calls == []                              # persisted on disk


def test_cache_key_depends_on_model_revision():
    a, b = FakeEncoder(), FakeEncoder()
    b.revision = "v2"
    assert EmbeddingCache.key(a, "document", "t") != EmbeddingCache.key(b, "document", "t")


def test_qwen_prompt_only_for_queries():
    class FakeST:
        prompts = {"query": "Instruct: q\nQuery:", "document": ""}
        def __init__(self):
            self.calls = []
        def encode(self, texts, prompt_name=None, **kw):
            self.calls.append(prompt_name)
            return np.ones((len(texts), 3), dtype=np.float32)
    fake = FakeST()
    enc = SentenceTransformerEncoder("Qwen/Qwen3-Embedding-0.6B", "rev", model_obj=fake)
    enc.encode(["task"], "query")
    enc.encode(["skill"], "document")
    assert fake.calls == ["query", None]
    assert enc.info()["query_prompt"] == "Instruct: q\nQuery:"


def test_parse_encoder_spec():
    assert parse_encoder_spec("st:Qwen/Qwen3-Embedding-0.6B")[:2] == ("st", "Qwen/Qwen3-Embedding-0.6B")
    assert parse_encoder_spec("st:Qwen/Qwen3-Embedding-0.6B@abc")[2] == "abc"
    assert parse_encoder_spec("openai:text-embedding-3-small")[0] == "openai"
    with pytest.raises(ValueError):
        parse_encoder_spec("tfidf")
    with pytest.raises(ValueError):
        parse_encoder_spec("st:some/unpinned-model")                # local models must be pinned


def test_index_contents(index, bench):
    assert index["representation"] == "name: description"
    assert [s["id"] for s in index["skills"]] == [s.id for s in bench.skills]
    assert len(index["tasks"]) == 6 and all(t["gate"]["status"] == "passed" for t in index["tasks"])
    enc = index["encoders"]["fake:hash@v1"]
    assert set(enc["skill_vectors"]) == {s.id for s in bench.skills}
    assert skill_text(bench.skills[0]) == f"{bench.skills[0].name}: {bench.skills[0].description}"


def test_selection(index):
    cache = select_all(index, Environment("windows", 8192), ram_mode="fixed:8192", k=3, seed=0)
    run = cache["runs"][0]
    assert run["params"]["seed"] == 0 and run["params"]["ram_mode"] == "fixed:8192"
    assert run["params"]["os"] == "windows" and run["params"]["k"] == 3
    for task in run["tasks"].values():
        rows = task["ranking"]
        assert len(rows) == 41
        kept = [r for r in rows if not r["excluded"]]
        assert [r["rank"] for r in kept] == list(range(1, 39))
        assert [r["skill_id"] for r in rows if r["selected"]] == [r["skill_id"] for r in kept[:3]] == task["selected"]
        for r in rows:
            assert (r["reason"] is None) == (not r["excluded"])
            if r["excluded"]:
                assert r["rank"] is None and not r["selected"]
        scores = [r["score"] for r in kept]
        assert scores == sorted(scores, reverse=True)


def test_select_accepts_user_spec_and_rejects_unknown(index, monkeypatch):
    import skill_selection.encoders as encoders
    monkeypatch.setitem(encoders.PINNED_REVISIONS, "hash", "v1")       # let "st:hash" resolve like a pinned model
    index = {**index, "encoders": {"st:hash@v1": index["encoders"]["fake:hash@v1"]}}
    env = Environment("windows", 8192)
    run = select_all(index, env, ram_mode="fixed:8192", k=3, seed=0, encoders=["st:hash"])["runs"][0]
    assert run["params"]["encoder"] == "st:hash@v1"
    with pytest.raises(ValueError, match="not in the index"):
        select_all(index, env, ram_mode="fixed:8192", k=3, seed=0, encoders=["openai:text-embedding-3-small"])


def test_selection_is_byte_identical(index, tmp_path):
    env = Environment("windows", 8192)
    for name in ("a.json", "b.json"):
        write_json_stable(select_all(index, env, ram_mode="fixed:8192", k=3, seed=0), tmp_path / name)
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


def test_selection_needs_no_network(index, monkeypatch):
    def no_network(*a, **kw):
        raise AssertionError("selection tried to open a socket")
    monkeypatch.setattr(socket, "socket", no_network)
    select_all(index, Environment("windows", 8192), ram_mode="fixed:8192", k=3, seed=0)


def test_selection_does_not_import_models(index, tmp_path):
    path = tmp_path / "index.json"
    write_json_stable(index, path)
    code = ("import json, sys; from skill_selection.explorer import select_all; "
            "from skill_selection.filters.constraint import Environment; "
            f"select_all(json.load(open(r'{path}', encoding='utf-8')), Environment('windows', 8192), "
            "ram_mode='fixed:8192', k=3, seed=0); "
            "print(json.dumps(sorted(m for m in ('torch', 'sentence_transformers', 'openai') if m in sys.modules)))")
    src = str(Path(__file__).resolve().parents[2] / "src")    # works without `pip install -e .` too
    env = {**os.environ, "PYTHONPATH": os.pathsep.join(filter(None, [src, os.environ.get("PYTHONPATH")]))}
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, env=env).stdout
    assert json.loads(out) == []
