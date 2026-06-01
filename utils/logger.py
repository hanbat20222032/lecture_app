"""
utils/logger.py
앱 전역 로거 — 콘솔 + 로테이팅 파일 핸들러
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from utils.config import LOG_FILE, LOG_LEVEL, LOG_MAX_BYTES, LOG_BACKUP_COUNT

_FMT = "%(asctime)s  %(levelname)-8s  %(name)-25s  %(message)s"
_DATE_FMT = "%Y-%m-%d %H:%M:%S"
_initialized = False


def _setup_root_logger() -> None:
    """루트 로거를 최초 1회 초기화한다."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter(_FMT, datefmt=_DATE_FMT)

    # ── 콘솔 핸들러 ──
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    stream_handler.setLevel(logging.DEBUG)
    root.addHandler(stream_handler)

    # ── 파일 핸들러 (로테이팅) ──
    try:
        LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(LOG_FILE),
            maxBytes=LOG_MAX_BYTES,
            backupCount=LOG_BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        root.addHandler(file_handler)
    except OSError as exc:
        root.warning("로그 파일 핸들러 초기화 실패: %s", exc)

    root.info(
        "로거 초기화 완료  |  레벨=%s  |  파일=%s",
        LOG_LEVEL,
        LOG_FILE,
    )


def get_logger(name: str) -> logging.Logger:
    """
    모듈별 로거를 반환한다.

    사용법:
        from utils.logger import get_logger
        logger = get_logger(__name__)
        logger.info("메시지")
    """
    _setup_root_logger()
    return logging.getLogger(name)


# 앱 전체에서 공유하는 최상위 로거
app_logger = get_logger("lecture_app")
