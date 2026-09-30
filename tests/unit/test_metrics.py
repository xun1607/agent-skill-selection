import math

import pytest

from skill_selection.evaluation.metrics import (completeness_at_k, evaluate, map_at_k, ndcg_at_k,
                                                precision_at_k, recall_at_k)

RANKED = ["a", "b", "c"]
RELS = {"a": 1, "c": 1}


def test_binary_metrics_by_hand():
    ideal = 1 + 1 / math.log2(3)
    assert ndcg_at_k(RANKED, RELS, 3) == pytest.approx((1 + 1 / math.log2(4)) / ideal)
    assert ndcg_at_k(RANKED, RELS, 1) == pytest.approx(1.0)
    assert recall_at_k(RANKED, RELS, 1) == 0.5
    assert recall_at_k(RANKED, RELS, 3) == 1.0
    assert precision_at_k(RANKED, RELS, 3) == pytest.approx(2 / 3)
    assert map_at_k(RANKED, RELS, 3) == pytest.approx((1 / 1 + 2 / 3) / 2)
    assert completeness_at_k(RANKED, RELS, 1) == 0.0
    assert completeness_at_k(RANKED, RELS, 3) == 1.0


def test_precision_divides_by_k_and_map_by_all_relevant():
    assert precision_at_k(["a"], RELS, 5) == pytest.approx(1 / 5)
    assert map_at_k(["a"], RELS, 5) == pytest.approx(1 / 2)


def test_graded_ndcg_uses_relevance_as_gain():
    rels = {"x": 2, "y": 1}
    ideal = 2 + 1 / math.log2(3)
    assert ndcg_at_k(["y", "x"], rels, 2) == pytest.approx((1 + 2 / math.log2(3)) / ideal)


def test_evaluate_skips_queries_without_relevant_and_zeroes_missing():
    qrels = {"q1": {"a": 1}, "q2": {"b": 0}, "q3": {"c": 1}}
    report = evaluate({"q1": ["a", "z"]}, qrels, ks=(1,))
    assert report.n_evaluated == 2
    assert report.n_skipped_no_relevant == 1
    assert report.n_missing_from_run == 1
    assert report.per_query["q1"]["NDCG@1"] == 1.0
    assert report.per_query["q3"]["NDCG@1"] == 0.0
    assert report.mean["Recall@1"] == 0.5
    assert report.mean["n_selected"] == 1.0            # q1 returned 2 skills, q3 returned none


def test_evaluate_rejects_duplicate_skills():
    with pytest.raises(ValueError):
        evaluate({"q1": ["a", "a"]}, {"q1": {"a": 1}}, ks=(1,))
