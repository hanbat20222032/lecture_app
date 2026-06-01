"""
quiz/evaluator.py
퀴즈 채점 — 답변 평가, 세션 점수 계산, 이해도 DB 저장
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from database import db_manager as db
from database.models import Quiz, QuizResult, QuizType
from analysis.scorer import calculate_score, save_score, ScoreBreakdown
from analysis.gap_detector import GapReport, GapItem
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class EvalResult:
    """단일 문제 채점 결과."""
    quiz:        Quiz
    user_answer: str
    is_correct:  bool
    correct_ans: str

    @property
    def feedback(self) -> str:
        if self.is_correct:
            return f"✓ 정답: {self.correct_ans}"
        return f"✗ 오답 — 정답: {self.correct_ans}"


@dataclass
class SessionReport:
    """세션 전체 채점 보고서."""
    session_id:    int
    doc_id:        int
    total:         int
    correct:       int
    results:       list[EvalResult]
    breakdown:     ScoreBreakdown
    wrong_keywords: list[str] = field(default_factory=list)

    @property
    def wrong_count(self) -> int:
        return self.total - self.correct

    @property
    def accuracy(self) -> float:
        return self.correct / max(self.total, 1)


def check_answer(quiz: Quiz, user_answer: str) -> EvalResult:
    """
    단일 문제의 정오를 판정한다.

    빈칸형: 대소문자·공백 무시 후 비교
    OX형:   'O' / 'X' 또는 '맞다' / '틀리다' 허용
    """
    ua  = user_answer.strip()
    ans = quiz.answer.strip()

    if quiz.quiz_type == QuizType.BLANK:
        correct = ua.lower().replace(" ", "") == ans.lower().replace(" ", "")
    else:
        # OX 정규화
        ua_norm  = _normalize_ox(ua)
        ans_norm = _normalize_ox(ans)
        correct  = ua_norm == ans_norm

    return EvalResult(
        quiz        = quiz,
        user_answer = ua,
        is_correct  = correct,
        correct_ans = ans,
    )


def _normalize_ox(text: str) -> str:
    t = text.strip().upper()
    if t in ("O", "O", "맞다", "맞음", "TRUE", "참", "정"):  return "O"
    if t in ("X", "X", "틀리다", "틀림", "FALSE", "거짓", "오"): return "X"
    return t


def evaluate_session(
    session_id:      int,
    doc_id:          int,
    answers:         list[tuple[Quiz, str]],   # [(quiz, user_answer), ...]
    coverage_rate:   float = 0.0,
    keyword_density: float = 0.0,
    missing_words:   list[str] | None = None,
) -> SessionReport:
    """
    세션 전체를 채점하고 DB에 결과를 저장한다.

    Args:
        session_id:      QuizSession ID
        doc_id:          문서 ID
        answers:         [(Quiz, 사용자 답변), ...] 목록
        coverage_rate:   커버리지 (0~1)
        keyword_density: 키워드 밀도 (0~1)
        missing_words:   누락 개념 목록
    """
    eval_results: list[EvalResult] = []
    correct = 0

    for quiz, ua in answers:
        er = check_answer(quiz, ua)
        eval_results.append(er)
        if er.is_correct:
            correct += 1
        # DB에 개별 결과 저장
        db.save_result(QuizResult(
            session_id  = session_id,
            quiz_id     = quiz.id,
            user_answer = er.user_answer,
            is_correct  = er.is_correct,
        ))

    total = len(answers)

    # 점수 계산
    breakdown = calculate_score(correct, total, coverage_rate, keyword_density)

    # 세션 완료 처리
    db.complete_session(session_id, total, correct, breakdown.total_score)

    # 틀린 문제의 키워드 수집
    wrong_kws = list(set(
        er.quiz.keyword
        for er in eval_results
        if not er.is_correct and er.quiz.keyword
    ))

    # 누락 개념 결정: 외부 전달값 우선, 없으면 틀린 키워드 사용
    effective_missing = missing_words if missing_words else wrong_kws

    # 이해도 점수 DB 저장
    gap = GapReport(
        items         = [GapItem(w, 0, 0, 0, "missing") for w in effective_missing],
        missing_count = len(effective_missing),
        partial_count = 0,
        gap_rate      = 0.0,
    )
    save_score(doc_id, breakdown, gap)

    report = SessionReport(
        session_id     = session_id,
        doc_id         = doc_id,
        total          = total,
        correct        = correct,
        results        = eval_results,
        breakdown      = breakdown,
        wrong_keywords = wrong_kws,
    )
    logger.info(
        "세션 채점 완료: session_id=%d  %d/%d  점수=%.1f(%s)",
        session_id, correct, total,
        breakdown.total_score, breakdown.grade,
    )
    return report
