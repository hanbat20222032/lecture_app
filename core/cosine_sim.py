"""
core/cosine_sim.py
코사인 유사도 — 문서 비교 및 이해도 커버리지 계산
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Optional

import numpy as np

from utils.config import COSINE_SIM_THRESHOLD
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 기본 코사인 유사도
# ──────────────────────────────────────────────

def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """두 numpy 벡터의 코사인 유사도를 반환한다."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


def cosine_similarity_tokens(
    tokens_a: list[str], tokens_b: list[str]
) -> float:
    """
    두 토큰 목록의 코사인 유사도를 BoW 벡터로 계산한다.
    공통 어휘만 사용하므로 별도의 vectorizer 불필요.
    """
    if not tokens_a or not tokens_b:
        return 0.0

    vocab = list(set(tokens_a) | set(tokens_b))
    w2i   = {w: i for i, w in enumerate(vocab)}

    def to_vec(tokens: list[str]) -> np.ndarray:
        vec = np.zeros(len(vocab), dtype=np.float64)
        for t in tokens:
            if t in w2i:
                vec[w2i[t]] += 1.0
        return vec

    return cosine_similarity(to_vec(tokens_a), to_vec(tokens_b))


def cosine_matrix(tfidf_matrix: np.ndarray) -> np.ndarray:
    """
    TF-IDF 행렬에서 문서 간 코사인 유사도 행렬을 계산한다.

    Args:
        tfidf_matrix: (n_docs, n_vocab) 배열

    Returns:
        (n_docs, n_docs) 유사도 행렬
    """
    norms = np.linalg.norm(tfidf_matrix, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    normalized = tfidf_matrix / norms
    return normalized @ normalized.T


# ──────────────────────────────────────────────
# 커버리지 계산
# ──────────────────────────────────────────────

def compute_coverage(
    source_keywords: list[str],
    target_tokens:   list[str],
) -> dict:
    """
    소스(PDF) 키워드가 대상(필기·입력 텍스트) 토큰에
    얼마나 포함되어 있는지(커버리지)를 계산한다.

    Args:
        source_keywords: PDF에서 추출한 핵심 키워드 목록
        target_tokens:   필기·직접 입력 텍스트의 토큰 목록

    Returns:
        {
            "coverage_rate":    float,     # 0.0 ~ 1.0
            "covered_count":    int,
            "missing_count":    int,
            "covered":          list[str],
            "missing":          list[str],
            "partial":          list[str],  # 부분 일치
        }
    """
    if not source_keywords:
        return {
            "coverage_rate": 1.0, "covered_count": 0,
            "missing_count": 0, "covered": [], "missing": [], "partial": [],
        }

    target_set = set(target_tokens)
    target_str = " ".join(target_tokens)

    covered: list[str] = []
    missing: list[str] = []
    partial: list[str] = []

    for kw in source_keywords:
        if kw in target_set:
            covered.append(kw)
        elif any(kw in t or t in kw for t in target_set if len(t) >= 2):
            partial.append(kw)
        else:
            missing.append(kw)

    # 부분 일치는 0.5점으로 반영
    covered_score  = len(covered) + len(partial) * 0.5
    coverage_rate  = covered_score / len(source_keywords)

    result = {
        "coverage_rate":  round(coverage_rate, 4),
        "covered_count":  len(covered),
        "partial_count":  len(partial),
        "missing_count":  len(missing),
        "covered":        covered,
        "partial":        partial,
        "missing":        missing,
    }
    logger.debug(
        "커버리지: %.1f%%  covered=%d  partial=%d  missing=%d",
        coverage_rate * 100, len(covered), len(partial), len(missing),
    )
    return result


def compute_keyword_density(
    keywords: list[str],
    tokens:   list[str],
) -> float:
    """
    키워드 밀도를 계산한다.
    전체 토큰 중 키워드가 차지하는 비율 (0~1).
    """
    if not tokens:
        return 0.0
    kw_set  = set(keywords)
    kw_hits = sum(1 for t in tokens if t in kw_set)
    return kw_hits / len(tokens)


# ──────────────────────────────────────────────
# 문서 유사도 비교
# ──────────────────────────────────────────────

def compare_documents(
    tokens_a: list[str],
    tokens_b: list[str],
    label_a:  str = "문서 A",
    label_b:  str = "문서 B",
) -> dict:
    """
    두 문서(PDF vs 필기)를 비교하여 유사도와 차이를 분석한다.

    Returns:
        {
            "similarity":   float,   # 코사인 유사도
            "common_words": list,
            "only_a":       list,    # A에만 있는 단어
            "only_b":       list,    # B에만 있는 단어
            "is_similar":   bool,    # threshold 이상이면 True
        }
    """
    set_a = set(tokens_a)
    set_b = set(tokens_b)

    similarity  = cosine_similarity_tokens(tokens_a, tokens_b)
    common      = sorted(set_a & set_b)
    only_a      = sorted(set_a - set_b)
    only_b      = sorted(set_b - set_a)

    result = {
        "similarity":   round(similarity, 4),
        "common_words": common,
        "only_a":       only_a,
        "only_b":       only_b,
        "is_similar":   similarity >= COSINE_SIM_THRESHOLD,
        "label_a":      label_a,
        "label_b":      label_b,
    }
    logger.debug(
        "문서 비교: %s vs %s  유사도=%.3f  공통=%d  A전용=%d  B전용=%d",
        label_a, label_b, similarity, len(common), len(only_a), len(only_b),
    )
    return result


def rank_keywords_by_coverage(
    source_keywords:  list[str],
    source_scores:    list[float],
    target_tokens:    list[str],
) -> list[dict]:
    """
    소스 키워드를 커버리지 여부 + TF-IDF 점수로 정렬한 목록을 반환한다.
    분석 탭의 키워드 테이블 표시에 사용.

    Returns:
        [{"word", "tfidf_score", "in_target", "frequency"}, ...]
    """
    target_set   = set(target_tokens)
    target_freq  = Counter(target_tokens)
    result: list[dict] = []

    for kw, score in zip(source_keywords, source_scores):
        result.append({
            "word":        kw,
            "tfidf_score": round(score, 6),
            "in_target":   kw in target_set,
            "frequency":   target_freq.get(kw, 0),
        })

    # 정렬: 커버리지 True 우선, 같으면 TF-IDF 점수 내림차순
    result.sort(key=lambda x: (not x["in_target"], -x["tfidf_score"]))
    return result
