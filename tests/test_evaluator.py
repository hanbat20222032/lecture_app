"""
tests/test_evaluator.py
quiz/evaluator.py 테스트

check_answer() 채점 로직 검증
"""
import pytest
from unittest.mock import patch, MagicMock
from database.models import Quiz, QuizType
from quiz.evaluator import check_answer, EvalResult


def make_blank_quiz(answer: str, keyword: str = None) -> Quiz:
    """빈칸 테스트용 Quiz 객체 생성"""
    return Quiz(
        document_id=1,
        quiz_type=QuizType.BLANK,
        question=f"[____]은 모듈 내 요소들의 연관성이다.",
        answer=answer,
        context=f"{answer}은 모듈 내 요소들의 연관성이다.",
        keyword=keyword or answer,
    )


def make_ox_quiz(answer: str, keyword: str = "응집력") -> Quiz:
    """OX 테스트용 Quiz 객체 생성"""
    return Quiz(
        document_id=1,
        quiz_type=QuizType.OX,
        question="응집력은 높을수록 좋다.",
        answer=answer,
        context="응집력은 높을수록 좋다.",
        keyword=keyword,
    )


# ── 빈칸 채점 ─────────────────────────────────────────────────
class TestCheckAnswerBlank:
    def test_exact_match(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert result.is_correct is True

    def test_wrong_answer(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "결합력")
        assert result.is_correct is False

    def test_case_insensitive(self):
        """대소문자 무시 (영문 키워드)"""
        quiz = make_blank_quiz("Cohesion")
        result = check_answer(quiz, "cohesion")
        assert result.is_correct is True

    def test_whitespace_ignored(self):
        """공백 무시"""
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, " 응집력 ")
        assert result.is_correct is True

    def test_empty_answer_wrong(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "")
        assert result.is_correct is False

    def test_returns_eval_result(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert isinstance(result, EvalResult)

    def test_correct_ans_in_result(self):
        """결과에 정답이 포함"""
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "오답")
        assert result.correct_ans == "응집력"

    def test_user_answer_stored(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "내답변")
        assert result.user_answer == "내답변"

    def test_feedback_correct(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert "정답" in result.feedback or "✓" in result.feedback

    def test_feedback_wrong(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "오답")
        assert "오답" in result.feedback or "✗" in result.feedback


# ── OX 채점 ──────────────────────────────────────────────────
class TestCheckAnswerOX:
    def test_correct_o(self):
        quiz = make_ox_quiz("O")
        result = check_answer(quiz, "O")
        assert result.is_correct is True

    def test_correct_x(self):
        quiz = make_ox_quiz("X")
        result = check_answer(quiz, "X")
        assert result.is_correct is True

    def test_wrong_o_gets_x(self):
        quiz = make_ox_quiz("O")
        result = check_answer(quiz, "X")
        assert result.is_correct is False

    def test_wrong_x_gets_o(self):
        quiz = make_ox_quiz("X")
        result = check_answer(quiz, "O")
        assert result.is_correct is False

    def test_normalize_맞다(self):
        """'맞다' → O로 정규화"""
        quiz = make_ox_quiz("O")
        result = check_answer(quiz, "맞다")
        assert result.is_correct is True

    def test_normalize_틀리다(self):
        """'틀리다' → X로 정규화"""
        quiz = make_ox_quiz("X")
        result = check_answer(quiz, "틀리다")
        assert result.is_correct is True

    def test_normalize_true(self):
        quiz = make_ox_quiz("O")
        result = check_answer(quiz, "TRUE")
        assert result.is_correct is True

    def test_normalize_false(self):
        quiz = make_ox_quiz("X")
        result = check_answer(quiz, "FALSE")
        assert result.is_correct is True

    def test_empty_answer(self):
        quiz = make_ox_quiz("O")
        result = check_answer(quiz, "")
        assert result.is_correct is False


# ── EvalResult 속성 ──────────────────────────────────────────
class TestEvalResult:
    def test_has_quiz(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert result.quiz is quiz

    def test_is_correct_type_bool(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert isinstance(result.is_correct, bool)

    def test_feedback_property(self):
        quiz = make_blank_quiz("응집력")
        result = check_answer(quiz, "응집력")
        assert isinstance(result.feedback, str)
        assert len(result.feedback) > 0
