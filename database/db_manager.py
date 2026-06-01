"""
database/db_manager.py
SQLite 연결 관리 및 CRUD 레이어
모든 DB 접근은 이 모듈을 통해 이루어진다.
"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional

from utils.config import DB_PATH, DB_TIMEOUT, DB_CACHE_SIZE
from utils.logger import get_logger
from database.models import (
    Subject, Document, Keyword, Quiz, QuizSession,
    QuizResult, ComprehensionScore, SourceType, QuizType, Language,
)

logger = get_logger(__name__)

# 마이그레이션 SQL 경로
_MIGRATION_DIR = Path(__file__).parent / "migrations"


# ──────────────────────────────────────────────
# 연결 관리
# ──────────────────────────────────────────────

def _make_connection() -> sqlite3.Connection:
    """SQLite 연결을 생성하고 최적화 PRAGMA를 적용한다."""
    conn = sqlite3.connect(
        str(DB_PATH),
        timeout=DB_TIMEOUT,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.row_factory = sqlite3.Row
    conn.execute(f"PRAGMA cache_size   = {DB_CACHE_SIZE}")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode  = WAL")
    conn.execute("PRAGMA synchronous   = NORMAL")
    return conn


@contextmanager
def get_connection() -> Generator[sqlite3.Connection, None, None]:
    """
    DB 연결 컨텍스트 매니저.
    with 블록 종료 시 자동 commit / 예외 시 rollback.
    """
    conn = _make_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ──────────────────────────────────────────────
# 초기화
# ──────────────────────────────────────────────

def initialize_db() -> None:
    """
    DB를 초기화한다.
    migrations/ 디렉터리의 SQL 파일을 순서대로 실행한다.
    이미 테이블이 존재하면 CREATE IF NOT EXISTS 로 건너뛴다.
    """
    sql_files = sorted(_MIGRATION_DIR.glob("*.sql"))
    if not sql_files:
        logger.warning("마이그레이션 SQL 파일이 없습니다: %s", _MIGRATION_DIR)
        return

    with get_connection() as conn:
        for sql_file in sql_files:
            logger.info("마이그레이션 실행: %s", sql_file.name)
            sql = sql_file.read_text(encoding="utf-8")
            conn.executescript(sql)

    logger.info("DB 초기화 완료: %s", DB_PATH)


# ──────────────────────────────────────────────
# 내부 헬퍼
# ──────────────────────────────────────────────

def _row_to_subject(row: sqlite3.Row) -> Subject:
    return Subject(
        id=row["id"], name=row["name"], description=row["description"],
        created_at=_parse_dt(row["created_at"]),
        updated_at=_parse_dt(row["updated_at"]),
    )


def _row_to_document(row: sqlite3.Row) -> Document:
    return Document(
        id=row["id"], subject_id=row["subject_id"], title=row["title"],
        source_type=SourceType(row["source_type"]),
        language=Language(row["language"]),
        file_path=row["file_path"], content=row["content"],
        page_count=row["page_count"], char_count=row["char_count"],
        created_at=_parse_dt(row["created_at"]),
    )


def _row_to_keyword(row: sqlite3.Row) -> Keyword:
    return Keyword(
        id=row["id"], document_id=row["document_id"], word=row["word"],
        tfidf_score=row["tfidf_score"], textrank_score=row["textrank_score"],
        frequency=row["frequency"],
        is_user_added=bool(row["is_user_added"]),
        is_user_removed=bool(row["is_user_removed"]),
        created_at=_parse_dt(row["created_at"]),
    )


def _row_to_quiz(row: sqlite3.Row) -> Quiz:
    return Quiz(
        id=row["id"], document_id=row["document_id"],
        quiz_type=QuizType(row["quiz_type"]),
        question=row["question"], answer=row["answer"],
        context=row["context"], keyword=row["keyword"],
        created_at=_parse_dt(row["created_at"]),
    )


def _row_to_session(row: sqlite3.Row) -> QuizSession:
    return QuizSession(
        id=row["id"], document_id=row["document_id"],
        total_questions=row["total_questions"],
        correct_count=row["correct_count"],
        score=row["score"], completed=bool(row["completed"]),
        started_at=_parse_dt(row["started_at"]),
        completed_at=_parse_dt(row["completed_at"]),
    )


def _row_to_score(row: sqlite3.Row) -> ComprehensionScore:
    return ComprehensionScore(
        id=row["id"], document_id=row["document_id"],
        chapter=row["chapter"], quiz_score=row["quiz_score"],
        coverage_score=row["coverage_score"],
        keyword_density=row["keyword_density"],
        total_score=row["total_score"],
        missing_concepts=row["missing_concepts"],
        measured_at=_parse_dt(row["measured_at"]),
    )


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ──────────────────────────────────────────────
# Subject CRUD
# ──────────────────────────────────────────────

def create_subject(name: str, description: str = "") -> Subject:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO subjects (name, description) VALUES (?, ?)",
            (name.strip(), description.strip()),
        )
        row = conn.execute(
            "SELECT * FROM subjects WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
    subject = _row_to_subject(row)
    logger.info("과목 생성: id=%d  name=%s", subject.id, subject.name)
    return subject


def get_subject(subject_id: int) -> Optional[Subject]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM subjects WHERE id = ?", (subject_id,)
        ).fetchone()
    return _row_to_subject(row) if row else None


def get_all_subjects() -> list[Subject]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM subjects ORDER BY created_at DESC"
        ).fetchall()
    return [_row_to_subject(r) for r in rows]


def update_subject(subject_id: int, name: str, description: str = "") -> bool:
    with get_connection() as conn:
        conn.execute(
            "UPDATE subjects SET name=?, description=? WHERE id=?",
            (name.strip(), description.strip(), subject_id),
        )
    logger.info("과목 수정: id=%d", subject_id)
    return True


def delete_subject(subject_id: int) -> bool:
    """과목과 연관 데이터(CASCADE)를 모두 삭제한다."""
    with get_connection() as conn:
        conn.execute("DELETE FROM subjects WHERE id=?", (subject_id,))
    logger.info("과목 삭제: id=%d", subject_id)
    return True


# ──────────────────────────────────────────────
# Document CRUD
# ──────────────────────────────────────────────

def create_document(doc: Document) -> Document:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO documents
               (subject_id, title, source_type, language, file_path,
                content, page_count, char_count)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                doc.subject_id, doc.title,
                doc.source_type.value, doc.language.value,
                doc.file_path, doc.content,
                doc.page_count,
                len(doc.content) if doc.content else 0,
            ),
        )
        row = conn.execute(
            "SELECT * FROM documents WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
    result = _row_to_document(row)
    logger.info("문서 저장: id=%d  title=%s", result.id, result.title)
    return result


def get_document(doc_id: int) -> Optional[Document]:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM documents WHERE id=?", (doc_id,)
        ).fetchone()
    return _row_to_document(row) if row else None


def get_documents_by_subject(subject_id: int) -> list[Document]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE subject_id=? ORDER BY created_at DESC",
            (subject_id,),
        ).fetchall()
    return [_row_to_document(r) for r in rows]


def delete_document(doc_id: int) -> bool:
    with get_connection() as conn:
        conn.execute("DELETE FROM documents WHERE id=?", (doc_id,))
    logger.info("문서 삭제: id=%d", doc_id)
    return True


# ──────────────────────────────────────────────
# Keyword CRUD
# ──────────────────────────────────────────────

def save_keywords(keywords: list[Keyword]) -> int:
    """키워드 목록을 일괄 저장한다. 저장된 행 수를 반환한다."""
    if not keywords:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO keywords
               (document_id, word, tfidf_score, textrank_score,
                frequency, is_user_added)
               VALUES (?,?,?,?,?,?)""",
            [
                (
                    k.document_id, k.word,
                    k.tfidf_score, k.textrank_score,
                    k.frequency, int(k.is_user_added),
                )
                for k in keywords
            ],
        )
    logger.info("키워드 저장: %d개  document_id=%d", len(keywords), keywords[0].document_id)
    return len(keywords)


def get_keywords(doc_id: int, exclude_removed: bool = True) -> list[Keyword]:
    sql = "SELECT * FROM keywords WHERE document_id=?"
    if exclude_removed:
        sql += " AND is_user_removed=0"
    sql += " ORDER BY tfidf_score DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, (doc_id,)).fetchall()
    return [_row_to_keyword(r) for r in rows]


def update_keyword_removed(keyword_id: int, removed: bool) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE keywords SET is_user_removed=? WHERE id=?",
            (int(removed), keyword_id),
        )


def add_user_keyword(doc_id: int, word: str) -> Keyword:
    """사용자가 수동으로 키워드를 추가한다."""
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO keywords
               (document_id, word, tfidf_score, textrank_score, is_user_added)
               VALUES (?,?,0.0,0.0,1)""",
            (doc_id, word.strip()),
        )
        row = conn.execute(
            "SELECT * FROM keywords WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
    return _row_to_keyword(row)


# ──────────────────────────────────────────────
# 역색인 CRUD
# ──────────────────────────────────────────────

def build_inverted_index(doc_id: int, word_positions: dict[str, list[int]]) -> None:
    """
    역색인을 저장한다.

    Args:
        doc_id: 문서 ID
        word_positions: {단어: [위치1, 위치2, ...]} 형태의 딕셔너리
    """
    rows = [
        (word, doc_id, len(positions), json.dumps(positions, ensure_ascii=False))
        for word, positions in word_positions.items()
    ]
    with get_connection() as conn:
        conn.execute(
            "DELETE FROM inverted_index WHERE document_id=?", (doc_id,)
        )
        conn.executemany(
            """INSERT OR REPLACE INTO inverted_index
               (word, document_id, frequency, positions)
               VALUES (?,?,?,?)""",
            rows,
        )
    logger.info("역색인 구축: %d개 단어  document_id=%d", len(rows), doc_id)


def search_inverted_index(query: str, subject_id: Optional[int] = None) -> list[dict]:
    """
    역색인으로 키워드 검색을 수행한다.

    Returns:
        [{"word": ..., "document_id": ..., "title": ..., "frequency": ...}, ...]
    """
    sql = """
        SELECT ii.word, ii.document_id, d.title, ii.frequency
        FROM   inverted_index ii
        JOIN   documents d ON d.id = ii.document_id
        WHERE  ii.word LIKE ?
    """
    params: list[Any] = [f"%{query}%"]
    if subject_id is not None:
        sql += " AND d.subject_id = ?"
        params.append(subject_id)
    sql += " ORDER BY ii.frequency DESC LIMIT 50"

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────
# Quiz CRUD
# ──────────────────────────────────────────────

def save_quizzes(quizzes: list[Quiz]) -> int:
    if not quizzes:
        return 0
    with get_connection() as conn:
        conn.executemany(
            """INSERT INTO quizzes
               (document_id, quiz_type, question, answer, context, keyword)
               VALUES (?,?,?,?,?,?)""",
            [
                (
                    q.document_id, q.quiz_type.value,
                    q.question, q.answer, q.context, q.keyword,
                )
                for q in quizzes
            ],
        )
    logger.info("퀴즈 저장: %d개  document_id=%d", len(quizzes), quizzes[0].document_id)
    return len(quizzes)


def get_quizzes(doc_id: int, quiz_type: Optional[QuizType] = None) -> list[Quiz]:
    sql = "SELECT * FROM quizzes WHERE document_id=?"
    params: list[Any] = [doc_id]
    if quiz_type:
        sql += " AND quiz_type=?"
        params.append(quiz_type.value)
    sql += " ORDER BY created_at DESC"
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_quiz(r) for r in rows]


def delete_quizzes(doc_id: int) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM quizzes WHERE document_id=?", (doc_id,))


# ──────────────────────────────────────────────
# QuizSession / QuizResult CRUD
# ──────────────────────────────────────────────

def create_session(doc_id: int) -> QuizSession:
    with get_connection() as conn:
        cursor = conn.execute(
            "INSERT INTO quiz_sessions (document_id) VALUES (?)", (doc_id,)
        )
        row = conn.execute(
            "SELECT * FROM quiz_sessions WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
    return _row_to_session(row)


def complete_session(
    session_id: int, total: int, correct: int, score: float
) -> None:
    now = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """UPDATE quiz_sessions
               SET total_questions=?, correct_count=?, score=?,
                   completed=1, completed_at=?
               WHERE id=?""",
            (total, correct, round(score, 2), now, session_id),
        )
    logger.info("세션 완료: id=%d  score=%.1f", session_id, score)


def save_result(result: QuizResult) -> QuizResult:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO quiz_results
               (session_id, quiz_id, user_answer, is_correct)
               VALUES (?,?,?,?)""",
            (
                result.session_id, result.quiz_id,
                result.user_answer, int(result.is_correct),
            ),
        )
        row = conn.execute(
            "SELECT * FROM quiz_results WHERE id=?", (cursor.lastrowid,)
        ).fetchone()
    return QuizResult(
        id=row["id"], session_id=row["session_id"],
        quiz_id=row["quiz_id"], user_answer=row["user_answer"],
        is_correct=bool(row["is_correct"]),
        answered_at=_parse_dt(row["answered_at"]),
    )


def get_sessions(doc_id: int) -> list[QuizSession]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM quiz_sessions
               WHERE document_id=? AND completed=1
               ORDER BY completed_at DESC""",
            (doc_id,),
        ).fetchall()
    return [_row_to_session(r) for r in rows]


# ──────────────────────────────────────────────
# ComprehensionScore CRUD
# ──────────────────────────────────────────────

def save_score(score: ComprehensionScore) -> ComprehensionScore:
    with get_connection() as conn:
        cursor = conn.execute(
            """INSERT INTO comprehension_scores
               (document_id, chapter, quiz_score, coverage_score,
                keyword_density, total_score, missing_concepts)
               VALUES (?,?,?,?,?,?,?)""",
            (
                score.document_id, score.chapter,
                score.quiz_score, score.coverage_score,
                score.keyword_density, score.total_score,
                score.missing_concepts,
            ),
        )
        row = conn.execute(
            "SELECT * FROM comprehension_scores WHERE id=?",
            (cursor.lastrowid,),
        ).fetchone()
    result = _row_to_score(row)
    logger.info(
        "이해도 저장: doc=%d  chapter=%s  score=%.1f",
        result.document_id, result.chapter, result.total_score,
    )
    return result


def get_scores(doc_id: int) -> list[ComprehensionScore]:
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM comprehension_scores
               WHERE document_id=? ORDER BY measured_at DESC""",
            (doc_id,),
        ).fetchall()
    return [_row_to_score(r) for r in rows]


def get_latest_score(doc_id: int) -> Optional[ComprehensionScore]:
    with get_connection() as conn:
        row = conn.execute(
            """SELECT * FROM comprehension_scores
               WHERE document_id=? ORDER BY measured_at DESC LIMIT 1""",
            (doc_id,),
        ).fetchone()
    return _row_to_score(row) if row else None


# ──────────────────────────────────────────────
# 통계 / 대시보드 쿼리
# ──────────────────────────────────────────────

def get_subject_stats(subject_id: int) -> dict:
    """과목 전체 통계를 반환한다."""
    with get_connection() as conn:
        doc_count = conn.execute(
            "SELECT COUNT(*) FROM documents WHERE subject_id=?", (subject_id,)
        ).fetchone()[0]

        quiz_count = conn.execute(
            """SELECT COUNT(*) FROM quizzes q
               JOIN documents d ON d.id = q.document_id
               WHERE d.subject_id=?""",
            (subject_id,),
        ).fetchone()[0]

        avg_score = conn.execute(
            """SELECT AVG(cs.total_score)
               FROM comprehension_scores cs
               JOIN documents d ON d.id = cs.document_id
               WHERE d.subject_id=?""",
            (subject_id,),
        ).fetchone()[0]

    return {
        "document_count": doc_count,
        "quiz_count":     quiz_count,
        "avg_score":      round(avg_score or 0.0, 1),
    }
