"""
tests/test_analysis.py  — analysis/ 모듈 단위 테스트
실행: python -m pytest tests/test_analysis.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from database.db_manager import initialize_db
initialize_db()


# ── ConceptExtractor ──────────────────────────────────
class TestConceptExtractor:
    def setup_method(self):
        from core.text_processor import TextProcessor
        from analysis.concept_extractor import ConceptExtractor
        self.tp = TextProcessor()
        self.ex = ConceptExtractor(max_keywords=20)
        text = ("소프트웨어 공학은 품질 높은 소프트웨어를 개발하는 체계적 방법론이다. "
                "이를 위해 요구사항 분석, 설계, 구현, 테스트 단계를 거친다. "
                "소프트웨어 품질 관리는 매우 중요하다. "
                "테스트는 결함을 발견하고 품질을 보증하는 과정이다.")
        self.processed = self.tp.process(text, "ko")

    def test_extract_returns_keywords(self):
        r = self.ex.extract(self.processed, doc_id=999, save_to_db=False)
        assert r.keyword_count > 0

    def test_extract_top_is_frequent(self):
        r = self.ex.extract(self.processed, doc_id=999, save_to_db=False)
        top_words = [k.word for k in r.top_keywords[:5]]
        # 소프트웨어가 가장 많이 등장하므로 상위권
        assert any(w in ("소프트웨어","품질","테스트") for w in top_words)

    def test_extract_scores_in_range(self):
        r = self.ex.extract(self.processed, doc_id=999, save_to_db=False)
        for kw in r.keywords:
            assert kw.tfidf_score >= 0.0
            assert kw.textrank_score >= 0.0

    def test_extract_language(self):
        r = self.ex.extract(self.processed, doc_id=999, save_to_db=False)
        assert r.language in ("ko", "en", "mixed")

    def test_extract_empty_text(self):
        from core.text_processor import TextProcessor
        tp = TextProcessor()
        empty = tp.process("", "ko")
        r = self.ex.extract(empty, doc_id=999, save_to_db=False)
        assert r.keyword_count == 0

    def test_combined_score(self):
        r = self.ex.extract(self.processed, doc_id=999, save_to_db=False)
        for kw in r.keywords:
            expected = round(kw.tfidf_score * 0.6 + kw.textrank_score * 0.4, 6)
            assert abs(kw.combined_score - expected) < 1e-5

    def test_get_missing_concepts(self):
        from analysis.concept_extractor import get_missing_concepts
        src = ["소프트웨어","공학","알고리즘","테스트"]
        tgt = ["소프트웨어","공학","개발","품질"]
        missing = get_missing_concepts(src, tgt)
        assert "알고리즘" in missing
        assert "소프트웨어" not in missing


# ── CoverageCalc ──────────────────────────────────────
class TestCoverageCalc:
    def test_full_coverage(self):
        from analysis.coverage_calc import calc_coverage
        src_kw  = ["소프트웨어","공학","테스트"]
        src_tok = ["소프트웨어","공학","테스트","품질"]
        tgt_tok = ["소프트웨어","공학","테스트","개발"]
        r = calc_coverage(src_kw, src_tok, tgt_tok)
        assert r.covered_count == 3
        assert r.missing_count == 0
        assert r.coverage_pct == 100.0

    def test_partial_coverage(self):
        from analysis.coverage_calc import calc_coverage
        src_kw  = ["소프트웨어","공학","알고리즘","자료구조"]
        src_tok = src_kw[:]
        tgt_tok = ["소프트웨어","공학","개발","품질"]
        r = calc_coverage(src_kw, src_tok, tgt_tok)
        assert r.covered_count == 2
        assert r.coverage_pct < 100.0

    def test_zero_coverage(self):
        from analysis.coverage_calc import calc_coverage
        r = calc_coverage(["알고리즘","자료구조"], ["알고리즘"], ["설계","구현"])
        assert r.covered_count == 0

    def test_empty_keywords(self):
        from analysis.coverage_calc import calc_coverage
        # 분석할 키워드 없음 → 0.0 (측정 불가)
        r = calc_coverage([], ["소프트웨어"], ["소프트웨어"])
        assert r.coverage_rate == 0.0
        assert r.covered_count == 0

    def test_empty_target(self):
        from analysis.coverage_calc import calc_coverage
        r = calc_coverage(["소프트웨어"], ["소프트웨어"], [])
        assert r.coverage_rate == 0.0


# ── GapDetector ───────────────────────────────────────
class TestGapDetector:
    def _make_report(self, covered, partial, missing):
        from analysis.coverage_calc import CoverageReport
        return CoverageReport(
            coverage_rate  = len(covered) / max(len(covered)+len(missing), 1),
            covered        = covered,
            partial        = partial,
            missing        = missing,
            keyword_density= 0.3,
            similarity     = 0.5,
            covered_count  = len(covered),
            partial_count  = len(partial),
            missing_count  = len(missing),
        )

    def test_missing_detected(self):
        from analysis.gap_detector import detect_gaps
        cov = self._make_report(["소프트웨어"], [], ["알고리즘","테스트"])
        scores = {"소프트웨어":0.9,"알고리즘":0.7,"테스트":0.5}
        gap = detect_gaps(cov, scores)
        assert gap.missing_count == 2
        assert gap.items[0].word == "알고리즘"  # 높은 점수 먼저

    def test_no_gap(self):
        from analysis.gap_detector import detect_gaps
        cov = self._make_report(["소프트웨어","공학"], [], [])
        gap = detect_gaps(cov, {"소프트웨어":0.9,"공학":0.7})
        assert gap.missing_count == 0
        assert len(gap.items) == 0

    def test_partial_category(self):
        from analysis.gap_detector import detect_gaps
        cov = self._make_report(["소프트웨어"], ["공학"], ["알고리즘"])
        gap = detect_gaps(cov, {"소프트웨어":0.9,"공학":0.7,"알고리즘":0.5})
        categories = [i.category for i in gap.items]
        assert "partial" in categories
        assert "missing" in categories

    def test_to_json_list(self):
        from analysis.gap_detector import detect_gaps
        cov = self._make_report([], [], ["알고리즘","테스트"])
        gap = detect_gaps(cov, {"알고리즘":0.7,"테스트":0.5})
        jlist = gap.to_json_list()
        assert isinstance(jlist, list)
        assert "알고리즘" in jlist


# ── Scorer ────────────────────────────────────────────
class TestScorer:
    def test_perfect_score(self):
        from analysis.scorer import calculate_score
        bd = calculate_score(10, 10, 1.0, 1.0)
        assert bd.total_score == 100.0
        assert bd.grade == "A"
        assert bd.passed is True

    def test_zero_score(self):
        from analysis.scorer import calculate_score
        bd = calculate_score(0, 10, 0.0, 0.0)
        assert bd.total_score == 0.0
        assert bd.grade == "F"
        assert bd.passed is False

    def test_pass_threshold(self):
        from analysis.scorer import calculate_score
        # quiz=80, cov=50, density=30 → 0.6×80 + 0.3×50 + 0.1×30 = 48+15+3 = 66
        bd = calculate_score(8, 10, 0.5, 0.3)
        assert bd.passed is True
        assert bd.total_score == pytest.approx(66.0, abs=0.1)

    def test_score_in_range(self):
        from analysis.scorer import calculate_score
        bd = calculate_score(5, 10, 0.6, 0.4)
        assert 0.0 <= bd.total_score <= 100.0

    def test_grade_mapping(self):
        from analysis.scorer import calculate_score
        assert calculate_score(10, 10, 1.0, 1.0).grade == "A"
        assert calculate_score(8, 10, 0.8, 0.8).grade in ("A","B")
        assert calculate_score(0, 10, 0.0, 0.0).grade == "F"

    def test_quiz_score_calc(self):
        from analysis.scorer import calculate_score
        bd = calculate_score(7, 10, 0.5, 0.5)
        assert bd.quiz_score == pytest.approx(70.0, abs=0.01)

    def test_zero_total_questions(self):
        from analysis.scorer import calculate_score
        bd = calculate_score(0, 0, 0.5, 0.5)
        assert 0.0 <= bd.total_score <= 100.0
