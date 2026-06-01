"""
core/text_processor.py
한국어·영어 텍스트 전처리 파이프라인
외부 형태소 분석기 없이 정규식 + 불용어 사전으로 구현
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

from utils.logger import get_logger
from utils.stopwords_ko import filter_tokens, get_stopwords, STOPWORDS_KO, STOPWORDS_EN

logger = get_logger(__name__)

# ──────────────────────────────────────────────
# 정규식 상수
# ──────────────────────────────────────────────

# 한국어 음절 범위: AC00-D7A3
_KO_CHAR   = re.compile(r"[\uAC00-\uD7A3]")
_EN_CHAR   = re.compile(r"[A-Za-z]")

# 문장 분리 (한국어·영어 혼합)
_SENT_SPLIT = re.compile(
    r"(?<=[^0-9][.!?])\s+"                 # 영어/한글 문장 끝 (숫자 뒤 . 제외)
    r"|(?<=다\.)\s+"                         # ~다.
    r"|(?<=요\.)\s+"                         # ~요.
    r"|(?<=죠\.)\s+"                         # ~죠.
    r"|(?<=니다\.)\s+"                       # ~니다.
    r"|(?<=습니다\.)\s+"                     # ~습니다.
    r"|(?<=았다\.)\s+"                       # ~았다.
    r"|(?<=었다\.)\s+"                       # ~었다.
    r"|(?<=겠다\.)\s+"                       # ~겠다.
)

# 번호 목록 항목 경계 (마침표 없는 형태): "~다 2. "
_NUM_BOUNDARY = re.compile(
    r"(?<=다)\s+(?=\d{1,2}[\.\)]\s*[\uAC00-\uD7A3A-Z])"
)

# 마침표 없는 한국어 문장 경계: "~있다 자료사전", "~이해한다 UML" 등
# 긴 문단에서만 적용 (짧은 절은 분리 안 함)
_KO_SENT_BOUND = re.compile(
    r"(?<=다)\s+(?=[\uAC00-\uD7A3A-Z\(])"
)

# 섹션 내 속성 레이블 앞 분리
# "① 외부실체 - 정의: ... - 기호: ... - 예: ..." → 개별 조각
# "DFD 정의: 내용 왜 필요한가? 내용 실무 예시: 내용" → 3개 조각
_PROP_SPLIT = re.compile(
    r"\s+(?="
    r"정\s*의:|왜\s+필요|실무\s+예시:|특\s*징:|목적:|배경:|개요:|효과:|원칙:|구성\s+요소:"
    r"|종류:|방법:|단계:|기\s*능:|역할:|적용:|의미:"
    r"|기\s*호:|표\s*기:|속\s*성:|주\s*의:|예\s*:"
    r")"
)


def _split_with_title_prefix(para: str) -> list[str]:
    """
    "섹션제목 정의: 내용 왜 필요한가? 내용 실무 예시: 내용" 형태 또는
    "① 외부 실체 - 정의: ... - 기호: ... - 예: ..." 형태를
    섹션 제목을 앞에 붙인 개별 문장으로 분리한다.
    """
    # "- 정의:" 형태를 "정의:"로 정규화 → 이중 split 충돌 방지
    _DASH_LABEL = re.compile(
        r'\s*-\s*(정\s*의:|기\s*호:|표\s*기:|속\s*성:|주\s*의:|특\s*징:|예\s*:'
        r'|실무\s+예시:|왜\s+필요)'
    )
    normalized = _DASH_LABEL.sub(r' \1', para)

    parts = _PROP_SPLIT.split(normalized)
    if len(parts) <= 1:
        return [para]

    first = parts[0].strip()
    title_m = re.match(
        r'^(.+?)\s+(?:-\s*)?(정의:|왜\s+필요|실무\s+예시:|특징:|목적:|배경:|개요:|기호:|표기:|속성:|주의:)',
        first
    )
    if title_m:
        section_title = title_m.group(1).strip()
        results = [first]
    else:
        section_title = first
        results = []

    for part in parts[1:]:
        part = re.sub(r'^-\s*', '', part.strip()).strip()
        if part and len(part) >= 10:
            results.append(f"{section_title} {part}")

    return [r for r in results if len(r) >= 15]

# 한국어 토큰: 2글자 이상 한글 연속
_KO_TOKEN = re.compile(r"[\uAC00-\uD7A3]{2,}")

# 영어 토큰: 알파벳 2글자 이상
_EN_TOKEN = re.compile(r"[A-Za-z]{2,}")

# 숫자+단위 (의미 있는 수식 표현)
_NUM_UNIT = re.compile(r"\d+(?:\.\d+)?[%개건명억만원kg℃]+")

# 특수문자·제어문자 제거
_SPECIAL = re.compile(r"[^\uAC00-\uD7A3A-Za-z0-9\s.,!?;:()\-①②③④⑤⑥⑦⑧⑨⑩]")

# 반복 공백 (탭·스페이스만 — 줄바꿈은 보존)
_SPACES = re.compile(r"[ \t]+")


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class ProcessedText:
    """전처리 결과물."""
    original:   str
    normalized: str                          # 정규화된 전체 텍스트
    sentences:  list[str]                    # 문장 목록
    tokens:     list[str]                    # 토큰(단어) 목록 (불용어 제외)
    bigrams:    list[str]                    # 바이그램 목록
    language:   str                          # 감지된 주요 언어 ("ko"/"en"/"mixed")
    token_freq: dict[str, int] = field(default_factory=dict)  # 단어 빈도

    @property
    def token_count(self) -> int:
        return len(self.tokens)

    @property
    def sentence_count(self) -> int:
        return len(self.sentences)

    @property
    def unique_token_count(self) -> int:
        return len(set(self.tokens))


# ──────────────────────────────────────────────
# 텍스트 프로세서
# ──────────────────────────────────────────────

class TextProcessor:
    """
    한국어·영어 혼합 텍스트 전처리기.

    파이프라인:
        1. 유니코드 정규화
        2. 특수문자 제거
        3. 언어 감지
        4. 문장 분리
        5. 토큰화 (한글 / 영어)
        6. 불용어 제거
        7. 바이그램 생성
        8. 빈도 계산
    """

    def __init__(self, min_token_len: int = 2, use_bigrams: bool = True):
        self.min_token_len = min_token_len
        self.use_bigrams   = use_bigrams

    # ── 공개 메서드 ─────────────────────────
    def process(self, text: str, lang: Optional[str] = None) -> ProcessedText:
        """
        텍스트를 전처리하여 ProcessedText를 반환한다.

        Args:
            text: 원본 텍스트
            lang: 언어 코드 ('ko'/'en'/'all'). None이면 자동 감지
        """
        if not text or not text.strip():
            return self._empty_result(text or "")

        normalized  = self.normalize(text)
        detected    = lang or self.detect_language(normalized)
        sentences   = self.split_sentences(normalized)
        tokens      = self.tokenize(normalized, detected)
        bigrams     = self.make_bigrams(tokens) if self.use_bigrams else []
        freq        = self._calc_freq(tokens)

        result = ProcessedText(
            original   = text,
            normalized = normalized,
            sentences  = sentences,
            tokens     = tokens,
            bigrams    = bigrams,
            language   = detected,
            token_freq = freq,
        )
        logger.debug(
            "전처리 완료: %d자 → 문장 %d개  토큰 %d개  언어=%s",
            len(text), result.sentence_count, result.token_count, detected,
        )
        return result

    # ── 유니코드 정규화 ─────────────────────
    def normalize(self, text: str) -> str:
        """텍스트를 정규화한다."""
        # NFC 정규화 (한글 조합형 통일)
        text = unicodedata.normalize("NFC", text)
        # 전각 문자 → 반각
        text = self._fullwidth_to_halfwidth(text)
        # 특수문자 제거 (의미 있는 문장부호 유지)
        text = _SPECIAL.sub(" ", text)
        # 반복 공백 제거
        text = _SPACES.sub(" ", text)
        return text.strip()

    # ── 언어 감지 ───────────────────────────
    def detect_language(self, text: str) -> str:
        """
        텍스트의 주요 언어를 감지한다.

        Returns:
            "ko" / "en" / "mixed"
        """
        ko_count = len(_KO_CHAR.findall(text))
        en_count = len(_EN_CHAR.findall(text))
        total    = ko_count + en_count
        if total == 0:
            return "ko"

        ko_ratio = ko_count / total
        if ko_ratio >= 0.7:
            return "ko"
        if ko_ratio <= 0.3:
            return "en"
        return "mixed"

    # ── 문장 분리 ───────────────────────────
    def split_sentences(self, text: str) -> list[str]:
        """
        텍스트를 문장 단위로 분리한다.
        한국어·영어 혼합 텍스트 처리.

        구조 마커 인식:
            ①②③...  원문자 번호
            1) 2) 3) 괄호 번호
            (1) (2)  괄호 번호
        """
        import re as _re

        # ── 0. 구조 마커 앞에 줄바꿈 삽입 ──────────────────
        # 원문자 번호 ①②③④⑤⑥⑦⑧⑨⑩
        text = _re.sub(r'([①②③④⑤⑥⑦⑧⑨⑩])', r'\n\1', text)
        # (1) (2) 형태 — 소괄호 숫자
        text = _re.sub(r'(\(\d{1,2}\)\s)', r'\n\1', text)
        # 1) 2) 형태 — 숫자+닫는괄호 (단어 안의 숫자 제외)
        text = _re.sub(r'(?<![\w가-힣])(\d{1,2}\)\s)', r'\n\1', text)
        # N-N. / N.N. 섹션 번호: "1-1. DFD의..." "4-2. 행위..." 앞에 줄바꿈
        # (하이픈 포함 형태만 처리 — 단순 "1." 목록 번호와 구분)
        text = _re.sub(r'\s+(\d+[-\.]\d+\.\s+[\uAC00-\uD7A3A-Z])', r'\n\1', text)

        # ── 1. 줄바꿈 기준 1차 분리 ──────────────────────
        paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
        sentences: list[str] = []

        # 섹션 제목 헬퍼 ─────────────────────────────────
        _SECTION_NUM = re.compile(r'^\d[\d\-\.]*[\.\s]+')  # "1-1. " "1. " 등
        _CIRCLED     = re.compile(r'^[①②③④⑤⑥⑦⑧⑨⑩]')

        def _is_section_heading(s: str) -> bool:
            """짧고 콜론 없는 번호 형식 → 섹션 제목 후보"""
            if len(s) > 80 or ':' in s:
                return False
            return bool(_SECTION_NUM.match(s) and
                        re.search(r'[\uAC00-\uD7A3]{2}', s))

        def _extract_section_name(s: str) -> str:
            """번호/기호 제거 후 핵심 제목 반환 (최대 30자)"""
            name = _SECTION_NUM.sub('', s).strip()
            return name[:30] if len(name) > 30 else name

        current_parent: str | None = None  # 현재 상위 섹션 제목

        for para in paragraphs:
            # 섹션 제목 감지 → 상위 제목 갱신
            if _is_section_heading(para):
                current_parent = _extract_section_name(para)

            # 0단계: 섹션 제목 + 속성 레이블 패턴 분리
            # "DFD 정의: ... 왜 필요한가? ..." → ["DFD 정의: ...", "DFD 왜 필요한가? ..."]
            pre_parts = _split_with_title_prefix(para)
            for pre_part in pre_parts:
                pre_part = pre_part.strip()
                if not pre_part:
                    continue
                # ①②③ 시작 문장에 상위 섹션 제목 앞에 붙이기
                if current_parent and _CIRCLED.match(pre_part):
                    pre_part = f"{current_parent} {pre_part}"
                # 1차: 번호 목록 항목 경계 분리 ("~다 2. 다음항목")
                num_parts = _NUM_BOUNDARY.split(pre_part)
                for num_part in num_parts:
                    num_part = num_part.strip()
                    if not num_part:
                        continue
                    # 2차: 마침표 없는 한국어 문장 경계 (긴 단락만)
                    if len(num_part) > 60:
                        ko_parts = _KO_SENT_BOUND.split(num_part)
                    else:
                        ko_parts = [num_part]
                    for ko_part in ko_parts:
                        ko_part = ko_part.strip()
                        if not ko_part:
                            continue
                        # 3차: 문장 패턴으로 분리
                        parts = _SENT_SPLIT.split(ko_part)
                        for part in parts:
                            part = part.strip()
                            if part and len(part) >= 15:
                                sentences.append(part)

        # ── 2. 표 행 → 자연어 문장 변환 ─────────────────
        table_sents = self._table_rows_to_sentences(paragraphs)
        sentences.extend(table_sents)

        # 중복 제거 (순서 유지)
        seen = set()
        unique: list[str] = []
        for s in sentences:
            key = s[:60]
            if key not in seen:
                seen.add(key); unique.append(s)

        return unique


    def _table_rows_to_sentences(self, paragraphs: list[str]) -> list[str]:
        """
        표 형식 행을 자연어 문장으로 변환한다.
        패턴A: "응집력 모듈 내 요소들의 연관성" → "응집력은 모듈 내 요소들의 연관성."
        패턴B: "7 Functional 모든 요소가 하나의 기능" → "Functional은(는) 모든 요소가 하나의 기능."
        패턴C: "정의 모듈 내의 요소들이 ..." → "모듈 내의 요소들이 ..."
        """
        import re as _re
        results: list[str] = []

        def _josa(word: str) -> str:
            if not word: return "은"
            code = ord(word[-1]) - 0xAC00
            if code < 0: return "은"
            return "은" if (code % 28) > 0 else "는"

        # 속성 레이블 단어: 주어로 쓰면 "무엇의 종류인지 알 수 없는" 문장이 됨
        _WEAK_SUBJECTS = {
            "종류", "역할", "유형", "방법", "방식", "예시", "형태",
            "구조", "개념", "의미", "목표", "단계", "절차", "기준",
            "조건", "결과", "항목", "내용", "요소", "성질",
        }

        for para in paragraphs:
            parts = para.strip().split()
            if len(parts) < 3:
                continue
            subject = parts[0]

            # 패턴A: 한국어 2~6글자 개념어 + 정의
            # (속성 레이블 단어는 주어로 사용하지 않음)
            if (_re.match(r"^[\uAC00-\uD7A3]{2,6}$", subject)
                    and subject not in _WEAK_SUBJECTS):
                rest = " ".join(parts[1:])
                if len(rest) >= 8 and _re.search(r"[\uAC00-\uD7A3]{3}", rest):
                    sentence = f"{subject}{_josa(subject)} {rest}."
                    if 20 <= len(sentence) <= 150:
                        results.append(sentence)

            # 패턴B: 숫자 + 영어명 + 한국어 설명
            elif _re.match(r"^\d+$", parts[0]) and len(parts) >= 4:
                eng = parts[1]
                if _re.match(r"^[A-Za-z]{3,20}$", eng):
                    rest = " ".join(parts[2:])
                    if len(rest) >= 8 and _re.search(r"[\uAC00-\uD7A3]{3}", rest):
                        sentence = f"{eng}은(는) {rest}."
                        if 20 <= len(sentence) <= 150:
                            results.append(sentence)

            # 패턴C: 항목어 + 내용 (정의, 특징 등)
            elif subject in ("정의", "특징", "원칙", "효과", "목적", "비유", "핵심", "장점", "이점"):
                rest = " ".join(parts[1:])
                if len(rest) >= 12 and _re.search(r"[\uAC00-\uD7A3]{4}", rest):
                    results.append(rest + ".")

        return results

    # ── 토큰화 ──────────────────────────────
    def tokenize(self, text: str, lang: str = "ko") -> list[str]:
        """
        텍스트를 토큰(단어) 목록으로 변환한다.
        불용어를 제거하고 최소 길이 이상의 토큰만 반환한다.
        """
        tokens: list[str] = []

        # 한국어 토큰
        ko_tokens = [t for t in _KO_TOKEN.findall(text) if len(t) >= self.min_token_len]

        # 영어 토큰
        en_tokens = [t.lower() for t in _EN_TOKEN.findall(text) if len(t) >= self.min_token_len]

        # 언어별 불용어 제거
        from utils.stopwords_ko import _PROG_KEYWORDS
        if lang in ("ko", "mixed"):
            ko_tokens = [t for t in ko_tokens if t not in STOPWORDS_KO]
        # 영어 토큰: 언어 무관 항상 필터 (코드 키워드 제거)
        en_tokens = [t for t in en_tokens
                     if t not in STOPWORDS_EN
                     and t.lower() not in _PROG_KEYWORDS]

        tokens = ko_tokens + en_tokens

        # 숫자+단위 패턴 추가 (예: 100개, 50%, 3.14)
        tokens += _NUM_UNIT.findall(text)

        return tokens

    # ── 바이그램 ────────────────────────────
    def make_bigrams(self, tokens: list[str]) -> list[str]:
        """
        인접 토큰 쌍으로 바이그램을 생성한다.
        예: ['소프트웨어', '공학'] → ['소프트웨어_공학']
        """
        if len(tokens) < 2:
            return []
        return [f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)]

    # ── 빈도 계산 ───────────────────────────
    def _calc_freq(self, tokens: list[str]) -> dict[str, int]:
        freq: dict[str, int] = {}
        for t in tokens:
            freq[t] = freq.get(t, 0) + 1
        return freq

    # ── 챕터 처리 ───────────────────────────
    def process_chapters(
        self, chapters: list, lang: Optional[str] = None
    ) -> list[ProcessedText]:
        """
        챕터 목록(ParsedDocument.chapters)을 순서대로 전처리한다.
        각 챕터별 ProcessedText 리스트를 반환한다.
        """
        results = []
        for i, ch in enumerate(chapters):
            logger.debug("챕터 %d/%d 전처리: %s", i+1, len(chapters), ch.title)
            result = self.process(ch.text, lang)
            results.append(result)
        return results

    # ── 헬퍼 ─────────────────────────────────
    @staticmethod
    def _fullwidth_to_halfwidth(text: str) -> str:
        """전각 문자(ａ-ｚ, ０-９)를 반각으로 변환한다."""
        result = []
        for ch in text:
            code = ord(ch)
            # 전각 알파벳·숫자: FF01~FF5E → 21~7E
            if 0xFF01 <= code <= 0xFF5E:
                result.append(chr(code - 0xFEE0))
            # 전각 공백
            elif code == 0x3000:
                result.append(" ")
            else:
                result.append(ch)
        return "".join(result)

    def _empty_result(self, text: str) -> ProcessedText:
        return ProcessedText(
            original=text, normalized="", sentences=[],
            tokens=[], bigrams=[], language="ko", token_freq={},
        )


# ──────────────────────────────────────────────
# 전처리 파이프라인 (편의 함수)
# ──────────────────────────────────────────────

_default_processor = TextProcessor()


def process_text(text: str, lang: Optional[str] = None) -> ProcessedText:
    """텍스트를 전처리하여 ProcessedText를 반환한다."""
    return _default_processor.process(text, lang)


def tokenize_only(text: str, lang: str = "ko") -> list[str]:
    """토큰 목록만 빠르게 반환한다."""
    normalized = _default_processor.normalize(text)
    return _default_processor.tokenize(normalized, lang)


def split_sentences(text: str) -> list[str]:
    """문장 목록만 반환한다."""
    normalized = _default_processor.normalize(text)
    return _default_processor.split_sentences(normalized)


def detect_language(text: str) -> str:
    """언어 코드를 반환한다."""
    return _default_processor.detect_language(text)


def chunk_text(
    text: str,
    chunk_size: int = 1000,
    overlap: int = 100,
) -> list[str]:
    """
    긴 텍스트를 고정 크기 청크로 분할한다.
    TF-IDF 행렬 구성 시 메모리 절약에 사용.

    Args:
        chunk_size: 청크당 최대 글자 수
        overlap:    앞뒤 청크 중복 글자 수
    """
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks
