"""
core/tfidf_engine.py
TF-IDF 엔진 — numpy 직접 구현 (외부 ML 라이브러리 없음)

지원:
    - 단일 문서 내 키워드 추출
    - 다중 문서 TF-IDF 행렬
    - 유니그램 + 바이그램
    - 서브리니어 TF 스케일링
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Optional

import numpy as np

from utils.config import TFIDF_MAX_FEATURES, TFIDF_MIN_DF, TFIDF_NGRAM_RANGE
from utils.logger import get_logger

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class TFIDFResult:
    """TF-IDF 계산 결과."""
    keywords:    list[str]            # 키워드 목록 (점수 내림차순)
    scores:      list[float]          # 각 키워드의 TF-IDF 점수
    vocab:       list[str]            # 전체 어휘 목록
    tfidf_matrix: Optional[np.ndarray] = None  # (n_docs, n_vocab) 행렬

    def top_n(self, n: int = 20) -> list[tuple[str, float]]:
        """상위 n개 (keyword, score) 쌍 반환."""
        pairs = sorted(zip(self.keywords, self.scores),
                       key=lambda x: x[1], reverse=True)
        return pairs[:n]

    def as_dict(self) -> dict[str, float]:
        return dict(zip(self.keywords, self.scores))


# ──────────────────────────────────────────────
# TF-IDF 엔진
# ──────────────────────────────────────────────

class TFIDFEngine:
    """
    TF-IDF 직접 구현체.

    수식:
        TF(t, d)   = log(1 + count(t, d))          # 서브리니어
        IDF(t, D)  = log((|D|+1) / (df(t)+1)) + 1  # 스무딩
        TF-IDF     = TF × IDF

    사용법:
        engine = TFIDFEngine()
        # 단일 문서
        result = engine.fit_single(tokens)
        print(result.top_n(10))

        # 다중 문서
        result = engine.fit(corpus)   # corpus = [[tokens_doc1], [tokens_doc2], ...]
    """

    def __init__(
        self,
        max_features:  int   = TFIDF_MAX_FEATURES,
        min_df:        int   = TFIDF_MIN_DF,
        ngram_range:   tuple = TFIDF_NGRAM_RANGE,
        sublinear_tf:  bool  = True,
        smooth_idf:    bool  = True,
    ):
        self.max_features = max_features
        self.min_df       = min_df
        self.ngram_range  = ngram_range
        self.sublinear_tf = sublinear_tf
        self.smooth_idf   = smooth_idf

        # 학습된 상태
        self._vocab:     list[str]          = []
        self._vocab_idx: dict[str, int]     = {}
        self._idf:       Optional[np.ndarray] = None
        self._df:        dict[str, int]     = {}

    # ── 단일 문서 ────────────────────────────
    def fit_single(self, tokens: list[str]) -> TFIDFResult:
        """
        단일 문서의 토큰으로 TF-IDF 점수를 계산한다.
        다중 문서가 없으므로 IDF = log(2/(df+1))+1 로 근사.
        """
        if not tokens:
            return TFIDFResult(keywords=[], scores=[], vocab=[])

        ngrams  = self._make_ngrams(tokens)
        tf_dict = self._compute_tf(ngrams)

        # 단일 문서: IDF를 역 빈도로 근사 (자주 나오는 단어 = 낮은 IDF)
        total  = sum(tf_dict.values()) or 1
        result_pairs: list[tuple[str, float]] = []
        for term, tf in tf_dict.items():
            # TF 서브리니어
            tf_val = math.log1p(tf) if self.sublinear_tf else tf / total
            # IDF 근사: 전체 토큰 수 대비 해당 단어 빈도의 역수
            idf_val = math.log((total + 1) / (tf + 1)) + 1
            result_pairs.append((term, tf_val * idf_val))

        # 정렬 및 상위 N개
        result_pairs.sort(key=lambda x: x[1], reverse=True)
        result_pairs = result_pairs[: self.max_features]

        keywords = [p[0] for p in result_pairs]
        scores   = [p[1] for p in result_pairs]

        logger.debug("단일문서 TF-IDF: %d개 키워드", len(keywords))
        return TFIDFResult(keywords=keywords, scores=scores, vocab=keywords)

    # ── 다중 문서 ────────────────────────────
    def fit(self, corpus: list[list[str]]) -> TFIDFResult:
        """
        다중 문서 코퍼스에 TF-IDF를 적합한다.

        Args:
            corpus: 문서별 토큰 목록의 리스트
                    [[doc1_tokens], [doc2_tokens], ...]

        Returns:
            TFIDFResult (tfidf_matrix 포함)
        """
        if not corpus:
            return TFIDFResult(keywords=[], scores=[], vocab=[])

        n_docs = len(corpus)
        ngram_corpus = [self._make_ngrams(doc) for doc in corpus]

        # 1. 어휘 구축 및 DF 계산
        self._build_vocab(ngram_corpus, n_docs)
        if not self._vocab:
            return TFIDFResult(keywords=[], scores=[], vocab=[])

        n_vocab = len(self._vocab)

        # 2. TF 행렬 구성 (n_docs × n_vocab)
        tf_matrix = np.zeros((n_docs, n_vocab), dtype=np.float32)
        for i, ngrams in enumerate(ngram_corpus):
            tf_dict = self._compute_tf(ngrams)
            for term, tf in tf_dict.items():
                j = self._vocab_idx.get(term)
                if j is not None:
                    tf_matrix[i, j] = (
                        math.log1p(tf) if self.sublinear_tf else tf
                    )

        # 3. IDF 벡터
        self._idf = self._compute_idf(n_docs)

        # 4. TF-IDF 행렬
        tfidf_matrix = tf_matrix * self._idf   # 브로드캐스트

        # 5. 전체 점수 집계 (문서 평균)
        mean_scores  = tfidf_matrix.mean(axis=0)
        sorted_idx   = np.argsort(mean_scores)[::-1][: self.max_features]

        keywords = [self._vocab[i] for i in sorted_idx]
        scores   = [float(mean_scores[i]) for i in sorted_idx]

        logger.info(
            "다중문서 TF-IDF: 문서 %d개  어휘 %d개  키워드 %d개",
            n_docs, n_vocab, len(keywords),
        )
        return TFIDFResult(
            keywords     = keywords,
            scores       = scores,
            vocab        = self._vocab,
            tfidf_matrix = tfidf_matrix,
        )

    def transform(self, tokens: list[str]) -> np.ndarray:
        """
        fit() 이후 새 문서의 TF-IDF 벡터를 반환한다.
        코사인 유사도 계산에 사용.
        """
        if self._idf is None or not self._vocab:
            raise RuntimeError("먼저 fit()을 호출하세요.")

        ngrams  = self._make_ngrams(tokens)
        tf_dict = self._compute_tf(ngrams)
        vec     = np.zeros(len(self._vocab), dtype=np.float32)
        for term, tf in tf_dict.items():
            j = self._vocab_idx.get(term)
            if j is not None:
                vec[j] = math.log1p(tf) if self.sublinear_tf else tf
        return vec * self._idf

    # ── 내부 메서드 ─────────────────────────
    def _make_ngrams(self, tokens: list[str]) -> list[str]:
        """설정된 ngram_range에 따라 n-gram 생성."""
        result: list[str] = []
        lo, hi = self.ngram_range
        for n in range(lo, hi + 1):
            if n == 1:
                result.extend(tokens)
            else:
                for i in range(len(tokens) - n + 1):
                    result.append("_".join(tokens[i: i + n]))
        return result

    def _compute_tf(self, ngrams: list[str]) -> dict[str, int]:
        """토큰 목록의 빈도 딕셔너리 반환."""
        return dict(Counter(ngrams))

    def _build_vocab(self, ngram_corpus: list[list[str]], n_docs: int):
        """코퍼스에서 어휘를 구축하고 DF를 계산한다."""
        df: dict[str, int] = Counter()
        all_terms: set[str] = set()
        for ngrams in ngram_corpus:
            unique_in_doc = set(ngrams)
            all_terms |= unique_in_doc
            for term in unique_in_doc:
                df[term] += 1

        # min_df 필터링
        filtered = {t: c for t, c in df.items() if c >= self.min_df}

        # 빈도 기준 상위 max_features 선택
        sorted_terms = sorted(filtered.items(), key=lambda x: x[1], reverse=True)
        selected     = [t for t, _ in sorted_terms[: self.max_features]]

        self._vocab     = selected
        self._vocab_idx = {t: i for i, t in enumerate(selected)}
        self._df        = {t: df[t] for t in selected}

    def _compute_idf(self, n_docs: int) -> np.ndarray:
        """IDF 벡터를 계산한다."""
        idf = np.zeros(len(self._vocab), dtype=np.float32)
        for i, term in enumerate(self._vocab):
            df_t  = self._df.get(term, 0)
            if self.smooth_idf:
                idf[i] = math.log((n_docs + 1) / (df_t + 1)) + 1
            else:
                idf[i] = math.log(n_docs / max(df_t, 1)) + 1
        return idf

    # ── 유틸 ─────────────────────────────────
    def get_feature_names(self) -> list[str]:
        return list(self._vocab)

    def vocabulary_size(self) -> int:
        return len(self._vocab)

    def is_fitted(self) -> bool:
        return self._idf is not None


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def compute_tfidf_single(tokens: list[str], top_n: int = 50) -> list[tuple[str, float]]:
    """단일 문서에서 상위 키워드와 점수를 반환한다."""
    engine = TFIDFEngine(max_features=top_n * 2)
    result = engine.fit_single(tokens)
    return result.top_n(top_n)


def compute_tfidf_corpus(
    corpus: list[list[str]], top_n: int = 50
) -> tuple[list[tuple[str, float]], TFIDFEngine]:
    """
    다중 문서 코퍼스에 TF-IDF를 적용한다.

    Returns:
        ([(keyword, score), ...], fitted_engine)
    """
    engine = TFIDFEngine(max_features=top_n * 2)
    result = engine.fit(corpus)
    return result.top_n(top_n), engine
