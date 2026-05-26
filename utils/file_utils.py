"""
utils/file_utils.py
파일 및 경로 관련 헬퍼 함수 모음
"""

from __future__ import annotations

import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.config import UPLOAD_DIR, MAX_FILE_SIZE_MB, SUPPORTED_EXTENSIONS
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 파일 검증
# ──────────────────────────────────────────────

def validate_file(path: str | Path) -> tuple[bool, str]:
    """
    파일 유효성을 검사한다.

    Returns:
        (ok: bool, message: str)
    """
    p = Path(path)

    if not p.exists():
        return False, f"파일을 찾을 수 없습니다: {p.name}"

    if not p.is_file():
        return False, f"파일이 아닙니다: {p.name}"

    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        supported = ", ".join(SUPPORTED_EXTENSIONS)
        return False, f"지원하지 않는 형식: {ext}  (지원: {supported})"

    size_mb = p.stat().st_size / 1024 / 1024
    if size_mb > MAX_FILE_SIZE_MB:
        return False, f"파일 크기 초과: {size_mb:.1f}MB (최대 {MAX_FILE_SIZE_MB}MB)"

    # PDF 시그니처 확인
    if ext == ".pdf":
        try:
            with open(p, "rb") as f:
                header = f.read(5)
            if header != b"%PDF-":
                return False, "손상된 PDF 파일입니다."
        except OSError as e:
            return False, f"파일 읽기 오류: {e}"

    return True, "OK"


def get_file_size_str(path: str | Path) -> str:
    """파일 크기를 사람이 읽기 쉬운 문자열로 반환."""
    size = Path(path).stat().st_size
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_file_hash(path: str | Path, algorithm: str = "sha256") -> str:
    """파일의 해시값을 반환한다. 중복 업로드 감지에 사용."""
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


# ──────────────────────────────────────────────
# 파일 복사 / 이동
# ──────────────────────────────────────────────

def copy_to_upload_dir(src: str | Path, subject_id: int) -> Path:
    """
    파일을 업로드 디렉터리의 과목 폴더로 복사한다.

    Returns:
        복사된 파일의 절대 경로
    """
    src = Path(src)
    dest_dir = UPLOAD_DIR / str(subject_id)
    dest_dir.mkdir(parents=True, exist_ok=True)

    # 타임스탬프로 이름 충돌 방지
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = dest_dir / f"{ts}_{src.name}"

    shutil.copy2(src, dest)
    logger.info("파일 복사: %s → %s", src, dest)
    return dest


def safe_delete(path: str | Path) -> bool:
    """파일/디렉터리를 안전하게 삭제한다."""
    p = Path(path)
    try:
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)
        logger.info("삭제 완료: %s", p)
        return True
    except OSError as e:
        logger.warning("삭제 실패: %s  |  %s", p, e)
        return False


# ──────────────────────────────────────────────
# 경로 유틸
# ──────────────────────────────────────────────

def sanitize_filename(name: str) -> str:
    """파일명에서 OS 금지 문자를 제거한다."""
    forbidden = r'\/:*?"<>|'
    for ch in forbidden:
        name = name.replace(ch, "_")
    return name.strip()


def ensure_dir(path: str | Path) -> Path:
    """디렉터리가 없으면 생성하고 Path를 반환한다."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def list_uploaded_files(subject_id: Optional[int] = None) -> list[Path]:
    """
    업로드된 파일 목록을 반환한다.

    Args:
        subject_id: None이면 전체 파일, 정수면 해당 과목 파일만
    """
    base = UPLOAD_DIR / str(subject_id) if subject_id is not None else UPLOAD_DIR
    if not base.exists():
        return []
    return sorted(
        [p for p in base.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )


def get_relative_path(path: str | Path, base: Optional[str | Path] = None) -> str:
    """절대 경로를 프로젝트 루트 기준 상대 경로 문자열로 변환한다."""
    from utils.config import ROOT_DIR
    base = Path(base) if base else ROOT_DIR
    try:
        return str(Path(path).relative_to(base))
    except ValueError:
        return str(path)
