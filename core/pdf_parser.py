"""
core/pdf_parser.py
pymupdf(fitz) 기반 PDF 텍스트 추출 및 챕터 분리
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import fitz  # pymupdf

from utils.logger import get_logger

logger = get_logger(__name__)

# ── 챕터 감지 정규식 ─────────────────────────────────────
# 한국어: "제1장", "1장", "Chapter 1", "1.", "1.1" 등
_CH_PATTERNS = [
    re.compile(r"^제\s*(\d+)\s*장"),                        # 제1장
    re.compile(r"^(\d+)\s*장\b"),                           # 1장
    re.compile(r"^chapter\s+(\d+)", re.IGNORECASE),         # Chapter 1
    re.compile(r"^(\d+)\.\s+[A-Za-z가-힣]"),               # 1. 제목
    re.compile(r"^(\d+\.\d+)\s+[A-Za-z가-힣]"),            # 1.1 소제목
    re.compile(r"^[IVX]+\.\s+[A-Za-z가-힣]"),              # I. 로마자
]

# ── 노이즈 패턴 ─────────────────────────────────────────
_NOISE = re.compile(
    r"(\f|\x0c)"                          # 폼피드
    r"|^\s*\d+\s*$"                       # 페이지 번호만 있는 줄
    r"|^\s*[-–—]{3,}\s*$"                # 구분선
, re.MULTILINE)

_WHITESPACE = re.compile(r"[ \t]+")
_MULTI_NL   = re.compile(r"\n{3,}")


# ──────────────────────────────────────────────
# 데이터 클래스
# ──────────────────────────────────────────────

@dataclass
class PageBlock:
    """PDF 한 페이지에서 추출된 텍스트 블록."""
    page_num:   int
    text:       str
    font_sizes: list[float] = field(default_factory=list)   # 블록 내 폰트 크기 목록
    is_heading: bool = False


@dataclass
class Chapter:
    """챕터 단위 텍스트."""
    title:      str
    start_page: int
    end_page:   int
    text:       str
    blocks:     list[PageBlock] = field(default_factory=list)

    @property
    def char_count(self) -> int:
        return len(self.text)


@dataclass
class ParsedDocument:
    """PDF 전체 파싱 결과."""
    title:      str
    author:     str
    page_count: int
    full_text:  str
    chapters:   list[Chapter]
    metadata:   dict

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    @property
    def char_count(self) -> int:
        return len(self.full_text)


# ──────────────────────────────────────────────
# PDF 파서
# ──────────────────────────────────────────────

class PDFParser:
    """
    pymupdf 기반 PDF 파서.

    사용법:
        parser = PDFParser("lecture.pdf")
        doc = parser.parse()
        print(doc.full_text[:500])
        for ch in doc.chapters:
            print(ch.title, ch.char_count)
    """

    def __init__(self, path: str | Path, progress_cb=None):
        """
        Args:
            path:        PDF 파일 경로
            progress_cb: 진행률 콜백 (0~100 int를 받는 callable)
        """
        self.path        = Path(path)
        self.progress_cb = progress_cb
        self._doc: Optional[fitz.Document] = None
        self._table_pages: set[int] = set()   # 패턴D 표가 감지된 페이지 번호

    # ── 공개 메서드 ─────────────────────────
    def parse(self) -> ParsedDocument:
        """PDF를 파싱하여 ParsedDocument를 반환한다."""
        if not self.path.exists():
            raise FileNotFoundError(f"PDF 파일 없음: {self.path}")

        logger.info("PDF 파싱 시작: %s", self.path.name)
        self._doc = fitz.open(str(self.path))

        try:
            meta     = self._extract_metadata()
            blocks   = self._extract_blocks()
            chapters = self._split_chapters(blocks)

            # 표 문장 추출 (패턴D 감지 시 _table_pages 채워짐)
            self._table_pages = set()
            table_sents = self._extract_table_sentences()

            # 패턴D 표 페이지의 blob 텍스트는 제외하고 full_text 빌드
            if self._table_pages:
                clean_blocks = [b for b in blocks if b.page_num not in self._table_pages]
                full_text = self._build_full_text(clean_blocks)
                logger.debug("표 blob 제외 페이지: %s", sorted(self._table_pages))
            else:
                full_text = self._build_full_text(blocks)

            if table_sents:
                full_text = full_text + "\n\n" + "\n".join(table_sents)

            result = ParsedDocument(
                title      = meta.get("title") or self.path.stem,
                author     = meta.get("author", ""),
                page_count = self._doc.page_count,
                full_text  = full_text,
                chapters   = chapters,
                metadata   = meta,
            )
            logger.info(
                "PDF 파싱 완료: %d페이지  %d자  챕터 %d개",
                result.page_count, result.char_count, result.chapter_count,
            )
            return result
        finally:
            self._doc.close()
            self._doc = None

    def extract_text_only(self) -> str:
        """전체 텍스트만 빠르게 추출한다 (챕터 분리 없음)."""
        doc = fitz.open(str(self.path))
        try:
            pages = []
            total = doc.page_count
            for i, page in enumerate(doc):
                pages.append(page.get_text("text"))
                if self.progress_cb:
                    self.progress_cb(int((i + 1) / total * 100))
            raw = "\n".join(pages)
            return self._clean_text(raw)
        finally:
            doc.close()

    # ── 메타데이터 ───────────────────────────
    def _extract_metadata(self) -> dict:
        meta = self._doc.metadata or {}
        return {
            "title":    meta.get("title", ""),
            "author":   meta.get("author", ""),
            "subject":  meta.get("subject", ""),
            "keywords": meta.get("keywords", ""),
            "creator":  meta.get("creator", ""),
        }

    # ── 페이지별 블록 추출 ──────────────────
    def _extract_blocks(self) -> list[PageBlock]:
        """각 페이지에서 텍스트 블록과 폰트 크기를 추출한다."""
        blocks: list[PageBlock] = []
        total = self._doc.page_count

        for page_num, page in enumerate(self._doc):
            block_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
            page_text_parts: list[str] = []
            font_sizes: list[float]    = []

            for block in block_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        txt = span.get("text", "").strip()
                        if txt:
                            page_text_parts.append(txt)
                            font_sizes.append(span.get("size", 12.0))

            raw_text  = " ".join(page_text_parts)
            clean     = self._clean_text(raw_text)
            is_heading = self._is_heading_block(clean, font_sizes)

            if clean:
                blocks.append(PageBlock(
                    page_num   = page_num + 1,
                    text       = clean,
                    font_sizes = font_sizes,
                    is_heading = is_heading,
                ))

            if self.progress_cb:
                self.progress_cb(int((page_num + 1) / total * 90))

        return blocks

    def _extract_table_sentences(self) -> list[str]:
        """
        sort=True 모드로 표 구조를 인식하여 자연어 문장을 생성한다.

        지원 패턴:
          A: [한국어, 영문, 한국어정의] → "한국어(영문)은 정의이다."
             예: "응집력 Cohesion 모듈내요소들의연관성"
             → "응집력(Cohesion)은 모듈내요소들의연관성이다."
          B: [한국어, 한국어정의, ...]  → "한국어는 정의이다."
          C: [숫자, 영문명, 한국어설명] → "영문명은 한국어설명이다."

        필터:
          - 코드 패턴(괄호+점, ={, (), new 등) 포함 행 제외
          - 약한 일반 명사 주어 제외
          - 정의부 최소 8자
        """
        import re as _re
        results: list[str] = []

        # 맥락 없이 사용되면 불명확한 속성 행 주어
        _WEAK = {
            # 일반 속성 명칭
            "정의", "효과", "항목", "내용", "설명", "방법", "특징", "종류",
            "원칙", "비유", "중요성", "이점", "구현", "예시", "기준", "이름",
            "범위", "번호", "평가", "강도", "이유", "목적", "핵심", "장점",
            # 모듈 품질 속성 (어느 개념인지 불명확)
            "독립성", "명확성", "보안성", "확장성", "유연성", "재사용성",
            # 모듈 크기/설계 지표 (단독으로는 의미 없음)
            "개발인력", "개발기간", "함수개수", "라인수", "순환복잡도",
            "병렬개발", "유지보수", "테스트",
            # 기타
            "기호", "코드", "방향", "지표",
        }

        # 코드 패턴 감지
        _CODE_PAT = _re.compile(
            r'new\s+\w|[{};]|class|void|return'
            r'|=\s*\w+\(|\.connect\(|//'
        )

        def _josa(word: str) -> str:
            if not word: return "은"
            code = ord(word[-1]) - 0xAC00
            if code < 0: return "은"
            return "은" if (code % 28) > 0 else "는"

        def _has_code(text: str) -> bool:
            return bool(_CODE_PAT.search(text))

        def _clean_def(text: str) -> str:
            """정의 텍스트에서 불필요한 마커 제거."""
            return _re.sub(r"^[-=→:•\.\s]+", "", text).strip()

        # 헤더 행 판별: 공백 없는 짧은 한국어 단일 어절 (2~8자)
        def _is_header_row(cols: list[str]) -> bool:
            if not (2 <= len(cols) <= 6):
                return False
            for c in cols:
                if ' ' in c:                              # 단일 어절이어야 함
                    return False
                if not (2 <= len(c) <= 10):              # /포함 시 약간 길어질 수 있음
                    return False
                # 한글 + '/' 허용 ("정답/힌트", "문제/내용" 등)
                if not _re.match(r'^[\uAC00-\uD7A3/]+$', c):
                    return False
                # 최소 한글 2자 이상 포함
                if len(_re.findall(r'[\uAC00-\uD7A3]', c)) < 2:
                    return False
            return True

        # 섹션 제목 행에서 핵심 개념어 추출
        # "1. 응집력(Cohesion)"      → "응집력"      (단일 개념어)
        # "응집력의 정의 및 중요성"   → "응집력"      (소유격 구조 → 첫 개념어)
        # "모듈 크기 결정"           → "모듈크기결정" (나열형 → 전체 합치기)
        def _extract_section_word(line: str) -> str | None:
            s = _re.sub(r'^\s*\d+[\.\)]\s+', '', line.strip())   # 번호 제거
            s = _re.sub(r'\([A-Za-z][\w\s,]*\)', '', s).strip()  # (영문) 제거
            # 한국어+숫자 복합 토큰 포함 (예: '5가지')
            words = [w for w in _re.findall(r'[\uAC00-\uD7A3\d]+', s)
                     if len(w) >= 2 and _re.search(r'[\uAC00-\uD7A3]', w)]
            if not words:
                return None
            # 모든 단어 합치기 (최대 12자)
            joined = ''.join(words)
            return joined[:12]

        current_section: str | None = None   # 섹션 제목 — 페이지 넘김에도 유지

        for page in self._doc:
            lines = page.get_text("text", sort=True).split("\n")
            current_headers: list[str] | None = None   # 페이지별 헤더 추적
            page_has_d = False   # 이 페이지에서 패턴D/E 감지 여부
            last_d_idx = -1      # results에서 마지막 D/E 문장 인덱스 (continuation용)
            last_d_cols: list[str] | None = None  # 마지막 D행의 컬럼값 (줄바꿈 병합용)

            for line in lines:
                line_stripped = line.strip()
                if not line_stripped:
                    last_d_idx = -1   # 빈 줄 → continuation 컨텍스트 종료
                    last_d_cols = None
                    continue

                # 다중 공백으로 컬럼 분리
                cols = [c.strip() for c in _re.split(r"  +", line_stripped) if c.strip()]

                # ── 단일 공백 헤더 행 보완 감지 ──────────────────
                # PDF 폰트 특성상 컬럼 구분이 단일 공백일 때:
                # "등급 이름 설명 예시 평가" → 1컬럼으로 오인 → 단어 분리 재시도
                if len(cols) == 1 and len(line_stripped) <= 50:
                    single_split = [c.strip() for c in line_stripped.split(" ") if c.strip()]
                    if 2 <= len(single_split) <= 6 and _is_header_row(single_split):
                        cols = single_split

                # ── 연속 행(continuation) 처리 ────────────────────
                # 직전이 D/E 행이고 현재가 짧은 단일 조각 → col2에 병합
                if (len(cols) == 1
                        and last_d_idx >= 0
                        and last_d_idx == len(results) - 1
                        and 1 <= len(line_stripped) <= 25):
                    if (last_d_cols is not None
                            and current_headers is not None
                            and len(last_d_cols) > 2):
                        # col2(설명 컬럼)에 이어붙임
                        last_d_cols[2] = last_d_cols[2] + line_stripped
                        parts = [f"{current_headers[i]}:{last_d_cols[i]}"
                                 for i in range(len(last_d_cols))]
                        base = ", ".join(parts)
                        sentence = f"{current_section} {base}" if current_section else base
                        if len(sentence) <= 300:
                            results[last_d_idx] = sentence
                    else:
                        # 헤더 없는 경우 기존 방식
                        results[last_d_idx] = results[last_d_idx] + " " + line_stripped
                    continue

                # ── 단일 컬럼 행: 섹션 제목 후보 ─────────────────
                if len(cols) == 1 and 4 <= len(line_stripped) <= 50:
                    # 문장형 제외 (~이다, ~하다 등)
                    if not _re.search(r'(이다|하다|있다|없다|된다|한다)[.\s]*$', line_stripped):
                        word = _extract_section_word(line_stripped)
                        if word:
                            current_section = word

                if len(cols) < 2:
                    continue

                # 코드 포함 행 전체 제외
                if any(_has_code(c) for c in cols):
                    current_headers = None
                    continue

                subject = cols[0]

                # ── 다중 컬럼 줄바꿈 연속 행 (헤더 탐지보다 먼저!) ──────────
                # "기능을수행  변환" → _is_header_row가 가로채기 전에 처리
                # 조건: 이전 D행 있음, 현재 행이 헤더보다 컬럼 수 적음,
                #       첫 컬럼이 숫자·영문 아님, 모두 한국어
                if (len(cols) >= 2
                        and last_d_idx >= 0
                        and last_d_idx == len(results) - 1
                        and current_headers is not None
                        and len(cols) < len(current_headers)
                        and not _re.match(r'^\d+$', cols[0])
                        and not _re.match(r'^[A-Za-z]', cols[0])
                        and last_d_cols is not None
                        and all(_re.search(r'[\uAC00-\uD7A3]', c) for c in cols)):
                    # col2(설명)부터 순서대로 병합
                    start_col = 2
                    for i, cont in enumerate(cols):
                        col_idx = start_col + i
                        if col_idx < len(last_d_cols):
                            last_d_cols[col_idx] = last_d_cols[col_idx] + cont
                    parts = [f"{current_headers[i]}:{last_d_cols[i]}"
                             for i in range(len(last_d_cols))]
                    base = ", ".join(parts)
                    sentence = f"{current_section} {base}" if current_section else base
                    if len(sentence) <= 300:
                        results[last_d_idx] = sentence
                    continue   # current_headers 유지, 헤더 탐지 건너뜀

                # ── 패턴 D/E: 헤더 행 탐지 ──────────────────
                if _is_header_row(cols):
                    current_headers = cols
                    last_d_idx = -1   # 헤더 감지 시 continuation 리셋
                    continue

                # ── 패턴 E: 2컬럼 표 → "섹션 속성:내용" ──────
                if (current_headers
                        and len(current_headers) == 2
                        and len(cols) == 2):
                    label, content = cols[0], cols[1]
                    if len(label) >= 2 and len(content) >= 1:
                        if current_section:
                            sentence = f"{current_section} {label}:{content}"
                        else:
                            sentence = f"{label}:{content}"
                        if 10 <= len(sentence) <= 300:
                            results.append(sentence)
                            last_d_idx = len(results) - 1
                            page_has_d = True
                    continue

                # ── 패턴 D: 3+ 컬럼 표 → "[섹션 ]헤더:값, ..." ──────
                if current_headers and len(cols) == len(current_headers):
                    if all(c and len(c) >= 1 for c in cols):
                        parts = [f"{h}:{v}" for h, v in zip(current_headers, cols)]
                        base = ", ".join(parts)
                        sentence = f"{current_section} {base}" if current_section else base
                        if 20 <= len(sentence) <= 300:
                            results.append(sentence)
                            last_d_idx = len(results) - 1
                            last_d_cols = list(cols)   # 줄바꿈 병합용 저장
                            page_has_d = True
                    continue

                # ── 컬럼 수 불일치: 헤더 유지하면서 가능한 컬럼만 Pattern D 형식 출력 ──
                if current_headers and len(cols) != len(current_headers):
                    # 숫자+영문명 구조이면 → 있는 컬럼까지 Pattern D 형식
                    if (2 <= len(cols) <= len(current_headers)
                            and _re.match(r"^\d+$", cols[0])
                            and len(cols) >= 2
                            and _re.match(r"^[A-Za-z]{3,}", cols[1])):
                        avail = len(cols)
                        parts = [f"{current_headers[i]}:{cols[i]}" for i in range(avail)]
                        base = ", ".join(parts)
                        sentence = f"{current_section} {base}" if current_section else base
                        if 20 <= len(sentence) <= 300:
                            results.append(sentence)
                            last_d_idx = len(results) - 1
                            page_has_d = True
                        continue   # 헤더는 리셋하지 않고 유지
                    # 그 외(헤더 없는 잡문)는 리셋
                    else:
                        current_headers = None
                        last_d_idx = -1

                # ── 패턴 A: [한국어, 영문, 한국어정의] ──
                if (_re.match(r"^[\uAC00-\uD7A3]{2,6}$", subject)
                        and subject not in _WEAK
                        and len(cols) >= 3
                        and _re.match(r"^[A-Za-z][\w\s]+$", cols[1])):
                    eng = cols[1].strip()
                    defn = _clean_def(cols[2])
                    if (len(defn) >= 6
                            and _re.search(r"[\uAC00-\uD7A3]{2}", defn)
                            and not _has_code(defn)):
                        s = f"{subject}({eng}){_josa(subject)} {defn}이다."
                        if 20 <= len(s) <= 120:
                            results.append(s)
                        continue

                # ── 패턴 B: [한국어, 한국어정의] ──
                if (_re.match(r"^[\uAC00-\uD7A3]{2,6}$", subject)
                        and subject not in _WEAK):
                    defn = _clean_def(" ".join(cols[1:3]))
                    if (len(defn) >= 8
                            and _re.search(r"[\uAC00-\uD7A3]{3}", defn)
                            and not _has_code(defn)):
                        s = f"{subject}{_josa(subject)} {defn}이다."
                        if 20 <= len(s) <= 120:
                            results.append(s)

                # ── 패턴 C: [숫자, 영문명, 한국어설명+나머지] ──
                elif (_re.match(r"^\d+$", subject)
                        and len(cols) >= 3
                        and _re.match(r"^[A-Za-z]{4,20}$", cols[1])):
                    # current_headers가 있으면 Pattern D 형식으로 통일
                    if current_headers and 2 <= len(cols) <= len(current_headers):
                        avail = min(len(cols), len(current_headers))
                        parts = [
                            f"{current_headers[i]}:{cols[i]}"
                            for i in range(avail)
                        ]
                        base = ", ".join(parts)
                        s = f"{current_section} {base}" if current_section else base
                        if 20 <= len(s) <= 300:
                            results.append(s)
                            last_d_idx = len(results) - 1
                            page_has_d = True
                    else:
                        # 헤더 컨텍스트 없음 → 컬럼 수에 따라 형식 결정
                        if len(cols) >= 5:
                            # 5컬럼: [번호, 영문명, 설명, 예시, 평가] 형태
                            desc  = _clean_def(cols[2])
                            ex    = _clean_def(cols[3]) if len(cols) > 3 else ""
                            grade = _clean_def(cols[4]) if len(cols) > 4 else ""
                            parts = [p for p in [desc, ex, grade] if p and len(p) >= 2]
                            defn  = ". ".join(parts)
                        else:
                            defn = _clean_def(" ".join(cols[2:]))
                        if (len(defn) >= 8
                                and _re.search(r"[\uAC00-\uD7A3]{3}", defn)
                                and not _has_code(defn)):
                            s = f"{cols[1]}({subject}등급): {defn}"
                            if 20 <= len(s) <= 300:
                                results.append(s)

            # 이 페이지에서 패턴D/E가 사용됐으면 페이지 번호 기록
            if page_has_d:
                self._table_pages.add(page.number + 1)   # fitz는 0-indexed

        # 중복 제거
        seen, unique = set(), []
        for s in results:
            k = s[:50]
            if k not in seen:
                seen.add(k); unique.append(s)

        logger.debug("표 문장 생성: %d개", len(unique))
        return unique

    # ── 챕터 분리 ────────────────────────────
    def _split_chapters(self, blocks: list[PageBlock]) -> list[Chapter]:
        """
        챕터 헤딩을 기준으로 블록을 챕터 단위로 묶는다.
        헤딩이 없으면 전체를 단일 챕터로 반환한다.
        """
        chapters: list[Chapter] = []
        current_title = "서론"
        current_start = 1
        current_blocks: list[PageBlock] = []

        for block in blocks:
            heading = self._detect_chapter_title(block)
            if heading and current_blocks:
                # 이전 챕터 저장
                chapters.append(self._make_chapter(
                    current_title, current_start,
                    current_blocks[-1].page_num, current_blocks
                ))
                current_title  = heading
                current_start  = block.page_num
                current_blocks = [block]
            else:
                current_blocks.append(block)

        # 마지막 챕터
        if current_blocks:
            chapters.append(self._make_chapter(
                current_title, current_start,
                current_blocks[-1].page_num, current_blocks
            ))

        if self.progress_cb:
            self.progress_cb(100)

        # 챕터가 하나도 감지되지 않으면 전체를 단일 챕터로
        if not chapters:
            full = " ".join(b.text for b in blocks)
            chapters = [Chapter(
                title="전체", start_page=1,
                end_page=blocks[-1].page_num if blocks else 1,
                text=full, blocks=blocks,
            )]

        logger.debug("챕터 %d개 감지", len(chapters))
        return chapters

    def _make_chapter(
        self,
        title: str,
        start: int,
        end: int,
        blocks: list[PageBlock],
    ) -> Chapter:
        text = "\n\n".join(b.text for b in blocks)
        return Chapter(title=title, start_page=start, end_page=end,
                       text=text, blocks=list(blocks))

    # ── 전체 텍스트 빌드 ─────────────────────
    def _build_full_text(self, blocks: list[PageBlock]) -> str:
        return "\n\n".join(b.text for b in blocks)

    # ── 헬퍼 ─────────────────────────────────
    def _clean_text(self, text: str) -> str:
        """노이즈 제거 및 공백 정규화."""
        text = _NOISE.sub(" ", text)
        text = _WHITESPACE.sub(" ", text)
        text = _MULTI_NL.sub("\n\n", text)
        # 하이픈 줄바꿈 복원 (단어 연결)
        text = re.sub(r"-\n(\S)", r"\1", text)
        return text.strip()

    def _is_heading_block(
        self, text: str, font_sizes: list[float]
    ) -> bool:
        """블록이 제목/소제목인지 폰트 크기로 판별한다."""
        if not font_sizes or not text:
            return False
        avg_size = sum(font_sizes) / len(font_sizes)
        # 평균 폰트 크기가 14pt 이상이면 제목으로 간주
        return avg_size >= 14.0

    def _detect_chapter_title(self, block: PageBlock) -> Optional[str]:
        """블록의 첫 줄이 챕터 제목 패턴이면 제목 문자열 반환."""
        first_line = block.text.split("\n")[0].strip()
        if len(first_line) > 80:   # 너무 긴 줄은 제목이 아님
            return None
        for pat in _CH_PATTERNS:
            if pat.match(first_line):
                return first_line
        # 폰트 크기 기반 제목 감지 (짧은 텍스트 + 큰 폰트)
        if block.is_heading and len(first_line) <= 50:
            return first_line
        return None


# ──────────────────────────────────────────────
# 편의 함수
# ──────────────────────────────────────────────

def parse_pdf(path: str | Path, progress_cb=None) -> ParsedDocument:
    """PDF 파일을 파싱하여 ParsedDocument를 반환한다."""
    return PDFParser(path, progress_cb).parse()


def extract_text_fast(path: str | Path, progress_cb=None) -> str:
    """PDF에서 텍스트만 빠르게 추출한다."""
    return PDFParser(path, progress_cb).extract_text_only()


def validate_pdf(path: str | Path) -> tuple[bool, str]:
    """
    PDF 파일의 유효성을 검사한다.

    Returns:
        (valid: bool, message: str)
    """
    p = Path(path)
    try:
        with open(p, "rb") as f:
            header = f.read(5)
        if header != b"%PDF-":
            return False, "PDF 헤더가 올바르지 않습니다."
        doc = fitz.open(str(p))
        pages = doc.page_count
        doc.close()
        if pages == 0:
            return False, "페이지가 없는 PDF입니다."
        return True, f"유효한 PDF ({pages}페이지)"
    except fitz.FileDataError:
        return False, "손상된 PDF 파일입니다."
    except Exception as e:
        return False, f"파일 오류: {e}"
