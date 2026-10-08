"""White-box tests of the baseline components (no model download: fake models / hand-made graphs).
Each test records its testcase id (TC-...) and its actual output for the testcase workbook."""
from types import SimpleNamespace

import numpy as np
import pytest

from skill_selection.encoders import MODEL_PROFILES, canonical_spec, parse_encoder_spec
from skill_selection.encoders.hf_encoder import LastTokenEncoder
from skill_selection.rerankers import QWEN_RERANK_PREFIX, QWEN_RERANK_SUFFIX, YesNoReranker
from skill_selection.selectors.gos_lite import dependency_graph, gos_lite, personalized_pagerank, rrf


def skill(id, body="", desc="d"):
    return SimpleNamespace(id=id, name=id, description=desc, body=body)


def test_skillrouter_reranker_prompt_matches_model_card(record_property):
    record_property("tc", "TC-BL-SR-01")
    r = YesNoReranker()
    p = r.prompt("fix the bug", "git-x", "D" * 600, "B" * 2500)
    want = ("<Instruct>: Given a task description, judge whether the skill document is relevant and useful for "
            "completing the task\n\n<Query>: fix the bug\n\n<Document>: git-x | " + "D" * 500 + " | " + "B" * 2000)
    assert p == want
    assert QWEN_RERANK_PREFIX.startswith("<|im_start|>system\nJudge whether the Document meets the requirements")
    assert QWEN_RERANK_SUFFIX == "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
    record_property("actual", "prompt khớp model card: desc cắt 500, body cắt 2000, đúng tiền tố/hậu tố")


def test_reranker_cache_avoids_model(tmp_path, record_property):
    record_property("tc", "TC-BL-SR-02")
    calls = []
    r = YesNoReranker(cache_path=tmp_path / "c.json")
    r._score_one = lambda p: calls.append(p) or float(len(p) % 7)
    s1 = r.score("q", [skill("a", "x"), skill("b", "yy")])
    r2 = YesNoReranker(cache_path=tmp_path / "c.json")
    r2._score_one = lambda p: pytest.fail("model called although cached")
    assert r2.score("q", [skill("a", "x"), skill("b", "yy")]) == s1 and len(calls) == 2
    record_property("actual", "lần 2 đọc từ cache, không gọi mô hình; điểm giống hệt")


def test_skillrouter_embedding_query_format(record_property):
    record_property("tc", "TC-BL-SR-03")
    prof = MODEL_PROFILES["pipizhao/SkillRouter-Embedding-0.6B"]
    enc = LastTokenEncoder("pipizhao/SkillRouter-Embedding-0.6B", prof["revision"], prof["query_instruction"])
    assert enc.query_text("Sửa lỗi") == ("Instruct: Given a task description, retrieve the most relevant skill "
                                         "document that would help an agent complete the task\nQuery:Sửa lỗi")
    assert canonical_spec("hf:pipizhao/SkillRouter-Embedding-0.6B").endswith("@" + prof["revision"])
    assert enc.info()["max_seq_length"] == 4096
    record_property("actual", "query = instruction + văn bản (không dấu cách), max 4096, revision ghim")


def test_all_models_pinned(record_property):
    record_property("tc", "TC-BL-ALL-01")
    for model in MODEL_PROFILES:
        backend = "hf" if "SkillRouter" in model else "st"
        assert len(parse_encoder_spec(f"{backend}:{model}")[2]) == 40
    record_property("actual", f"{len(MODEL_PROFILES)} mô hình, mỗi mô hình ghim commit 40 ký tự")


def test_gos_graph_from_declared_and_mentioned(record_property):
    record_property("tc", "TC-BL-GOS-01")
    skills = [skill("debug-python-error", "First run analyze-stacktrace, then suggest-python-fix."),
              skill("analyze-stacktrace", "Read the trace."), skill("suggest-python-fix", "Write a fix."),
              skill("git", "mentions debug-python-error-extra only")]
    md = {"debug-python-error": "---\nname: debug-python-error\nsub_skills:\n  - analyze-stacktrace  # step 1\n---\nbody"}
    g = dependency_graph(skills, md)
    assert g["debug-python-error"] == ["analyze-stacktrace", "suggest-python-fix"]
    assert g["git"] == []                                    # "debug-python-error-extra" is not the id
    record_property("actual", f"cạnh: {g['debug-python-error']}")


def test_gos_reverse_weighted_ppr(record_property):
    record_property("tc", "TC-BL-GOS-02")
    ids = ["u", "v", "w"]
    graph = {"u": ["v"], "v": [], "w": []}
    x = personalized_pagerank(ids, graph, {"u": 1.0}, gamma_r=0.5)
    assert abs(x.sum() - 1) < 1e-9 and x[1] > 0 and x[2] == 0      # prerequisite v reached, unrelated w not
    y = personalized_pagerank(ids, graph, {"v": 1.0}, gamma_r=0.0)
    z = personalized_pagerank(ids, graph, {"v": 1.0}, gamma_r=0.5)
    assert y[0] == 0 and z[0] > 0                                   # only reverse edges lead from v back to u
    record_property("actual", f"tổng={x.sum():.6f}; v nhận {x[1]:.3f}; cạnh ngược đưa u từ 0 lên {z[0]:.3f}")


def test_gos_bundle_budget(record_property):
    record_property("tc", "TC-BL-GOS-03")
    ids = [f"s{i}" for i in range(12)]
    ranking, bundle, _ = gos_lite(ids, ids, ids[::-1], {i: [] for i in ids}, {i: 3000 for i in ids})
    assert sorted(ranking) == sorted(ids) and len(bundle) == 4      # 4 x 3000 chars = 12,000 budget
    assert rrf([["a", "b"], ["b", "a"]])["a"] == rrf([["a", "b"], ["b", "a"]])["b"]
    record_property("actual", f"thứ hạng đủ {len(ranking)} skill; gói {len(bundle)} skill (ngân sách 12.000 ký tự)")
