import math

import pytest

from skill_selection.schemas import QueryRecord, SkillRecord
from skill_selection.selectors import BM25Selector, RandomSelector, build_selector
from skill_selection.selectors.bm25 import tokenize


def skill(i, name, desc, body=""):
    return SkillRecord(id=i, name=name, description=desc, body=body, source="test")


CATALOG = [
    skill("s1", "pytest-runner", "Run the pytest suite and report failures"),
    skill("s2", "git-conflict", "Resolve git merge conflict markers"),
    skill("s3", "docker-inspect", "Inspect a running docker container"),
    skill("s4", "pytest-fixtures", "Explain pytest fixtures"),
]


def q(text, qid="q"):
    return QueryRecord(id=qid, text=text, source="test")


def test_tokenize_lowercases_drops_stopwords_and_single_chars():
    assert tokenize("Run THE tests, a b of pytest-x") == ["run", "tests", "pytest"]


def test_bm25_ranks_matching_skills_and_drops_zero_scores():
    sel = BM25Selector()
    sel.fit(CATALOG)
    res = sel.select(q("merge conflict in git"), k=3)
    assert res.skill_ids == ["s2"]
    res = sel.select(q("pytest failures"), k=3)
    assert res.skill_ids[0] == "s1"                     # matches both terms
    assert set(res.skill_ids) == {"s1", "s4"}
    assert res.scores == sorted(res.scores, reverse=True)


def test_bm25_single_term_score_matches_formula():
    sel = BM25Selector(k1=1.5, b=0.75)
    sel.fit(CATALOG)
    docs = [tokenize(s.text()) for s in CATALOG]
    avgdl = sum(map(len, docs)) / len(docs)
    df = sum("docker" in d for d in docs)
    idf = math.log(1 + (len(docs) - df + 0.5) / (df + 0.5))
    tf, dl = docs[2].count("docker"), len(docs[2])
    expected = idf * tf / (tf + 1.5 * (1 - 0.75 + 0.75 * dl / avgdl))
    assert sel.scores("docker")[2] == pytest.approx(expected)


def test_bm25_unknown_terms_return_nothing():
    sel = BM25Selector()
    sel.fit(CATALOG)
    assert sel.select(q("kubernetes helm"), k=5).skill_ids == []


def test_random_is_deterministic_per_query_regardless_of_query_order():
    sel = RandomSelector(seed=7)
    sel.fit(CATALOG)
    first = sel.select(q("x", "q1"), k=2).skill_ids
    sel.select(q("y", "q2"), k=2)
    assert first == sel.select(q("x", "q1"), k=2).skill_ids
    assert len(first) == len(set(first)) == 2
    assert len(sel.select(q("x", "q1"), k=10).skill_ids) == len(CATALOG)
    assert isinstance(build_selector("random", seed=1), RandomSelector)


def test_unknown_selector():
    with pytest.raises(ValueError):
        build_selector("nope")
