"""
quiz/generator.py
퀴즈 생성 파이프라인 — 빈칸 + OX 통합 생성 및 DB 저장
"""
from __future__ import annotations
from dataclasses import dataclass
from database import db_manager as db
from database.models import Quiz, QuizType, Keyword
from quiz.blank_type import generate_blank_quizzes
from quiz.ox_type    import generate_ox_quizzes
from core.text_processor import split_sentences
from utils.config import QUIZ_BLANK_COUNT, QUIZ_OX_COUNT
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class GenerationResult:
    """퀴즈 생성 결과."""
    blank_quizzes: list[Quiz]
    ox_quizzes:    list[Quiz]
    saved_ids:     list[int]

    @property
    def total_count(self) -> int:
        return len(self.blank_quizzes) + len(self.ox_quizzes)

    @property
    def all_quizzes(self) -> list[Quiz]:
        return self.blank_quizzes + self.ox_quizzes


class QuizGenerator:
    """
    문서 텍스트와 키워드를 받아 퀴즈를 생성하고 DB에 저장한다.

    사용법:
        gen = QuizGenerator()
        result = gen.generate(doc_id=1, content=text, keywords=kw_list)
    """

    def __init__(
        self,
        blank_count: int = QUIZ_BLANK_COUNT,
        ox_count:    int = QUIZ_OX_COUNT,
    ):
        self.blank_count = blank_count
        self.ox_count    = ox_count

    def generate(
        self,
        doc_id:     int,
        content:    str,
        keywords:   list[Keyword],
        save:       bool = True,
        quiz_type:  str  = "all",   # "blank" | "ox" | "all"
    ) -> GenerationResult:
        """
        퀴즈를 생성하고 DB에 저장한다.

        Args:
            doc_id:    문서 ID
            content:   원본 텍스트
            keywords:  Keyword 객체 목록 (combined_score 내림차순)
            save:      True이면 DB에 저장
            quiz_type: "blank" = 빈칸만, "ox" = OX만, "all" = 둘 다
        """
        if not keywords or not content.strip():
            logger.warning("퀴즈 생성 불가: 키워드 또는 텍스트 없음")
            return GenerationResult([], [], [])

        # 기존 퀴즈 삭제 (재생성 시 타입별 삭제)
        if save:
            if quiz_type == "all":
                db.delete_quizzes(doc_id)
            elif quiz_type == "blank":
                _delete_quizzes_by_type(doc_id, "blank")
            elif quiz_type == "ox":
                _delete_quizzes_by_type(doc_id, "ox")

        # 문장 분리
        sentences = split_sentences(content)
        if not sentences:
            sentences = [s.strip() for s in content.split('\n') if s.strip()]

        # 문장이 너무 적으면 DB에서 파일 경로를 찾아 표 문장 직접 추출
        # (이전 코드로 저장된 content에는 표 문장이 없을 수 있음)
        if len(sentences) < 30:
            try:
                doc_row = db.get_document(doc_id)
                if doc_row and doc_row.file_path:
                    from pathlib import Path as _P
                    fpath = _P(doc_row.file_path)
                    if fpath.exists():
                        from core.pdf_parser import PDFParser as _PP
                        _parser = _PP(str(fpath))
                        _parser._doc = __import__('fitz').open(str(fpath))
                        extra = _parser._extract_table_sentences()
                        _parser._doc.close()
                        if extra:
                            sentences.extend(extra)
                            logger.info("표 문장 보충: %d개 추가 (총 %d개)",
                                        len(extra), len(sentences))
            except Exception as _e:
                logger.debug("표 문장 보충 실패: %s", _e)

        # 키워드 단어 목록 (중요도 순)
        kw_words = [k.word for k in sorted(
            keywords, key=lambda k: k.combined_score, reverse=True
        )]

        # 빈칸 문제 생성
        blank = generate_blank_quizzes(
            sentences, kw_words, doc_id, self.blank_count
        ) if quiz_type in ("blank", "all") else []

        # OX 문제 생성
        ox = generate_ox_quizzes(
            sentences, kw_words, doc_id, self.ox_count
        ) if quiz_type in ("ox", "all") else []

        # DB 저장
        saved_ids: list[int] = []
        if save:
            all_q = blank + ox
            db.save_quizzes(all_q)
            # 저장된 ID 조회
            saved = db.get_quizzes(doc_id)
            saved_ids = [q.id for q in saved if q.id]

        result = GenerationResult(
            blank_quizzes = blank,
            ox_quizzes    = ox,
            saved_ids     = saved_ids,
        )
        logger.info(
            "퀴즈 생성 완료: doc_id=%d  빈칸=%d  OX=%d",
            doc_id, len(blank), len(ox),
        )
        return result


def _delete_quizzes_by_type(doc_id: int, quiz_type: str) -> None:
    """특정 타입의 퀴즈만 삭제한다."""
    from database.db_manager import get_connection
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM quizzes WHERE document_id=? AND quiz_type=?",
            (doc_id, quiz_type),
        )


def generate_quizzes(
    doc_id:    int,
    content:   str,
    keywords:  list[Keyword],
    quiz_type: str = "all",
) -> GenerationResult:
    """편의 함수 — QuizGenerator를 즉시 실행한다."""
    return QuizGenerator().generate(doc_id, content, keywords, quiz_type=quiz_type)
