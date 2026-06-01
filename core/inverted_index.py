"""
core/inverted_index.py
역색인 구축 및 검색
메모리 내 인덱스(빠른 분석용) + SQLite 영속 저장 지원
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class Posting:
    """역색인의 단일 포스팅 (단어가 등장하는 위치 정보)."""
    doc_id:    int
    positions: list[int]          # 텍스트 내 토큰 위치 인덱스 목록

    @property
    def frequency(self) -> int:
        return len(self.positions)


@dataclass
class SearchResult:
    """역색인 검색 결과 단건."""
    word:      str
    doc_id:    int
    title:     str
    frequency: int
    positions: list[int] = field(default_factory=list)

    @property
    def score(self) -> float:
        """간단한 TF 기반 점수 (로그 스케일)."""
        import math
        return math.log1p(self.frequency)


# ──────────────────────────────────────────────
# 인메모리 역색인
# ──────────────────────────────────────────────

class InvertedIndex:
    """
    메모리 내 역색인.

    구조:
        _index: {word: [Posting, ...]}

    특징:
        - 단일 문서 또는 다수 문서 지원
        - AND / OR 불리언 검색
        - 위치 기반 근접 검색
        - DB 저장/로드 지원
    """

    def __init__(self):
        # {word → [Posting]}
        self._index: dict[str, list[Posting]] = defaultdict(list)
        # {doc_id → 총 토큰 수} — TF 계산용
        self._doc_lengths: dict[int, int] = {}
        # {doc_id → 제목}
        self._doc_titles: dict[int, str]  = {}

    # ── 인덱스 구축 ─────────────────────────
    def build(
        self,
        tokens: list[str],
        doc_id: int,
        doc_title: str = "",
    ) -> dict[str, list[int]]:
        """
        토큰 목록으로 역색인을 구축한다.

        Args:
            tokens:    전처리된 토큰 목록 (순서 중요 — 위치 계산에 사용)
            doc_id:    문서 ID
            doc_title: 문서 제목

        Returns:
            {word: [위치1, 위치2, ...]} — DB 저장용
        """
        # 기존 문서 항목 제거 (재색인)
        self._remove_doc(doc_id)

        self._doc_lengths[doc_id] = len(tokens)
        self._doc_titles[doc_id]  = doc_title

        # 위치 인덱스 구성: {word → [pos]}
        word_positions: dict[str, list[int]] = defaultdict(list)
        for pos, token in enumerate(tokens):
            if token:
                word_positions[token].append(pos)

        # 인덱스에 추가
        for word, positions in word_positions.items():
            posting = Posting(doc_id=doc_id, positions=positions)
            self._index[word].append(posting)

        logger.debug(
            "역색인 구축: doc_id=%d  단어 %d종  토큰 %d개",
            doc_id, len(word_positions), len(tokens),
        )
        return dict(word_positions)

    def add_document(
        self,
        tokens: list[str],
        doc_id: int,
        doc_title: str = "",
    ) -> dict[str, list[int]]:
        """build()의 별칭. 문서를 인덱스에 추가한다."""
        return self.build(tokens, doc_id, doc_title)

    # ── 검색 ────────────────────────────────
    def search(
        self,
        query: str,
        doc_id: Optional[int] = None,
        top_n: int = 50,
    ) -> list[SearchResult]:
        """
        단어 검색. 부분 일치(LIKE) 방식.

        Args:
            query:  검색어
            doc_id: 특정 문서로 범위 제한 (None = 전체)
            top_n:  최대 반환 수
        """
        query = query.strip().lower()
        if not query:
            return []

        results: list[SearchResult] = []
        for word, postings in self._index.items():
            if query not in word.lower():
                continue
            for posting in postings:
                if doc_id is not None and posting.doc_id != doc_id:
                    continue
                results.append(SearchResult(
                    word      = word,
                    doc_id    = posting.doc_id,
                    title     = self._doc_titles.get(posting.doc_id, ""),
                    frequency = posting.frequency,
                    positions = posting.positions[:10],   # 위치 최대 10개
                ))

        # 빈도 내림차순 정렬
        results.sort(key=lambda r: r.frequency, reverse=True)
        return results[:top_n]

    def search_exact(
        self, word: str, doc_id: Optional[int] = None
    ) -> list[SearchResult]:
        """정확히 일치하는 단어 검색."""
        postings = self._index.get(word, [])
        results = []
        for p in postings:
            if doc_id is not None and p.doc_id != doc_id:
                continue
            results.append(SearchResult(
                word=word, doc_id=p.doc_id,
                title=self._doc_titles.get(p.doc_id, ""),
                frequency=p.frequency, positions=p.positions,
            ))
        return results

    def search_and(
        self, words: list[str], doc_id: Optional[int] = None
    ) -> list[int]:
        """
        AND 검색 — 모든 단어가 포함된 문서 ID 목록 반환.
        """
        if not words:
            return []
        sets = []
        for word in words:
            postings = self._index.get(word, [])
            if doc_id is not None:
                ids = {p.doc_id for p in postings if p.doc_id == doc_id}
            else:
                ids = {p.doc_id for p in postings}
            sets.append(ids)
        if not sets:
            return []
        result = sets[0]
        for s in sets[1:]:
            result &= s
        return sorted(result)

    def search_or(
        self, words: list[str], doc_id: Optional[int] = None
    ) -> list[int]:
        """OR 검색 — 하나 이상의 단어가 포함된 문서 ID 목록."""
        result: set[int] = set()
        for word in words:
            for p in self._index.get(word, []):
                if doc_id is None or p.doc_id == doc_id:
                    result.add(p.doc_id)
        return sorted(result)

    # ── 통계 / 유틸 ─────────────────────────
    def get_word_frequency(self, word: str, doc_id: int) -> int:
        """특정 문서에서 단어의 등장 횟수를 반환한다."""
        for p in self._index.get(word, []):
            if p.doc_id == doc_id:
                return p.frequency
        return 0

    def get_tf(self, word: str, doc_id: int) -> float:
        """단어의 TF (Term Frequency) 값을 반환한다."""
        freq   = self.get_word_frequency(word, doc_id)
        length = self._doc_lengths.get(doc_id, 1)
        return freq / length if length > 0 else 0.0

    def vocabulary(self) -> list[str]:
        """인덱스에 등록된 전체 단어 목록을 반환한다."""
        return sorted(self._index.keys())

    def doc_count(self) -> int:
        """인덱스에 등록된 문서 수를 반환한다."""
        return len(self._doc_lengths)

    def word_count(self) -> int:
        """인덱스에 등록된 고유 단어 수를 반환한다."""
        return len(self._index)

    def get_top_words(
        self, doc_id: int, top_n: int = 30
    ) -> list[tuple[str, int]]:
        """
        특정 문서에서 빈도 상위 단어를 반환한다.

        Returns:
            [(word, frequency), ...] 빈도 내림차순
        """
        word_freq: list[tuple[str, int]] = []
        for word, postings in self._index.items():
            for p in postings:
                if p.doc_id == doc_id:
                    word_freq.append((word, p.frequency))
                    break
        word_freq.sort(key=lambda x: x[1], reverse=True)
        return word_freq[:top_n]

    def keywords_coverage(
        self, keywords: list[str], doc_id: int
    ) -> dict[str, int]:
        """
        키워드 목록이 문서에 얼마나 등장하는지 반환한다.
        이해도 측정의 커버리지 계산에 사용.

        Returns:
            {keyword: frequency} — 등장하지 않으면 0
        """
        return {
            kw: self.get_word_frequency(kw, doc_id)
            for kw in keywords
        }

    # ── 직렬화 ──────────────────────────────
    def to_db_format(self, doc_id: int) -> dict[str, list[int]]:
        """
        DB 저장 형식으로 변환한다.
        {word: [pos1, pos2, ...]}
        """
        result: dict[str, list[int]] = {}
        for word, postings in self._index.items():
            for p in postings:
                if p.doc_id == doc_id:
                    result[word] = p.positions
                    break
        return result

    def _remove_doc(self, doc_id: int):
        """문서의 기존 인덱스 항목을 모두 제거한다."""
        for word in list(self._index.keys()):
            self._index[word] = [
                p for p in self._index[word] if p.doc_id != doc_id
            ]
            if not self._index[word]:
                del self._index[word]
        self._doc_lengths.pop(doc_id, None)
        self._doc_titles.pop(doc_id, None)

    def clear(self):
        """인덱스 전체를 초기화한다."""
        self._index.clear()
        self._doc_lengths.clear()
        self._doc_titles.clear()


# ──────────────────────────────────────────────
# 앱 전역 싱글턴 인덱스
# ──────────────────────────────────────────────

_global_index = InvertedIndex()


def get_global_index() -> InvertedIndex:
    """앱 전역 역색인 인스턴스를 반환한다."""
    return _global_index


def build_and_save(
    tokens: list[str],
    doc_id: int,
    doc_title: str = "",
) -> dict[str, list[int]]:
    """
    전역 역색인에 문서를 추가하고 DB 저장 형식을 반환한다.
    분석 파이프라인에서 이 함수를 호출한다.
    """
    from database.db_manager import build_inverted_index
    word_positions = _global_index.build(tokens, doc_id, doc_title)
    build_inverted_index(doc_id, word_positions)
    logger.info(
        "역색인 저장 완료: doc_id=%d  단어 %d종",
        doc_id, len(word_positions),
    )
    return word_positions


def load_from_db(doc_id: int, doc_title: str = "") -> None:
    """
    DB에 저장된 역색인을 전역 인덱스로 로드한다.
    앱 시작 시 또는 문서 전환 시 호출.
    """
    from database.db_manager import get_connection
    try:
        with get_connection() as conn:
            rows = conn.execute(
                "SELECT word, frequency, positions FROM inverted_index WHERE document_id=?",
                (doc_id,),
            ).fetchall()
        for row in rows:
            positions = json.loads(row["positions"])
            posting = Posting(doc_id=doc_id, positions=positions)
            _global_index._index[row["word"]].append(posting)
            _global_index._doc_lengths[doc_id] = (
                _global_index._doc_lengths.get(doc_id, 0) + row["frequency"]
            )
        _global_index._doc_titles[doc_id] = doc_title
        logger.debug("역색인 로드: doc_id=%d  %d개 단어", doc_id, len(rows))
    except Exception as e:
        logger.warning("역색인 로드 실패: doc_id=%d  %s", doc_id, e)
