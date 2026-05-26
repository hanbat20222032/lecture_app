"""
tests/test_core.py  — core/ 모듈 단위 테스트
실행: python -m pytest tests/test_core.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
import numpy as np


# ── TextProcessor ──────────────────────────────────────
class TestTextProcessor:
    def setup_method(self):
        from core.text_processor import TextProcessor
        self.tp = TextProcessor()

    def test_detect_ko(self):
        assert self.tp.detect_language("소프트웨어 공학 방법론") == "ko"

    def test_detect_en(self):
        assert self.tp.detect_language("software engineering methodology") == "en"

    def test_detect_mixed(self):
        lang = self.tp.detect_language("소프트웨어 software 개발 development")
        assert lang in ("ko", "en", "mixed")

    def test_tokenize_ko_stopwords(self):
        # 조사와 분리된 단어만 토큰화됨 (공학은 → 공학은 통째로 추출)
        tokens = self.tp.tokenize("소프트웨어 공학 품질 개발", "ko")
        assert "소프트웨어" in tokens
        assert "공학" in tokens
        # 2글자 미만 제거 확인
        assert all(len(t) >= 2 for t in tokens)

    def test_tokenize_en_stopwords(self):
        tokens = self.tp.tokenize("software engineering is systematic approach", "en")
        assert "software" in tokens
        assert "engineering" in tokens
        assert "is" not in tokens
        assert "a" not in tokens

    def test_bigrams_normal(self):
        bigrams = self.tp.make_bigrams(["소프트웨어", "공학", "품질"])
        assert "소프트웨어_공학" in bigrams
        assert "공학_품질" in bigrams

    def test_bigrams_empty(self):
        assert self.tp.make_bigrams([]) == []
        assert self.tp.make_bigrams(["하나"]) == []

    def test_process_ko(self):
        text = ("소프트웨어 공학은 품질 높은 소프트웨어를 개발하는 방법론이다. "
                "요구사항 분석과 설계가 필요하다.")
        r = self.tp.process(text, "ko")
        assert r.token_count > 0
        assert r.sentence_count >= 1
        assert "소프트웨어" in r.tokens
        assert r.token_freq.get("소프트웨어", 0) >= 1

    def test_process_en(self):
        text = ("Machine learning is a subset of artificial intelligence. "
                "Neural networks learn from data automatically.")
        r = self.tp.process(text, "en")
        assert r.token_count > 0
        assert r.language == "en"

    def test_process_empty(self):
        r = self.tp.process("")
        assert r.token_count == 0
        assert r.sentence_count == 0

    def test_chunk_short(self):
        from core.text_processor import chunk_text
        assert len(chunk_text("짧은 텍스트", chunk_size=1000)) == 1

    def test_chunk_long(self):
        from core.text_processor import chunk_text
        chunks = chunk_text("가" * 2500, chunk_size=1000, overlap=100)
        assert len(chunks) == 3

    def test_fullwidth_normalize(self):
        result = self.tp.normalize("ａｂｃ　１２３")
        assert "abc" in result
        assert "123" in result


# ── TFIDFEngine ────────────────────────────────────────
class TestTFIDFEngine:
    def setup_method(self):
        from core.tfidf_engine import TFIDFEngine
        self.E = TFIDFEngine(max_features=30)

    def test_single_top_keyword(self):
        tokens = "소프트웨어 공학 소프트웨어 개발 소프트웨어".split()
        r = self.E.fit_single(tokens)
        assert r.keywords[0] == "소프트웨어"

    def test_single_scores_positive(self):
        r = self.E.fit_single("소프트웨어 공학 품질".split())
        assert all(s > 0 for s in r.scores)

    def test_multi_matrix_shape(self):
        corpus = ["소프트웨어 공학".split(), "알고리즘 분석".split(), "데이터 설계".split()]
        r = self.E.fit(corpus)
        assert r.tfidf_matrix.shape[0] == 3
        assert r.tfidf_matrix.shape[1] == len(r.vocab)

    def test_transform_shape(self):
        corpus = ["소프트웨어 공학".split(), "알고리즘 분석".split()]
        self.E.fit(corpus)
        vec = self.E.transform("소프트웨어".split())
        assert vec.shape[0] == self.E.vocabulary_size()

    def test_empty_input(self):
        r = self.E.fit_single([])
        assert r.keywords == [] and r.scores == []

    def test_top_n(self):
        tokens = "소프트웨어 소프트웨어 소프트웨어 공학 품질".split()
        top = self.E.fit_single(tokens).top_n(2)
        assert len(top) == 2
        assert top[0][0] == "소프트웨어"

    def test_as_dict(self):
        r = self.E.fit_single("소프트웨어 공학 품질".split())
        d = r.as_dict()
        assert isinstance(d, dict)
        assert "소프트웨어" in d


# ── TextRankEngine ────────────────────────────────────
class TestTextRank:
    def setup_method(self):
        from core.textrank import TextRankEngine
        self.E = TextRankEngine(top_n=5)

    def test_top_keyword(self):
        tokens = ("소프트웨어 공학 소프트웨어 개발 "
                  "소프트웨어 테스트 소프트웨어").split()
        kws, scores, iters = self.E.extract_keywords(tokens)
        assert kws[0] == "소프트웨어"
        assert all(s >= 0 for s in scores)

    def test_empty_tokens(self):
        kws, scores, _ = self.E.extract_keywords([])
        assert kws == []

    def test_sentences_count(self):
        sents  = ["소프트웨어 공학 중요.", "품질 관리 필수.", "날씨 맑음.", "요구사항 필요."]
        tokens = "소프트웨어 공학 품질 요구사항".split()
        result, scores = self.E.extract_sentences(sents, tokens)
        assert len(result) <= 5
        assert len(result) == len(scores)

    def test_run_returns_result(self):
        from core.textrank import TextRankResult
        tokens = "소프트웨어 공학 소프트웨어 품질".split()
        sents  = ["소프트웨어 공학 중요.", "품질 관리 필수."]
        r = self.E.run(tokens, sents)
        assert isinstance(r, TextRankResult)
        assert len(r.keywords) > 0


# ── CosineSim ─────────────────────────────────────────
class TestCosineSim:
    def test_identical(self):
        from core.cosine_sim import cosine_similarity
        v = np.array([1., 2., 3.])
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-6

    def test_orthogonal(self):
        from core.cosine_sim import cosine_similarity
        assert cosine_similarity(np.array([1.,0.]), np.array([0.,1.])) == pytest.approx(0.0, abs=1e-6)

    def test_zero_vector(self):
        from core.cosine_sim import cosine_similarity
        assert cosine_similarity(np.zeros(3), np.ones(3)) == 0.0

    def test_token_similarity_partial(self):
        from core.cosine_sim import cosine_similarity_tokens
        sim = cosine_similarity_tokens(["소프트웨어","공학"], ["소프트웨어","테스트"])
        assert 0.0 < sim < 1.0

    def test_token_similarity_identical(self):
        from core.cosine_sim import cosine_similarity_tokens
        a = ["소프트웨어", "공학"]
        assert cosine_similarity_tokens(a, a) == pytest.approx(1.0, abs=1e-6)

    def test_coverage_counts(self):
        from core.cosine_sim import compute_coverage
        cov = compute_coverage(
            ["소프트웨어","공학","알고리즘"],
            ["소프트웨어","공학"]
        )
        assert cov["covered_count"] == 2
        assert "알고리즘" in cov["missing"]
        assert 0.0 <= cov["coverage_rate"] <= 1.0

    def test_coverage_empty_source(self):
        from core.cosine_sim import compute_coverage
        assert compute_coverage([], ["토큰"])["coverage_rate"] == 1.0

    def test_keyword_density(self):
        from core.cosine_sim import compute_keyword_density
        d = compute_keyword_density(["a","b"], ["a","b","c","a"])
        assert abs(d - 0.75) < 1e-6


# ── InvertedIndex ─────────────────────────────────────
class TestInvertedIndex:
    def setup_method(self):
        from core.inverted_index import InvertedIndex
        self.idx = InvertedIndex()
        self.idx.build(["소프트웨어","공학","품질","소프트웨어","개발"], 1, "문서1")
        self.idx.build(["알고리즘","자료구조","소프트웨어"], 2, "문서2")

    def test_search_finds_both_docs(self):
        assert len(self.idx.search("소프트웨어")) == 2

    def test_search_no_result(self):
        assert len(self.idx.search("존재안함xyz999")) == 0

    def test_and_search(self):
        docs = self.idx.search_and(["소프트웨어","공학"])
        assert 1 in docs and 2 not in docs

    def test_or_search(self):
        docs = self.idx.search_or(["소프트웨어","알고리즘"])
        assert 1 in docs and 2 in docs

    def test_tf_value(self):
        assert self.idx.get_tf("소프트웨어", 1) == pytest.approx(2/5, abs=1e-6)

    def test_top_words(self):
        assert self.idx.get_top_words(1, 1)[0][0] == "소프트웨어"

    def test_keywords_coverage(self):
        cov = self.idx.keywords_coverage(["소프트웨어","없는단어"], 1)
        assert cov["소프트웨어"] == 2
        assert cov["없는단어"] == 0

    def test_clear(self):
        self.idx.clear()
        assert self.idx.doc_count() == 0
        assert self.idx.word_count() == 0

    def test_doc_count(self):
        assert self.idx.doc_count() == 2

    def test_word_count_positive(self):
        assert self.idx.word_count() > 0
