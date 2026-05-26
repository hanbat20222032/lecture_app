"""
tests/test_quiz.py  — quiz/ 모듈 단위 테스트
실행: python -m pytest tests/test_quiz.py -v
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from database.db_manager import initialize_db
initialize_db()

SENTENCES = [
    "소프트웨어 공학은 체계적인 개발 방법론을 다루는 학문이다.",
    "품질 좋은 소프트웨어를 만들기 위해 테스트가 중요하다.",
    "요구사항 분석은 개발의 첫 번째 단계이다.",
    "설계 패턴은 반복되는 문제를 해결하는 방법이다.",
    "소프트웨어 유지보수는 배포 이후에도 계속된다.",
    "알고리즘은 문제 해결을 위한 절차이다.",
    "자료구조는 데이터를 효율적으로 저장하는 방법이다.",
]
KEYWORDS = ["소프트웨어","공학","테스트","요구사항","설계","알고리즘","자료구조"]


# ── blank_type ────────────────────────────────────────
class TestBlankType:
    def test_generates_requested_count(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=5)
        assert len(quizzes) == 5

    def test_all_blank_type(self):
        from quiz.blank_type import generate_blank_quizzes
        from database.models import QuizType
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=5)
        assert all(q.quiz_type == QuizType.BLANK for q in quizzes)

    def test_blank_marker_present(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=5)
        assert all("[____]" in q.question for q in quizzes)

    def test_answer_is_keyword(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=5)
        kw_set = set(KEYWORDS)
        assert all(q.answer in kw_set for q in quizzes)

    def test_context_contains_answer(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=5)
        assert all(q.answer in q.context for q in quizzes)

    def test_empty_keywords(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, [], doc_id=0, count=5)
        assert quizzes == []

    def test_empty_sentences(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes([], KEYWORDS, doc_id=0, count=5)
        assert quizzes == []

    def test_count_limit(self):
        from quiz.blank_type import generate_blank_quizzes
        quizzes = generate_blank_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=2)
        assert len(quizzes) <= 2


# ── ox_type ───────────────────────────────────────────
class TestOXType:
    def test_generates_quizzes(self):
        from quiz.ox_type import generate_ox_quizzes
        quizzes = generate_ox_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=6)
        assert len(quizzes) >= 1

    def test_all_ox_type(self):
        from quiz.ox_type import generate_ox_quizzes
        from database.models import QuizType
        quizzes = generate_ox_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=6)
        assert all(q.quiz_type == QuizType.OX for q in quizzes)

    def test_answer_is_o_or_x(self):
        from quiz.ox_type import generate_ox_quizzes
        quizzes = generate_ox_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=6)
        assert all(q.answer in ("O","X") for q in quizzes)

    def test_roughly_balanced(self):
        from quiz.ox_type import generate_ox_quizzes
        quizzes = generate_ox_quizzes(SENTENCES, KEYWORDS, doc_id=0, count=6)
        o_count = sum(1 for q in quizzes if q.answer == "O")
        x_count = sum(1 for q in quizzes if q.answer == "X")
        # O:X = 1:1 ± 2 허용
        assert abs(o_count - x_count) <= 2

    def test_empty_keywords(self):
        from quiz.ox_type import generate_ox_quizzes
        assert generate_ox_quizzes(SENTENCES, [], doc_id=0, count=5) == []


# ── evaluator ─────────────────────────────────────────
class TestEvaluator:
    def _make_blank_quiz(self, answer="소프트웨어"):
        from database.models import Quiz, QuizType
        return Quiz(
            document_id=0, quiz_type=QuizType.BLANK,
            question=f"[____] 공학은 중요하다.", answer=answer, keyword=answer,
        )

    def _make_ox_quiz(self, answer="O"):
        from database.models import Quiz, QuizType
        return Quiz(
            document_id=0, quiz_type=QuizType.OX,
            question="소프트웨어 공학은 중요하다.", answer=answer, keyword="소프트웨어",
        )

    def test_blank_correct(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_blank_quiz("소프트웨어"), "소프트웨어")
        assert r.is_correct is True

    def test_blank_wrong(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_blank_quiz("소프트웨어"), "알고리즘")
        assert r.is_correct is False

    def test_blank_case_insensitive(self):
        from database.models import Quiz, QuizType
        from quiz.evaluator import check_answer
        q = Quiz(document_id=0, quiz_type=QuizType.BLANK,
                 question="[____] is important.", answer="Software", keyword="Software")
        assert check_answer(q, "software").is_correct is True
        assert check_answer(q, "SOFTWARE").is_correct is True

    def test_blank_whitespace_ignored(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_blank_quiz("소프트웨어"), "  소프트웨어  ")
        assert r.is_correct is True

    def test_ox_correct_o(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_ox_quiz("O"), "O")
        assert r.is_correct is True

    def test_ox_correct_x(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_ox_quiz("X"), "X")
        assert r.is_correct is True

    def test_ox_wrong(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_ox_quiz("O"), "X")
        assert r.is_correct is False

    def test_feedback_correct(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_blank_quiz(), "소프트웨어")
        assert "정답" in r.feedback

    def test_feedback_wrong(self):
        from quiz.evaluator import check_answer
        r = check_answer(self._make_blank_quiz(), "틀린답")
        assert "오답" in r.feedback
        assert "소프트웨어" in r.feedback


# ── generator ────────────────────────────────────────
class TestGenerator:
    def test_generate_without_db(self):
        from quiz.generator import QuizGenerator
        from database.models import Keyword
        kws = [Keyword(document_id=0, word=w, tfidf_score=0.5, textrank_score=0.4)
               for w in KEYWORDS]
        text = " ".join(SENTENCES)
        gen = QuizGenerator(blank_count=3, ox_count=3)
        result = gen.generate(0, text, kws, save=False)
        assert result.total_count > 0
        assert len(result.blank_quizzes) <= 3
        assert len(result.ox_quizzes) <= 3

    def test_generate_empty_keywords(self):
        from quiz.generator import QuizGenerator
        result = QuizGenerator().generate(0, "텍스트", [], save=False)
        assert result.total_count == 0

    def test_generate_empty_content(self):
        from quiz.generator import QuizGenerator
        from database.models import Keyword
        kws = [Keyword(document_id=0, word="소프트웨어", tfidf_score=0.5, textrank_score=0.4)]
        result = QuizGenerator().generate(0, "", kws, save=False)
        assert result.total_count == 0

    def test_all_quizzes_property(self):
        from quiz.generator import QuizGenerator
        from database.models import Keyword
        kws = [Keyword(document_id=0, word=w, tfidf_score=0.5, textrank_score=0.4)
               for w in KEYWORDS]
        result = QuizGenerator(blank_count=2, ox_count=2).generate(
            0, " ".join(SENTENCES), kws, save=False
        )
        assert len(result.all_quizzes) == (
            len(result.blank_quizzes) + len(result.ox_quizzes)
        )
