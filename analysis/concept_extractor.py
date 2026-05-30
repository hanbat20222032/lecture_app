"""
analysis/concept_extractor.py
핵심 개념 추출기 — TF-IDF + TextRank 결합
가중 합산: TF-IDF 60% + TextRank 40%

흐름:
    ProcessedText → TF-IDF → TextRank → 결합 점수 → DB 저장 → Keyword 목록
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core.tfidf_engine import TFIDFEngine, TFIDFResult
from core.textrank     import TextRankEngine, TextRankResult
from core.cosine_sim   import compute_coverage, compute_keyword_density
from core.text_processor import ProcessedText
from database import db_manager as db
from database.models import Keyword
from utils.config import SCORE_WEIGHTS
from utils.logger import get_logger

logger = get_logger(__name__)

# TF-IDF : TextRank 가중치
_W_TFIDF    = 0.60
_W_TEXTRANK = 0.40


# ──────────────────────────────────────────────
# 결과 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class ExtractionResult:
    """개념 추출 결과."""
    doc_id:          int
    keywords:        list[Keyword]          # DB 저장된 Keyword 객체
    tfidf_result:    TFIDFResult
    textrank_result: TextRankResult
    top_sentences:   list[str]             # 핵심 문장 목록
    language:        str

    @property
    def top_keywords(self) -> list[Keyword]:
        """결합 점수 내림차순 상위 키워드."""
        return sorted(
            self.keywords, key=lambda k: k.combined_score, reverse=True
        )

    @property
    def keyword_words(self) -> list[str]:
        return [k.word for k in self.top_keywords]

    @property
    def keyword_count(self) -> int:
        return len(self.keywords)


# ──────────────────────────────────────────────
# 개념 추출기
# ──────────────────────────────────────────────

class ConceptExtractor:
    """
    TF-IDF + TextRank 결합 핵심 개념 추출기.

    사용법:
        extractor = ConceptExtractor()
        result = extractor.extract(processed, doc_id=1)
        for kw in result.top_keywords[:10]:
            print(kw.word, kw.combined_score)
    """

    def __init__(
        self,
        max_keywords: int = 50,
        tfidf_weight: float = _W_TFIDF,
        tr_weight:    float = _W_TEXTRANK,
    ):
        self.max_keywords  = max_keywords
        self.tfidf_weight  = tfidf_weight
        self.tr_weight     = tr_weight
        self._tfidf_engine = TFIDFEngine(max_features=max_keywords * 3)
        self._tr_engine    = TextRankEngine(top_n=max_keywords * 2)

    # ── 단일 문서 추출 ──────────────────────
    def extract(
        self,
        processed: ProcessedText,
        doc_id:    int,
        save_to_db: bool = True,
    ) -> ExtractionResult:
        """
        전처리 결과에서 핵심 개념을 추출한다.

        Args:
            processed:  TextProcessor.process() 결과
            doc_id:     문서 DB ID
            save_to_db: True이면 keywords 테이블에 저장

        Returns:
            ExtractionResult
        """
        tokens    = processed.tokens
        sentences = processed.sentences
        language  = processed.language

        if not tokens:
            logger.warning("토큰이 없어 추출 불가: doc_id=%d", doc_id)
            return ExtractionResult(
                doc_id=doc_id, keywords=[],
                tfidf_result=TFIDFResult([], [], []),
                textrank_result=TextRankResult([], [], [], [], 0),
                top_sentences=[], language=language,
            )

        logger.info(
            "개념 추출 시작: doc_id=%d  토큰=%d  문장=%d",
            doc_id, len(tokens), len(sentences),
        )

        # 1. TF-IDF
        tfidf_result = self._tfidf_engine.fit_single(tokens)
        tfidf_dict   = tfidf_result.as_dict()

        # 2. TextRank
        tr_result  = self._tr_engine.run(tokens, sentences)
        tr_dict    = tr_result.as_dict()

        # 3. 결합 점수 계산
        all_words  = set(tfidf_dict) | set(tr_dict)
        combined: list[tuple[str, float, float, float]] = []
        # (word, tfidf, textrank, combined)

        for word in all_words:
            tf_score = tfidf_dict.get(word, 0.0)
            tr_score = tr_dict.get(word, 0.0)
            # 0~1 정규화 후 가중 합산
            comb = self.tfidf_weight * tf_score + self.tr_weight * tr_score
            combined.append((word, tf_score, tr_score, comb))

        # 내림차순 정렬 후 상위 N개
        combined.sort(key=lambda x: x[3], reverse=True)
        combined = combined[: self.max_keywords]

        # 4. Keyword 객체 생성
        freq_dict = processed.token_freq
        keywords: list[Keyword] = []
        for word, tf_score, tr_score, comb_score in combined:
            keywords.append(Keyword(
                document_id    = doc_id,
                word           = word,
                tfidf_score    = round(tf_score, 6),
                textrank_score = round(tr_score, 6),
                frequency      = freq_dict.get(word, 1),
            ))

        # 5. DB 저장
        if save_to_db and keywords:
            # 기존 키워드 삭제 후 재저장
            self._clear_keywords(doc_id)
            db.save_keywords(keywords)

        # 6. 핵심 문장 (최대 5개)
        top_sents = tr_result.top_sentences(5)

        result = ExtractionResult(
            doc_id          = doc_id,
            keywords        = keywords,
            tfidf_result    = tfidf_result,
            textrank_result = tr_result,
            top_sentences   = top_sents,
            language        = language,
        )
        logger.info(
            "개념 추출 완료: doc_id=%d  키워드=%d개  문장=%d개",
            doc_id, len(keywords), len(top_sents),
        )
        return result

    # ── 다중 문서 비교 ──────────────────────
    def extract_multi(
        self,
        processed_list: list[ProcessedText],
        doc_ids:        list[int],
        save_to_db:     bool = True,
    ) -> list[ExtractionResult]:
        """
        여러 문서에 대해 코퍼스 TF-IDF를 적용하여 비교 정확도를 높인다.
        PDF + 필기 노트를 함께 분석할 때 사용.
        """
        corpus = [p.tokens for p in processed_list]

        # 코퍼스 TF-IDF
        self._tfidf_engine.fit(corpus)

        results: list[ExtractionResult] = []
        for i, (processed, doc_id) in enumerate(zip(processed_list, doc_ids)):
            # 각 문서의 TF-IDF 벡터
            vec       = self._tfidf_engine.transform(processed.tokens)
            tfidf_top = sorted(
                zip(self._tfidf_engine.get_feature_names(), vec.tolist()),
                key=lambda x: x[1], reverse=True,
            )[: self.max_keywords]
            tfidf_dict = dict(tfidf_top)

            # TextRank
            tr_result = self._tr_engine.run(
                processed.tokens, processed.sentences
            )
            tr_dict = tr_result.as_dict()

            # 결합
            all_words = set(tfidf_dict) | set(tr_dict)
            combined: list[tuple[str, float, float]] = []
            for word in all_words:
                tf_s  = tfidf_dict.get(word, 0.0)
                tr_s  = tr_dict.get(word, 0.0)
                combined.append((
                    word, tf_s, tr_s,
                ))
            combined.sort(key=lambda x: self.tfidf_weight * x[1] + self.tr_weight * x[2], reverse=True)
            combined = combined[: self.max_keywords]

            keywords: list[Keyword] = []
            for word, tf_s, tr_s in combined:
                keywords.append(Keyword(
                    document_id    = doc_id,
                    word           = word,
                    tfidf_score    = round(tf_s, 6),
                    textrank_score = round(tr_s, 6),
                    frequency      = processed.token_freq.get(word, 1),
                ))

            if save_to_db and keywords:
                self._clear_keywords(doc_id)
                db.save_keywords(keywords)

            from core.tfidf_engine import TFIDFResult
            results.append(ExtractionResult(
                doc_id          = doc_id,
                keywords        = keywords,
                tfidf_result    = TFIDFResult(
                    keywords=[w for w,_,_ in combined],
                    scores=[self.tfidf_weight*tf+self.tr_weight*tr for _,tf,tr in combined],
                    vocab=self._tfidf_engine.get_feature_names(),
                ),
                textrank_result = tr_result,
                top_sentences   = tr_result.top_sentences(5),
                language        = processed.language,
            ))

        logger.info("다중 문서 추출 완료: %d개", len(results))
        return results

    # ── 헬퍼 ─────────────────────────────────
    @staticmethod
    def _clear_keywords(doc_id: int):
        """기존 자동 추출 키워드를 삭제한다 (수동 추가 키워드는 보존)."""
        from database.db_manager import get_connection
        with get_connection() as conn:
            conn.execute(
                "DELETE FROM keywords WHERE document_id=? AND is_user_added=0",
                (doc_id,),
            )


# ──────────────────────────────────────────────
# 파이프라인 연동 워커 업데이트
# ──────────────────────────────────────────────

class ExtractionWorker:
    """
    AnalysisTab의 '분석 실행' 버튼과 연결되는 동기 추출기 래퍼.
    QThread 기반 AnalysisWorker 완료 후 호출됨.
    """

    def __init__(self, extractor: Optional[ConceptExtractor] = None):
        self._extractor = extractor or ConceptExtractor()

    def run(self, processed: ProcessedText, doc_id: int) -> ExtractionResult:
        return self._extractor.extract(processed, doc_id, save_to_db=True)


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def extract_concepts(
    processed: ProcessedText,
    doc_id:    int,
    max_kw:    int = 50,
) -> ExtractionResult:
    """단일 문서의 핵심 개념을 추출하고 DB에 저장한다."""
    extractor = ConceptExtractor(max_keywords=max_kw)
    return extractor.extract(processed, doc_id, save_to_db=True)


def get_missing_concepts(
    source_keywords: list[str],
    target_tokens:   list[str],
) -> list[str]:
    """
    소스(PDF) 키워드 중 대상(필기) 텍스트에 없는 누락 개념 목록.
    이해도 측정의 gap_detector와 연동.
    """
    coverage = compute_coverage(source_keywords, target_tokens)
    return coverage["missing"]
