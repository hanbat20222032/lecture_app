"""
analysis/gap_detector.py
누락 개념 탐지 — 소스 키워드 중 대상 텍스트에 없는 개념을 중요도 순으로 반환
"""
from __future__ import annotations
from dataclasses import dataclass
from analysis.coverage_calc import CoverageReport
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GapItem:
    """누락 개념 단건."""
    word:          str
    tfidf_score:   float
    textrank_score: float
    importance:    float     # combined score
    category:      str       # "missing" | "partial"


@dataclass
class GapReport:
    """누락 개념 전체 보고서."""
    items:           list[GapItem]   # 중요도 내림차순
    missing_count:   int
    partial_count:   int
    gap_rate:        float           # 누락률 (0~1)

    @property
    def top_missing(self) -> list[str]:
        return [g.word for g in self.items if g.category == "missing"]

    @property
    def top_partial(self) -> list[str]:
        return [g.word for g in self.items if g.category == "partial"]

    def to_json_list(self) -> list[str]:
        """DB 저장용 누락 단어 목록."""
        return [g.word for g in self.items if g.category == "missing"]


def detect_gaps(
    coverage:        CoverageReport,
    keyword_scores:  dict[str, float],   # {word: combined_score}
) -> GapReport:
    """
    커버리지 보고서와 키워드 점수를 결합해 누락 개념을 탐지한다.

    Args:
        coverage:       calc_coverage() 결과
        keyword_scores: {word: importance} — concept_extractor 결합 점수
    """
    items: list[GapItem] = []

    for word in coverage.missing:
        score = keyword_scores.get(word, 0.0)
        items.append(GapItem(
            word=word, tfidf_score=score,
            textrank_score=0.0, importance=score, category="missing",
        ))

    for word in coverage.partial:
        score = keyword_scores.get(word, 0.0) * 0.5
        items.append(GapItem(
            word=word, tfidf_score=score,
            textrank_score=0.0, importance=score, category="partial",
        ))

    items.sort(key=lambda x: x.importance, reverse=True)
    total = coverage.total_keywords or 1
    gap_rate = (coverage.missing_count + coverage.partial_count * 0.5) / total

    report = GapReport(
        items         = items,
        missing_count = coverage.missing_count,
        partial_count = coverage.partial_count,
        gap_rate      = round(gap_rate, 4),
    )
    logger.info(
        "갭 탐지: 누락=%d  부분=%d  갭율=%.1f%%",
        report.missing_count, report.partial_count, gap_rate * 100,
    )
    return report
