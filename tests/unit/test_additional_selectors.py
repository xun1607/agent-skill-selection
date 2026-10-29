import math

import numpy as np
import pytest

from skill_selection.schemas import QueryRecord, SkillRecord
from skill_selection.selectors import build_selector
from skill_selection.selectors.tfidf import TFIDFSelector
from skill_selection.selectors.minilm import MiniLMSelector


def skill(name, body):
    return SkillRecord(name, "", "", body, "test")


def query(text):
    return QueryRecord("q", text, "test")


def test_tfidf_matches_hand_calculated_cosine():
    selector = TFIDFSelector()
    selector.fit([skill("a", "alpha alpha beta"), skill("b", "beta gamma")])
    result = selector.select(query("alpha"), 2)
    idf = math.log(3 / 2) + 1
    alpha_weight = (1 + math.log(2)) * idf
    expected = alpha_weight / math.sqrt(alpha_weight ** 2 + 1)
    assert result.skill_ids == ["a"]
    assert result.scores == pytest.approx([expected])


def test_tfidf_empty_oov_zero_k_and_stable_ties():
    selector = TFIDFSelector()
    selector.fit([skill("first", "alpha"), skill("second", "alpha")])
    assert selector.select(query("alpha"), 10).skill_ids == ["first", "second"]
    assert selector.select(query("unknown"), 5).skill_ids == []
    assert selector.select(query("alpha"), 0).skill_ids == []
    selector.fit([])
    assert selector.select(query("alpha"), 5).skill_ids == []


def test_tfidf_fits_only_catalog_and_does_not_change_idf_on_queries():
    selector = TFIDFSelector()
    selector.fit([skill("a", "alpha"), skill("b", "beta")])
    before = selector._idf.copy()
    first = selector.select(query("alpha"), 2)
    selector.select(query("alpha new words"), 2)
    assert np.array_equal(selector._idf, before)
    assert selector.select(query("alpha"), 2).skill_ids == first.skill_ids


class FakeEncoder:
    def __init__(self):
        self.calls = []

    def encode(self, texts, kind):
        self.calls.append((texts, kind))
        return np.array([[1, 0], [1, 0], [0, 1]], dtype=np.float32) if kind == "document" else np.array([[1, 0]], dtype=np.float32)


def test_minilm_reuses_encoder_and_stable_cosine_ranker_without_loading_model():
    encoder = FakeEncoder()
    selector = MiniLMSelector(encoder=encoder)
    selector.fit([skill("a", "alpha"), skill("b", "alpha"), skill("c", "beta")])
    result = selector.select(query("alpha"), 2)
    assert result.skill_ids == ["a", "b"]
    assert result.scores == [1, 1]
    assert [kind for _, kind in encoder.calls] == ["document", "query"]
    assert encoder.calls[0][0] == [s.text() for s in selector.catalog]
    assert selector.select(query("alpha"), 0).skill_ids == []
    assert selector.config()["max_seq_length"] == 256


@pytest.mark.parametrize("name", ["tfidf", "minilm"])
def test_registered_baselines_and_invalid_k(name):
    selector = build_selector(name)
    with pytest.raises(ValueError, match="non-negative"):
        selector.select(query("alpha"), -1)


def test_tfidf_reuses_existing_offline_runner(tmp_path):
    from skill_selection.experiments.runner import run_offline
    result = run_offline(TFIDFSelector(), [skill("a", "alpha"), skill("b", "beta")],
                         [query("alpha")], {"q": {"a": 1}}, k=15,
                         dataset={"name": "toy", "split": "test"}, out_root=tmp_path)
    assert result.report.mean["Recall@10"] == 1
    assert result.report.n_evaluated == 1
    assert all((result.run_dir / name).exists() for name in ["manifest.json", "run.jsonl", "metrics.json", "per_query.csv", "report.md"])
