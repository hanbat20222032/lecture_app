"""
core/textrank.py
TextRank — 그래프 기반 키워드·문장 중요도 순위
PageRank 알고리즘 직접 구현 (numpy 사용)

키워드 추출:
    단어 공동 출현(co-occurrence) 그래프 → PageRank
문장 추출:
    문장 간 코사인 유사도 그래프 → PageRank
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np

from utils.config import (
    TEXTRANK_TOP_N, TEXTRANK_DAMPING,
    TEXTRANK_MAX_ITER, TEXTRANK_CONVERGENCE,
)
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class TextRankResult:
    """TextRank 실행 결과."""
    keywords:  list[str]             # 키워드 목록 (점수 내림차순)
    scores:    list[float]           # PageRank 점수
    sentences: list[str]             # 핵심 문장 목록
    sent_scores: list[float]         # 문장 PageRank 점수
    iterations: int                  # PageRank 수렴까지 반복 횟수

    def top_keywords(self, n: int = 20) -> list[tuple[str, float]]:
        return list(zip(self.keywords[:n], self.scores[:n]))

    def top_sentences(self, n: int = 5) -> list[str]:
        return self.sentences[:n]

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.keywords, self.scores))


# ──────────────────────────────────────────────
# PageRank 구현
# ──────────────────────────────────────────────

def _pagerank(
    graph:       dict[int, dict[int, float]],
    n_nodes:     int,
    damping:     float = TEXTRANK_DAMPING,
    max_iter:    int   = TEXTRANK_MAX_ITER,
    convergence: float = TEXTRANK_CONVERGENCE,
) -> tuple[np.ndarray, int]:
    """
    기본 PageRank 알고리즘.

    Args:
        graph:   {node_id → {neighbor_id → weight}} 가중 방향 그래프
        n_nodes: 노드 수

    Returns:
        (scores: np.ndarray, iterations: int)
    """
    if n_nodes == 0:
        return np.array([]), 0

    # 초기 점수 균등 분배
    scores = np.ones(n_nodes, dtype=np.float64) / n_nodes

    # 열 합계 정규화 (열 확률 행렬)
    # 인접 행렬 A[i][j] = node j가 node i에 줄 가중치
    A = np.zeros((n_nodes, n_nodes), dtype=np.float64)
    for src, neighbors in graph.items():
        total_weight = sum(neighbors.values()) or 1.0
        for dst, w in neighbors.items():
            A[dst, src] = w / total_weight

    # 반복 계산
    for iteration in range(1, max_iter + 1):
        new_scores = (1 - damping) / n_nodes + damping * A @ scores
        delta = np.abs(new_scores - scores).sum()
        scores = new_scores
        if delta < convergence:
            logger.debug("PageRank 수렴: %d회 반복", iteration)
            return scores, iteration

    logger.debug("PageRank 최대 반복 도달: %d회", max_iter)
    return scores, max_iter


# ──────────────────────────────────────────────
# TextRank 엔진
# ──────────────────────────────────────────────

class TextRankEngine:
    """
    TextRank 엔진.

    키워드 추출:
        - 단어 공동 출현 그래프 (윈도우 크기 내 함께 등장하는 단어 쌍)
        - 각 노드(단어)의 PageRank 점수 = 키워드 중요도

    문장 추출:
        - 문장 벡터 (BoW) 간 코사인 유사도로 그래프 구성
        - 각 노드(문장)의 PageRank 점수 = 문장 중요도
    """

    def __init__(
        self,
        window_size: int   = 4,
        top_n:       int   = TEXTRANK_TOP_N,
        damping:     float = TEXTRANK_DAMPING,
        max_iter:    int   = TEXTRANK_MAX_ITER,
        convergence: float = TEXTRANK_CONVERGENCE,
    ):
        self.window_size = window_size
        self.top_n       = top_n
        self.damping     = damping
        self.max_iter    = max_iter
        self.convergence = convergence

    # ── 통합 실행 ───────────────────────────
    def run(
        self,
        tokens:    list[str],
        sentences: list[str],
    ) -> TextRankResult:
        """
        토큰 목록과 문장 목록으로 키워드 + 핵심 문장을 추출한다.

        Args:
            tokens:    전처리된 토큰 목록
            sentences: 원본 문장 목록

        Returns:
            TextRankResult
        """
        kw_result  = self.extract_keywords(tokens)
        sent_result = self.extract_sentences(sentences, tokens)

        return TextRankResult(
            keywords    = kw_result[0],
            scores      = kw_result[1],
            sentences   = sent_result[0],
            sent_scores = sent_result[1],
            iterations  = kw_result[2],
        )

    # ── 키워드 추출 ─────────────────────────
    def extract_keywords(
        self, tokens: list[str]
    ) -> tuple[list[str], list[float], int]:
        """
        공동 출현 그래프 기반 키워드 추출.

        Returns:
            (keywords, scores, iterations)
        """
        if not tokens:
            return [], [], 0

        # 중복 제거된 어휘 목록
        unique = list(dict.fromkeys(tokens))   # 순서 유지
        word2id = {w: i for i, w in enumerate(unique)}
        n = len(unique)

        # 공동 출현 그래프 구성
        graph: dict[int, dict[int, float]] = defaultdict(dict)
        for i in range(len(tokens)):
            src_id = word2id[tokens[i]]
            window = tokens[i + 1: i + self.window_size + 1]
            for neighbor in window:
                dst_id = word2id[neighbor]
                if src_id == dst_id:
                    continue
                # 가중치: 거리에 반비례
                pos_diff = abs(window.index(neighbor) + 1)
                weight   = 1.0 / pos_diff
                graph[src_id][dst_id] = (
                    graph[src_id].get(dst_id, 0.0) + weight
                )
                graph[dst_id][src_id] = (
                    graph[dst_id].get(src_id, 0.0) + weight
                )

        if not graph:
            # 그래프 없음 → 빈도 기반 폴백
            from collections import Counter
            freq = Counter(tokens)
            top  = freq.most_common(self.top_n)
            return [w for w, _ in top], [float(c) for _, c in top], 0

        scores, iters = _pagerank(
            graph, n, self.damping, self.max_iter, self.convergence
        )

        # 정렬 (내림차순)
        ranked = sorted(
            zip(unique, scores.tolist()),
            key=lambda x: x[1], reverse=True,
        )
        ranked = ranked[: self.top_n]

        keywords = [r[0] for r in ranked]
        kw_scores = [r[1] for r in ranked]

        logger.debug("TextRank 키워드: %d개  반복=%d", len(keywords), iters)
        return keywords, kw_scores, iters

    # ── 핵심 문장 추출 ──────────────────────
    def extract_sentences(
        self,
        sentences: list[str],
        all_tokens: list[str],
    ) -> tuple[list[str], list[float]]:
        """
        문장 간 유사도 그래프 기반 핵심 문장 추출.

        Args:
            sentences:  원본 문장 목록
            all_tokens: 전체 토큰 목록 (어휘 구성용)

        Returns:
            (top_sentences, scores)
        """
        if not sentences or len(sentences) < 2:
            return sentences[:self.top_n], [1.0] * len(sentences[:self.top_n])

        # 어휘 구성
        vocab = list(set(all_tokens))
        word2id = {w: i for i, w in enumerate(vocab)}
        n_vocab = len(vocab)

        # 문장별 BoW 벡터
        def sent_vector(sent: str) -> np.ndarray:
            vec = np.zeros(n_vocab, dtype=np.float64)
            for word in sent.split():
                if word in word2id:
                    vec[word2id[word]] += 1.0
            return vec

        vecs = [sent_vector(s) for s in sentences]
        n_sent = len(sentences)

        # 유사도 그래프 구성
        graph: dict[int, dict[int, float]] = defaultdict(dict)
        for i in range(n_sent):
            for j in range(i + 1, n_sent):
                sim = self._cosine(vecs[i], vecs[j])
                if sim > 0.001:
                    graph[i][j] = sim
                    graph[j][i] = sim

        if not any(graph.values()):
            # 그래프가 비어 있으면 앞에서 top_n개 반환
            return sentences[:self.top_n], [1.0] * min(self.top_n, n_sent)

        scores, _ = _pagerank(
            graph, n_sent, self.damping, self.max_iter, self.convergence
        )

        ranked = sorted(
            enumerate(scores.tolist()),
            key=lambda x: x[1], reverse=True,
        )
        top = ranked[: self.top_n]

        # 원래 문서 순서로 정렬 (가독성)
        top_sorted = sorted(top, key=lambda x: x[0])
        top_sentences = [sentences[i] for i, _ in top_sorted]
        top_scores    = [s for _, s in top_sorted]

        logger.debug("TextRank 핵심 문장: %d개", len(top_sentences))
        return top_sentences, top_scores

    # ── 헬퍼 ─────────────────────────────────
    @staticmethod
    def _cosine(a: np.ndarray, b: np.ndarray) -> float:
        """두 벡터의 코사인 유사도를 반환한다."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def extract_keywords_textrank(
    tokens: list[str], top_n: int = 20
) -> list[tuple[str, float]]:
    """토큰 목록에서 TextRank 키워드를 추출한다."""
    engine = TextRankEngine(top_n=top_n)
    keywords, scores, _ = engine.extract_keywords(tokens)
    return list(zip(keywords, scores))


def extract_sentences_textrank(
    sentences: list[str], tokens: list[str], top_n: int = 5
) -> list[str]:
    """핵심 문장을 추출한다."""
    engine = TextRankEngine(top_n=top_n)
    result, _ = engine.extract_sentences(sentences, tokens)
    return result
