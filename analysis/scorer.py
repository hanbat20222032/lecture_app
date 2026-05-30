"""
analysis/scorer.py
이해도 점수 산출 — 퀴즈 정답률 + 커버리지 + 키워드 밀도 가중 합산
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from database import db_manager as db
from database.models import ComprehensionScore
from analysis.gap_detector import GapReport
from utils.config import SCORE_WEIGHTS, SCORE_PASS_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ScoreBreakdown:
    """점수 세부 내역."""
    quiz_score:       float   # 0~100 퀴즈 정답률
    coverage_score:   float   # 0~100 키워드 커버리지
    keyword_density:  float   # 0~100 키워드 밀도
    total_score:      float   # 0~100 최종 점수
    passed:           bool
    grade:            str     # A~F

    def summary(self) -> str:
        return (
            f"퀴즈 {self.quiz_score:.1f}점  "
            f"커버리지 {self.coverage_score:.1f}점  "
            f"밀도 {self.keyword_density:.1f}점  "
            f"→ 최종 {self.total_score:.1f}점 ({self.grade})"
        )


def _to_grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"


def calculate_score(
    quiz_correct:    int,
    quiz_total:      int,
    coverage_rate:   float,   # 0~1
    keyword_density: float,   # 0~1
) -> ScoreBreakdown:
    """
    세 지표를 가중 합산하여 이해도 점수를 계산한다.

    가중치 (config.py):
        quiz_correct    60%
        coverage        30%
        keyword_density 10%
    """
    quiz_pct     = (quiz_correct / max(quiz_total, 1)) * 100
    coverage_pct = coverage_rate * 100
    density_pct  = keyword_density * 100

    total = (
        SCORE_WEIGHTS["quiz_correct"]    * quiz_pct    +
        SCORE_WEIGHTS["coverage"]        * coverage_pct +
        SCORE_WEIGHTS["keyword_density"] * density_pct
    )
    total = round(min(max(total, 0.0), 100.0), 2)

    return ScoreBreakdown(
        quiz_score      = round(quiz_pct, 2),
        coverage_score  = round(coverage_pct, 2),
        keyword_density = round(density_pct, 2),
        total_score     = total,
        passed          = total >= SCORE_PASS_THRESHOLD,
        grade           = _to_grade(total),
    )


def save_score(
    doc_id:    int,
    breakdown: ScoreBreakdown,
    gap:       GapReport,
    chapter:   str = "전체",
) -> ComprehensionScore:
    """이해도 점수를 DB에 저장하고 ComprehensionScore를 반환한다."""
    missing_json = json.dumps(gap.to_json_list(), ensure_ascii=False)
    score = db.save_score(ComprehensionScore(
        document_id      = doc_id,
        chapter          = chapter,
        quiz_score       = breakdown.quiz_score,
        coverage_score   = breakdown.coverage_score,
        keyword_density  = breakdown.keyword_density,
        total_score      = breakdown.total_score,
        missing_concepts = missing_json,
    ))
    logger.info(
        "점수 저장: doc_id=%d  total=%.1f  grade=%s",
        doc_id, breakdown.total_score, breakdown.grade,
    )
    return score
