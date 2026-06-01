"""
core/pipeline.py
분석 파이프라인 — QThread 기반 비동기 처리
PDF 파싱 → 텍스트 전처리 → 역색인 구축 → DB 저장
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.pdf_parser   import PDFParser, ParsedDocument
from core.text_processor import TextProcessor, ProcessedText
from core.inverted_index import build_and_save
from database import db_manager as db
from database.models import Document, SourceType, Language
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 파이프라인 결과 데이터
# ──────────────────────────────────────────────

@dataclass
class PipelineResult:
    """파이프라인 실행 결과."""
    doc_id:        int
    doc_title:     str
    char_count:    int
    token_count:   int
    sentence_count: int
    word_positions: dict[str, list[int]]   # 역색인용
    language:      str
    chapters:      list                    # ParsedDocument.chapters 또는 빈 리스트
    processed:     ProcessedText
    parsed_doc:    Optional[ParsedDocument] = None   # PDF인 경우


# ──────────────────────────────────────────────
# 분석 워커 스레드
# ──────────────────────────────────────────────

class AnalysisWorker(QThread):
    """
    백그라운드에서 분석 파이프라인을 실행한다.

    시그널:
        progress(int)         진행률 0~100
        status(str)           현재 단계 메시지
        finished(PipelineResult)  완료 시 결과
        error(str)            오류 메시지
    """

    progress = pyqtSignal(int)
    status   = pyqtSignal(str)
    finished = pyqtSignal(object)   # PipelineResult
    error    = pyqtSignal(str)

    def __init__(
        self,
        subject_id:  int,
        source_type: SourceType,
        parent=None,
        # PDF 모드
        file_path:   Optional[str] = None,
        # 텍스트 모드
        text_content: Optional[str] = None,
        text_label:   Optional[str] = None,
        language:     str = "ko",
    ):
        super().__init__(parent)
        self.subject_id   = subject_id
        self.source_type  = source_type
        self.file_path    = file_path
        self.text_content = text_content
        self.text_label   = text_label or "직접 입력"
        self.language     = language

    def run(self):
        try:
            if self.source_type == SourceType.PDF:
                self._run_pdf()
            else:
                self._run_text()
        except Exception as exc:
            logger.exception("파이프라인 오류")
            self.error.emit(str(exc))

    # ── PDF 파이프라인 ──────────────────────
    def _run_pdf(self):
        path = Path(self.file_path)

        # 1. PDF 파싱
        self.status.emit(f"PDF 파싱 중: {path.name}")
        parser = PDFParser(
            path,
            progress_cb=lambda p: self.progress.emit(int(p * 0.4)),
        )
        parsed: ParsedDocument = parser.parse()

        # 2. 언어 감지
        processor = TextProcessor()
        detected  = processor.detect_language(parsed.full_text[:2000])
        lang      = self.language if self.language != "ko" else detected

        # 3. 텍스트 전처리
        self.status.emit("텍스트 전처리 중…")
        self.progress.emit(45)
        processed = processor.process(parsed.full_text, lang)

        # 4. DB 문서 저장
        self.status.emit("DB에 저장 중…")
        self.progress.emit(60)
        doc_lang = Language.EN if lang == "en" else Language.KO
        doc = db.create_document(Document(
            subject_id  = self.subject_id,
            title       = parsed.title or path.stem,
            source_type = SourceType.PDF,
            language    = doc_lang,
            file_path   = str(path),
            content     = parsed.full_text,
            page_count  = parsed.page_count,
        ))

        # 5. 역색인 구축 + DB 저장
        self.status.emit("역색인 구축 중…")
        self.progress.emit(75)
        word_positions = build_and_save(processed.tokens, doc.id, doc.title)

        self.progress.emit(100)
        self.status.emit("완료")

        result = PipelineResult(
            doc_id         = doc.id,
            doc_title      = doc.title,
            char_count     = len(parsed.full_text),
            token_count    = processed.token_count,
            sentence_count = processed.sentence_count,
            word_positions = word_positions,
            language       = lang,
            chapters       = parsed.chapters,
            processed      = processed,
            parsed_doc     = parsed,
        )
        logger.info(
            "PDF 파이프라인 완료: doc_id=%d  %d자  토큰 %d개",
            doc.id, result.char_count, result.token_count,
        )
        self.finished.emit(result)

    # ── 텍스트 파이프라인 ───────────────────
    def _run_text(self):
        content = self.text_content or ""

        # 1. 언어 감지
        processor = TextProcessor()
        detected  = processor.detect_language(content[:2000])
        lang      = self.language if self.language != "ko" else detected

        # 2. 전처리
        self.status.emit("텍스트 전처리 중…")
        self.progress.emit(30)
        processed = processor.process(content, lang)

        # 3. DB 저장
        self.status.emit("DB에 저장 중…")
        self.progress.emit(55)
        source = (
            SourceType.TXT
            if (self.text_label or "").endswith(".txt")
            else SourceType.TEXT
        )
        doc_lang = Language.EN if lang == "en" else Language.KO
        doc = db.create_document(Document(
            subject_id  = self.subject_id,
            title       = self.text_label,
            source_type = source,
            language    = doc_lang,
            content     = content,
        ))

        # 4. 역색인
        self.status.emit("역색인 구축 중…")
        self.progress.emit(75)
        word_positions = build_and_save(processed.tokens, doc.id, doc.title)

        self.progress.emit(100)
        self.status.emit("완료")

        result = PipelineResult(
            doc_id         = doc.id,
            doc_title      = doc.title,
            char_count     = len(content),
            token_count    = processed.token_count,
            sentence_count = processed.sentence_count,
            word_positions = word_positions,
            language       = lang,
            chapters       = [],
            processed      = processed,
        )
        logger.info(
            "텍스트 파이프라인 완료: doc_id=%d  %d자  토큰 %d개",
            doc.id, result.char_count, result.token_count,
        )
        self.finished.emit(result)
