"""
database/models.py
SQLite 테이블 구조를 Python dataclass로 정의
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


# ──────────────────────────────────────────────
# 열거형
# ──────────────────────────────────────────────

class SourceType(str, Enum):
    """문서 소스 유형."""
    PDF  = "pdf"
    TXT  = "txt"
    TEXT = "text"   # 직접 입력


class QuizType(str, Enum):
    """퀴즈 유형."""
    BLANK = "blank"   # 빈칸 채우기
    OX    = "ox"      # OX 퀴즈


class Language(str, Enum):
    """지원 언어."""
    KO = "ko"   # 한국어
    EN = "en"   # 영어


# ──────────────────────────────────────────────
# 테이블 모델
# ──────────────────────────────────────────────

@dataclass
class Subject:
    """
    subjects 테이블
    과목/강의 단위. 여러 문서와 퀴즈 세션을 포함한다.
    """
    name:        str
    description: str                  = ""
    id:          Optional[int]        = None
    created_at:  Optional[datetime]   = None
    updated_at:  Optional[datetime]   = None

    def __post_init__(self):
        if not self.name.strip():
            raise ValueError("과목 이름은 비워둘 수 없습니다.")


@dataclass
class Document:
    """
    documents 테이블
    업로드된 PDF / TXT / 직접 입력 자료.
    """
    subject_id:  int
    title:       str
    source_type: SourceType
    language:    Language             = Language.KO
    file_path:   Optional[str]        = None    # PDF·TXT 파일 경로
    content:     Optional[str]        = None    # 추출/입력된 텍스트
    page_count:  Optional[int]        = None    # PDF 페이지 수
    char_count:  int                  = 0       # 텍스트 글자 수
    id:          Optional[int]        = None
    created_at:  Optional[datetime]   = None

    def __post_init__(self):
        if isinstance(self.source_type, str):
            self.source_type = SourceType(self.source_type)
        if isinstance(self.language, str):
            self.language = Language(self.language)


@dataclass
class Keyword:
    """
    keywords 테이블
    문서에서 추출된 핵심 키워드.
    """
    document_id:      int
    word:             str
    tfidf_score:      float             = 0.0
    textrank_score:   float             = 0.0
    frequency:        int               = 1
    is_user_added:    bool              = False   # 사용자가 수동 추가한 키워드
    is_user_removed:  bool              = False   # 사용자가 제거한 키워드
    id:               Optional[int]    = None
    created_at:       Optional[datetime] = None

    @property
    def combined_score(self) -> float:
        """TF-IDF + TextRank 결합 점수 (0.6 : 0.4 가중 평균)."""
        return self.tfidf_score * 0.6 + self.textrank_score * 0.4


@dataclass
class Quiz:
    """
    quizzes 테이블
    자동 생성된 퀴즈 문제.
    """
    document_id:  int
    quiz_type:    QuizType
    question:     str               # 빈칸 문제 or OX 문장
    answer:       str               # 정답 (빈칸: 단어, OX: "O" / "X")
    context:      str       = ""    # 문제 출처 문장
    keyword:      str       = ""    # 관련 키워드
    id:           Optional[int]     = None
    created_at:   Optional[datetime] = None

    def __post_init__(self):
        if isinstance(self.quiz_type, str):
            self.quiz_type = QuizType(self.quiz_type)


@dataclass
class QuizSession:
    """
    quiz_sessions 테이블
    퀴즈 풀이 1회 세션.
    """
    document_id:      int
    total_questions:  int               = 0
    correct_count:    int               = 0
    score:            float             = 0.0     # 0~100
    completed:        bool              = False
    id:               Optional[int]     = None
    started_at:       Optional[datetime] = None
    completed_at:     Optional[datetime] = None

    @property
    def wrong_count(self) -> int:
        return self.total_questions - self.correct_count

    @property
    def pass_status(self) -> str:
        from utils.config import SCORE_PASS_THRESHOLD
        return "통과" if self.score >= SCORE_PASS_THRESHOLD else "미통과"


@dataclass
class QuizResult:
    """
    quiz_results 테이블
    세션 내 개별 문제 답변 기록.
    """
    session_id:   int
    quiz_id:      int
    user_answer:  str
    is_correct:   bool
    id:           Optional[int]     = None
    answered_at:  Optional[datetime] = None


@dataclass
class ComprehensionScore:
    """
    comprehension_scores 테이블
    챕터/문서별 이해도 점수 측정 결과.
    """
    document_id:       int
    chapter:           str       = "전체"
    quiz_score:        float     = 0.0    # 퀴즈 정답률 (0~100)
    coverage_score:    float     = 0.0    # 키워드 커버리지 (0~100)
    keyword_density:   float     = 0.0    # 키워드 밀도 (0~100)
    total_score:       float     = 0.0    # 가중 합산 점수
    missing_concepts:  str       = ""     # JSON 직렬화된 누락 개념 목록
    id:                Optional[int]     = None
    measured_at:       Optional[datetime] = None
