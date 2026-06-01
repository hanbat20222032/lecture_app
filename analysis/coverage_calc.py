"""
analysis/coverage_calc.py
소스(PDF) 키워드와 대상(필기·입력) 텍스트 간 커버리지 계산
"""
from __future__ import annotations
from dataclasses import dataclass, field
from core.cosine_sim import compute_coverage, compute_keyword_density, compare_documents
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CoverageReport:
    """커버리지 분석 결과."""
    coverage_rate:   float          # 0.0 ~ 1.0
    covered:         list[str]
    partial:         list[str]
    missing:         list[str]
    keyword_density: float
    similarity:      float          # 문서 간 코사인 유사도
    covered_count:   int
    partial_count:   int
    missing_count:   int

    @property
    def coverage_pct(self) -> float:
        return round(self.coverage_rate * 100, 1)

    @property
    def total_keywords(self) -> int:
        return self.covered_count + self.partial_count + self.missing_count


def calc_coverage(
    source_keywords: list[str],
    source_tokens:   list[str],
    target_tokens:   list[str],
) -> CoverageReport:
    """
    소스 키워드가 대상 텍스트에 얼마나 등장하는지 계산한다.

    Args:
        source_keywords: PDF 추출 키워드
        source_tokens:   PDF 전체 토큰
        target_tokens:   필기·직접 입력 토큰
    """
    if not source_keywords or not target_tokens:
        return CoverageReport(
            coverage_rate=0.0, covered=[], partial=[],
            missing=source_keywords, keyword_density=0.0,
            similarity=0.0, covered_count=0,
            partial_count=0, missing_count=len(source_keywords),
        )

    cov     = compute_coverage(source_keywords, target_tokens)
    density = compute_keyword_density(source_keywords, target_tokens)
    comp    = compare_documents(source_tokens, target_tokens, "PDF", "필기")

    report = CoverageReport(
        coverage_rate  = cov["coverage_rate"],
        covered        = cov["covered"],
        partial        = cov.get("partial", []),
        missing        = cov["missing"],
        keyword_density= round(density, 4),
        similarity     = comp["similarity"],
        covered_count  = cov["covered_count"],
        partial_count  = cov.get("partial_count", 0),
        missing_count  = cov["missing_count"],
    )
    logger.info(
        "커버리지: %.1f%%  유사도=%.3f  누락=%d개",
        report.coverage_pct, report.similarity, report.missing_count,
    )
    return report
