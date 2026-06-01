"""
tests/test_tfidf.py
core/tfidf_engine.py 테스트
"""
import pytest
import numpy as np
from core.tfidf_engine import TFIDFEngine, TFIDFResult, compute_tfidf_single


@pytest.fixture
def engine():
    return TFIDFEngine()


@pytest.fixture
def ko_tokens():
    return ["응집력", "모듈", "결합력", "응집력", "설계", "모듈화",
            "추상화", "캡슐화", "응집력", "결합력", "다형성", "상속"]


@pytest.fixture
def ko_corpus():
    return [
        ["응집력", "모듈", "결합력", "설계", "원칙"],
        ["응집력", "높음", "결합력", "낮음", "좋음"],
        ["모듈화", "시스템", "분해", "모듈", "관리"],
        ["추상화", "본질", "세부사항", "캡슐화"],
        ["다형성", "상속", "캡슐화", "객체지향", "원칙"],
    ]


class TestFitSingle:
    def test_returns_tfidf_result(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        assert isinstance(result, TFIDFResult)

    def test_has_keywords_and_scores(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        assert len(result.keywords) > 0
        assert len(result.scores) == len(result.keywords)

    def test_frequent_word_high_rank(self, engine, ko_tokens):
        """자주 등장한 '응집력'이 상위권"""
        result = engine.fit_single(ko_tokens)
        top5 = result.keywords[:5]
        assert "응집력" in top5, f"상위 5개: {top5}"

    def test_scores_positive(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        assert all(s > 0 for s in result.scores)

    def test_scores_sorted_desc(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        assert result.scores == sorted(result.scores, reverse=True)

    def test_empty_tokens(self, engine):
        result = engine.fit_single([])
        assert result.keywords == []
        assert result.scores == []

    def test_max_features_limit(self, engine, ko_tokens):
        engine2 = TFIDFEngine(max_features=3)
        result = engine2.fit_single(ko_tokens)
        assert len(result.keywords) <= 3

    def test_top_n(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        top3 = result.top_n(3)
        assert len(top3) <= 3
        assert all(isinstance(t, tuple) and len(t) == 2 for t in top3)

    def test_as_dict(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        d = result.as_dict()
        assert isinstance(d, dict)
        assert all(isinstance(v, float) for v in d.values())

    def test_unique_keywords(self, engine, ko_tokens):
        result = engine.fit_single(ko_tokens)
        assert len(result.keywords) == len(set(result.keywords))


class TestFitCorpus:
    def test_returns_tfidf_result(self, engine, ko_corpus):
        result = engine.fit(ko_corpus)
        assert isinstance(result, TFIDFResult)

    def test_has_matrix(self, engine, ko_corpus):
        result = engine.fit(ko_corpus)
        assert result.tfidf_matrix is not None
        assert result.tfidf_matrix.shape[0] == len(ko_corpus)

    def test_empty_corpus(self, engine):
        result = engine.fit([])
        assert result.keywords == []

    def test_is_fitted_after_fit(self, engine, ko_corpus):
        engine.fit(ko_corpus)
        assert engine.is_fitted() is True

    def test_not_fitted_initially(self):
        e = TFIDFEngine()
        assert e.is_fitted() is False


class TestComputeTfidfSingle:
    def test_returns_list_of_tuples(self, ko_tokens):
        result = compute_tfidf_single(ko_tokens, top_n=5)
        assert isinstance(result, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in result)

    def test_top_n_limit(self, ko_tokens):
        result = compute_tfidf_single(ko_tokens, top_n=3)
        assert len(result) <= 3
