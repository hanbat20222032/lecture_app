"""
reports/report_gen.py
리포트 데이터 수집 — DB에서 이해도 점수·세션·키워드를 집계하여
chart_builder에 전달할 데이터 딕셔너리를 반환한다.
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field
from database import db_manager as db
from database.models import ComprehensionScore
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ReportData:
    """리포트 전체 데이터."""
    doc_id:          int
    doc_title:       str
    # 점수 추이
    dates:           list[str]     = field(default_factory=list)
    history_scores:  list[float]   = field(default_factory=list)
    # 최신 점수 세부
    quiz_score:      float         = 0.0
    coverage_score:  float         = 0.0
    keyword_density: float         = 0.0
    total_score:     float         = 0.0
    grade:           str           = "F"
    passed:          bool          = False
    # 키워드 커버리지
    covered_count:   int           = 0
    partial_count:   int           = 0
    missing_count:   int           = 0
    missing_words:   list[str]     = field(default_factory=list)
    # 챕터
    chapters:        list[str]     = field(default_factory=list)
    chapter_scores:  list[float]   = field(default_factory=list)
    # 세션
    session_count:   int           = 0
    best_score:      float         = 0.0
    avg_score:       float         = 0.0

    @property
    def has_data(self) -> bool:
        return len(self.history_scores) > 0


def collect_report(doc_id: int) -> ReportData:
    """
    문서 ID를 받아 리포트 데이터를 DB에서 수집한다.

    Args:
        doc_id: 문서 ID

    Returns:
        ReportData 인스턴스
    """
    doc = db.get_document(doc_id)
    if not doc:
        logger.warning("문서 없음: doc_id=%d", doc_id)
        return ReportData(doc_id=doc_id, doc_title="알 수 없음")

    data = ReportData(doc_id=doc_id, doc_title=doc.title)

    # ── 이해도 점수 이력 ──
    scores: list[ComprehensionScore] = db.get_scores(doc_id)
    if scores:
        # 시간 오름차순
        scores_asc = sorted(scores, key=lambda s: s.measured_at or "")
        data.dates          = [
            s.measured_at.strftime("%m/%d %H:%M") if s.measured_at else "-"
            for s in scores_asc
        ]
        data.history_scores = [s.total_score for s in scores_asc]
        data.session_count  = len(scores)
        data.best_score     = max(s.total_score for s in scores)
        data.avg_score      = round(
            sum(s.total_score for s in scores) / len(scores), 1
        )

        # 최신 점수 세부 내역
        latest = scores[0]   # get_scores → DESC 정렬
        data.quiz_score      = latest.quiz_score
        data.coverage_score  = latest.coverage_score
        data.keyword_density = latest.keyword_density
        data.total_score     = latest.total_score
        data.passed          = latest.total_score >= 60.0
        data.grade           = _to_grade(latest.total_score)

        # 누락 개념
        try:
            missing = json.loads(latest.missing_concepts)
            data.missing_words = missing
            data.missing_count = len(missing)
        except Exception:
            data.missing_words = []

    # ── 키워드 커버리지 (퀴즈 세션이 있을 때만 재계산) ──
    keywords = db.get_keywords(doc_id, exclude_removed=True)
    if keywords:
        total_kw    = len(keywords)
        missing_set = set(data.missing_words)
        covered     = sum(1 for k in keywords if k.word not in missing_set)
        partial     = max(0, total_kw - covered - len(missing_set))

        data.covered_count = covered
        data.missing_count = len(missing_set)
        data.partial_count = partial

        # 퀴즈를 한 번이라도 풀었을 때만 재계산
        if data.has_data:
            if data.coverage_score == 0.0 and total_kw > 0:
                data.coverage_score = round(covered / total_kw * 100, 2)
            if data.keyword_density == 0.0 and total_kw > 0:
                density = (covered + partial * 0.5) / total_kw
                data.keyword_density = round(min(density * 100, 100.0), 2)

        # ※ 최종 점수는 퀴즈 점수만 반영 (커버리지·밀도는 참고용 표시)

    # ── 챕터별 점수 ──
    chapter_map: dict[str, list[float]] = {}
    for sc in scores:
        ch = sc.chapter or "전체"
        chapter_map.setdefault(ch, []).append(sc.total_score)

    if len(chapter_map) > 1:   # 챕터가 2개 이상일 때만 표시
        data.chapters       = list(chapter_map.keys())
        data.chapter_scores = [
            round(sum(v) / len(v), 1) for v in chapter_map.values()
        ]
    elif chapter_map:
        # 챕터 1개는 세션별로 시각화 (추이와 동일하므로 비워둠)
        data.chapters       = []
        data.chapter_scores = []

    logger.info(
        "리포트 데이터 수집: doc_id=%d  점수이력=%d개  최신=%.1f점",
        doc_id, len(data.history_scores), data.total_score,
    )
    return data


def collect_subject_report(subject_id: int) -> list[ReportData]:
    """과목의 모든 문서에 대한 리포트 데이터를 수집한다."""
    docs = db.get_documents_by_subject(subject_id)
    results = []
    for doc in docs:
        rd = collect_report(doc.id)
        if rd.has_data:
            results.append(rd)
    return results


def _to_grade(score: float) -> str:
    if score >= 90: return "A"
    if score >= 80: return "B"
    if score >= 70: return "C"
    if score >= 60: return "D"
    return "F"
