"""
utils/config.py
앱 전역 설정 및 상수 정의
"""

from __future__ import annotations

import os
from pathlib import Path

# ──────────────────────────────────────────────
# 경로 설정
# ──────────────────────────────────────────────

# 프로젝트 루트 (config.py 위치 기준 상위 디렉터리)
ROOT_DIR: Path = Path(__file__).resolve().parent.parent

# 사용자 데이터 저장 경로
DATA_DIR: Path = ROOT_DIR / "data"
UPLOAD_DIR: Path = DATA_DIR / "uploads"
EXPORT_DIR: Path = DATA_DIR / "exports"
LOG_DIR: Path = ROOT_DIR / "logs"

# DB 파일 경로
DB_PATH: Path = ROOT_DIR / "lecture_app.db"

# 경로 자동 생성 (앱 최초 실행 시)
for _dir in (DATA_DIR, UPLOAD_DIR, EXPORT_DIR, LOG_DIR):
    _dir.mkdir(parents=True, exist_ok=True)


# ──────────────────────────────────────────────
# 앱 메타 정보
# ──────────────────────────────────────────────

APP_NAME        = "강의 이해도 측정기"
APP_VERSION     = "1.0.0"
APP_AUTHOR      = "20222032 오은석"
APP_DESCRIPTION = "PDF·TXT 기반 핵심 개념 추출 및 이해도 측정 데스크탑 앱"


# ──────────────────────────────────────────────
# 지원 파일 형식
# ──────────────────────────────────────────────

SUPPORTED_EXTENSIONS: tuple[str, ...] = (".pdf", ".txt")
MAX_FILE_SIZE_MB: int = 100           # 최대 업로드 파일 크기 (MB)
MAX_TEXT_CHARS:   int = 500_000       # 직접 입력 최대 글자 수


# ──────────────────────────────────────────────
# 텍스트 처리 설정
# ──────────────────────────────────────────────

SUPPORTED_LANGUAGES: tuple[str, ...] = ("ko", "en")   # 한국어, 영어

# TF-IDF
TFIDF_MAX_FEATURES:  int   = 500     # 추출할 최대 키워드 수
TFIDF_MIN_DF:        int   = 1       # 최소 문서 빈도
TFIDF_NGRAM_RANGE:   tuple = (1, 2)  # 유니그램 + 바이그램

# TextRank
TEXTRANK_TOP_N:       int   = 20     # 상위 문장 수
TEXTRANK_DAMPING:     float = 0.85   # PageRank 감쇠 계수
TEXTRANK_MAX_ITER:    int   = 100    # 최대 반복 횟수
TEXTRANK_CONVERGENCE: float = 1e-4   # 수렴 임계값

# 코사인 유사도
COSINE_SIM_THRESHOLD: float = 0.3   # 유사 문서 판단 기준


# ──────────────────────────────────────────────
# 퀴즈 설정
# ──────────────────────────────────────────────

QUIZ_BLANK_COUNT: int = 10           # 기본 빈칸 문제 수
QUIZ_OX_COUNT:    int = 10           # 기본 OX 문제 수
QUIZ_MIN_SENT_LEN: int = 15          # 문제 생성 최소 문장 길이 (글자)


# ──────────────────────────────────────────────
# 이해도 점수화
# ──────────────────────────────────────────────

SCORE_PASS_THRESHOLD: float = 60.0   # 통과 기준 점수 (%)
SCORE_WEIGHTS: dict = {
    "quiz_correct":    0.60,          # 퀴즈 정답률 가중치
    "coverage":        0.30,          # 키워드 커버리지 가중치
    "keyword_density": 0.10,          # 키워드 밀도 가중치
}


# ──────────────────────────────────────────────
# UI 설정
# ──────────────────────────────────────────────

WINDOW_MIN_WIDTH:  int = 1024
WINDOW_MIN_HEIGHT: int = 700
WINDOW_TITLE: str = f"{APP_NAME}  v{APP_VERSION}"

# matplotlib 차트 DPI
CHART_DPI: int = 100

# 색상 팔레트 (QSS에서도 동일하게 사용)
COLOR = {
    "primary":    "#5B5FD9",
    "primary_h":  "#4347B5",
    "success":    "#22C55E",
    "warning":    "#F59E0B",
    "danger":     "#EF4444",
    "bg_dark":    "#0F0F1A",
    "bg_card":    "#1E1E2E",
    "bg_input":   "#13131F",
    "text_pri":   "#E2E2F0",
    "text_sec":   "#9494B8",
    "border":     "#2E2E4A",
}


# ──────────────────────────────────────────────
# 로깅 설정
# ──────────────────────────────────────────────

LOG_LEVEL:        str = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE:         Path = LOG_DIR / "app.log"
LOG_MAX_BYTES:    int = 5 * 1024 * 1024   # 5 MB
LOG_BACKUP_COUNT: int = 3


# ──────────────────────────────────────────────
# DB 설정
# ──────────────────────────────────────────────

DB_TIMEOUT: int = 30                 # SQLite 연결 타임아웃 (초)
DB_CACHE_SIZE: int = -32000          # SQLite 캐시 크기 (32MB, 음수 = KB 단위)


def get_version() -> str:
    return APP_VERSION


def is_supported_file(path: str | Path) -> bool:
    """파일 확장자가 지원 형식인지 확인."""
    return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS


def is_file_size_ok(path: str | Path) -> bool:
    """파일 크기가 제한 이내인지 확인."""
    size_mb = Path(path).stat().st_size / 1024 / 1024
    return size_mb <= MAX_FILE_SIZE_MB
