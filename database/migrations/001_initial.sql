-- database/migrations/001_initial.sql
-- 강의 이해도 측정 앱 초기 스키마
-- SQLite 3.35+

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- ──────────────────────────────────────────────
-- 과목 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    description TEXT    NOT NULL DEFAULT '',
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_subjects_name ON subjects(name);

-- updated_at 자동 갱신 트리거
CREATE TRIGGER IF NOT EXISTS trg_subjects_updated
    AFTER UPDATE ON subjects
    FOR EACH ROW
BEGIN
    UPDATE subjects
    SET    updated_at = strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')
    WHERE  id = OLD.id;
END;


-- ──────────────────────────────────────────────
-- 문서 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS documents (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  INTEGER NOT NULL REFERENCES subjects(id) ON DELETE CASCADE,
    title       TEXT    NOT NULL,
    source_type TEXT    NOT NULL CHECK(source_type IN ('pdf', 'txt', 'text')),
    language    TEXT    NOT NULL DEFAULT 'ko' CHECK(language IN ('ko', 'en')),
    file_path   TEXT,
    content     TEXT,
    page_count  INTEGER,
    char_count  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_documents_subject ON documents(subject_id);
CREATE INDEX IF NOT EXISTS idx_documents_type    ON documents(source_type);


-- ──────────────────────────────────────────────
-- 키워드 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS keywords (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    word             TEXT    NOT NULL,
    tfidf_score      REAL    NOT NULL DEFAULT 0.0,
    textrank_score   REAL    NOT NULL DEFAULT 0.0,
    frequency        INTEGER NOT NULL DEFAULT 1,
    is_user_added    INTEGER NOT NULL DEFAULT 0 CHECK(is_user_added IN (0, 1)),
    is_user_removed  INTEGER NOT NULL DEFAULT 0 CHECK(is_user_removed IN (0, 1)),
    created_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_keywords_document ON keywords(document_id);
CREATE INDEX IF NOT EXISTS idx_keywords_word     ON keywords(word);
CREATE INDEX IF NOT EXISTS idx_keywords_tfidf    ON keywords(tfidf_score DESC);


-- ──────────────────────────────────────────────
-- 역색인 테이블 (키워드 → 문서 검색)
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS inverted_index (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    word         TEXT    NOT NULL,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    frequency    INTEGER NOT NULL DEFAULT 1,
    positions    TEXT    NOT NULL DEFAULT '[]'  -- JSON 배열: 단어 등장 위치 목록
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_inverted_word_doc ON inverted_index(word, document_id);
CREATE        INDEX IF NOT EXISTS idx_inverted_word     ON inverted_index(word);


-- ──────────────────────────────────────────────
-- 퀴즈 문제 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quizzes (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id  INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    quiz_type    TEXT    NOT NULL CHECK(quiz_type IN ('blank', 'ox')),
    question     TEXT    NOT NULL,
    answer       TEXT    NOT NULL,
    context      TEXT    NOT NULL DEFAULT '',
    keyword      TEXT    NOT NULL DEFAULT '',
    created_at   TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_quizzes_document ON quizzes(document_id);
CREATE INDEX IF NOT EXISTS idx_quizzes_type     ON quizzes(quiz_type);


-- ──────────────────────────────────────────────
-- 퀴즈 세션 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    total_questions  INTEGER NOT NULL DEFAULT 0,
    correct_count    INTEGER NOT NULL DEFAULT 0,
    score            REAL    NOT NULL DEFAULT 0.0,
    completed        INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
    started_at       TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime')),
    completed_at     TEXT
);

CREATE INDEX IF NOT EXISTS idx_sessions_document ON quiz_sessions(document_id);


-- ──────────────────────────────────────────────
-- 퀴즈 개별 결과 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS quiz_results (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   INTEGER NOT NULL REFERENCES quiz_sessions(id) ON DELETE CASCADE,
    quiz_id      INTEGER NOT NULL REFERENCES quizzes(id) ON DELETE CASCADE,
    user_answer  TEXT    NOT NULL,
    is_correct   INTEGER NOT NULL DEFAULT 0 CHECK(is_correct IN (0, 1)),
    answered_at  TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_results_session ON quiz_results(session_id);
CREATE INDEX IF NOT EXISTS idx_results_correct ON quiz_results(is_correct);


-- ──────────────────────────────────────────────
-- 이해도 점수 테이블
-- ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS comprehension_scores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id      INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chapter          TEXT    NOT NULL DEFAULT '전체',
    quiz_score       REAL    NOT NULL DEFAULT 0.0,
    coverage_score   REAL    NOT NULL DEFAULT 0.0,
    keyword_density  REAL    NOT NULL DEFAULT 0.0,
    total_score      REAL    NOT NULL DEFAULT 0.0,
    missing_concepts TEXT    NOT NULL DEFAULT '[]',  -- JSON 배열
    measured_at      TEXT    NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%S', 'now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_scores_document ON comprehension_scores(document_id);
CREATE INDEX IF NOT EXISTS idx_scores_chapter  ON comprehension_scores(chapter);
