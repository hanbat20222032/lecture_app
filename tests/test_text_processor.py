"""
tests/test_text_processor.py
core/text_processor.py 테스트

BUG-01: _WEAK_SUBJECTS 필터 (속성 레이블 주어 제외) 수정 검증
"""
import pytest
import re
from core.text_processor import TextProcessor, ProcessedText, process_text, split_sentences


@pytest.fixture
def processor():
    return TextProcessor()


# ── process() → ProcessedText ─────────────────────────────────
class TestProcess:
    def test_returns_processed_text(self, processor):
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다.")
        assert isinstance(result, ProcessedText)

    def test_has_sentences(self, processor):
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다.")
        assert hasattr(result, 'sentences')
        assert isinstance(result.sentences, list)

    def test_has_tokens(self, processor):
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다.")
        assert hasattr(result, 'tokens')
        assert isinstance(result.tokens, list)

    def test_has_language(self, processor):
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다.")
        assert result.language in ("ko", "en", "mixed")

    def test_empty_text(self, processor):
        result = processor.process("")
        assert isinstance(result, ProcessedText)
        assert result.sentences == [] or result.tokens == []

    def test_token_count_property(self, processor):
        result = processor.process("응집력은 결합력과 함께 소프트웨어 설계의 핵심 원칙이다.")
        assert result.token_count == len(result.tokens)

    def test_sentence_count_property(self, processor):
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도이다.")
        assert result.sentence_count == len(result.sentences)

    def test_stopwords_removed(self, processor):
        """불용어가 토큰에서 제거됨"""
        result = processor.process("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다.")
        assert "은" not in result.tokens
        assert "의" not in result.tokens
        assert "이" not in result.tokens

    def test_prog_keywords_removed(self, processor):
        """BUG-04: 프로그래밍 예약어 토큰 제외"""
        result = processor.process("public void 메소드는 Java에서 캡슐화를 구현한다.")
        assert "public" not in result.tokens
        assert "void" not in result.tokens


# ── split_sentences() ────────────────────────────────────────
class TestSplitSentences:
    def test_newline_split(self, processor):
        """줄바꿈으로 문장 분리"""
        text = "응집력은 모듈 내의 요소들이 밀접하게 연관된 정도이다.\n결합력은 모듈 간의 의존성 정도를 나타낸다."
        sentences = processor.split_sentences(text)
        assert len(sentences) >= 1

    def test_korean_sentence_end_split(self, processor):
        """~다. 패턴으로 문장 분리 (각 문장 15자 이상)"""
        text = ("응집력은 모듈 내의 요소들이 밀접하게 연관된 정도이다. "
                "결합력은 모듈 간의 의존성 정도를 나타내며 낮을수록 좋다.")
        sentences = processor.split_sentences(text)
        assert len(sentences) >= 1

    def test_min_length_filter(self, processor):
        """15자 미만 문장은 제외"""
        text = "예. 응집력은 모듈 내의 요소들이 밀접하게 연관된 정도를 나타낸다."
        sentences = processor.split_sentences(text)
        for s in sentences:
            assert len(s) >= 15, f"15자 미만 문장 포함: '{s}'"

    def test_returns_list(self, processor):
        result = processor.split_sentences("응집력은 모듈 내의 요소들의 연관성 정도이다.")
        assert isinstance(result, list)

    def test_empty_text(self, processor):
        result = processor.split_sentences("")
        assert result == []

    def test_no_duplicate_sentences(self, processor):
        """중복 문장 제거"""
        text = "응집력은 모듈 내의 요소들이 밀접하게 연관된 정도이다.\n응집력은 모듈 내의 요소들이 밀접하게 연관된 정도이다."
        sentences = processor.split_sentences(text)
        assert len(sentences) == len(set(s[:60] for s in sentences))

    def test_module_level_function(self):
        """모듈 레벨 split_sentences 함수"""
        result = split_sentences("응집력은 모듈 내의 요소들의 연관성 정도이다.")
        assert isinstance(result, list)


# ── _table_rows_to_sentences() — BUG-01 _WEAK_SUBJECTS 필터 ──
class TestTableRowsToSentences:
    """BUG-01 수정 검증: 속성 레이블이 주어인 행은 문장 생성 제외"""

    def test_valid_concept_generates_sentence(self, processor):
        """개념어 주어 → 문장 생성"""
        rows = ["응집력 모듈 내의 요소들이 밀접하게 연관된 정도이다"]
        result = processor._table_rows_to_sentences(rows)
        assert len(result) > 0
        assert any("응집력" in s for s in result)

    def test_weak_subject_filtered(self, processor):
        """BUG-01: 속성 레이블 주어 → 문장 생성 제외"""
        weak_rows = [
            "종류 Content Common Control Stamp Data로 나뉜다 독립성",
            "역할 데이터를 저장하고 관리하는 기능을 담당한다 모듈에서",
            "유형 과정 추상화 데이터 추상화 제어 추상화로 구분한다",
            "방법 인터페이스 사용 의존성 주입 이벤트 기반 방식",
            "단계 분석 설계 구현 테스트로 이루어지는 개발 과정이다",
            "조건 모든 요소가 하나의 기능을 수행해야 하는 원칙이다",
            "결과 변경 영향 최소화와 재사용성 증대 효과를 얻는다",
        ]
        result = processor._table_rows_to_sentences(weak_rows)
        weak_subjects = {
            "종류", "역할", "유형", "방법", "방식", "형태",
            "구조", "개념", "의미", "목표", "단계", "절차",
            "기준", "조건", "결과", "항목", "내용", "요소",
        }
        for s in result:
            first_word = s.split()[0].rstrip("은는이가")
            assert first_word not in weak_subjects, \
                f"속성 레이블 주어 문장 생성됨: '{s}'"

    @pytest.mark.parametrize("weak_word", [
        "종류", "역할", "유형", "방법", "단계", "조건", "결과", "요소"
    ])
    def test_individual_weak_words(self, processor, weak_word):
        """개별 속성 레이블 단어 필터 확인"""
        row = f"{weak_word} 관련된 내용으로 세 가지 항목을 포함하는 개념이다 분류된다"
        result = processor._table_rows_to_sentences([row])
        for s in result:
            assert not s.startswith(weak_word), \
                f"'{weak_word}' 시작 문장이 생성됨: '{s}'"

    def test_pattern_b_number_english(self, processor):
        """패턴B: 숫자+영문명+한국어 설명"""
        rows = ["7 Functional 모든 요소가 하나의 기능을 수행하는 응집력 등급"]
        result = processor._table_rows_to_sentences(rows)
        assert len(result) > 0
        assert any("Functional" in s for s in result)

    def test_short_row_skipped(self, processor):
        """3개 미만 단어는 건너뜀"""
        rows = ["응집력 중요"]
        result = processor._table_rows_to_sentences(rows)
        assert result == []

    def test_empty_paragraphs(self, processor):
        result = processor._table_rows_to_sentences([])
        assert result == []


# ── tokenize() ───────────────────────────────────────────────
class TestTokenize:
    def test_returns_list(self, processor):
        result = processor.tokenize("응집력은 모듈 내 요소들의 연관성이다.")
        assert isinstance(result, list)

    def test_korean_tokens(self, processor):
        result = processor.tokenize("응집력 결합력 모듈화 추상화")
        korean = [t for t in result if re.search(r'[\uAC00-\uD7A3]', t)]
        assert len(korean) > 0

    def test_min_length_2(self, processor):
        """최소 2자 이상 토큰"""
        result = processor.tokenize("응집력은 이 좋다")
        for t in result:
            assert len(t) >= 2, f"1자 토큰 포함: '{t}'"

    def test_bigrams(self, processor):
        tokens = ["응집력", "결합력", "모듈화"]
        bigrams = processor.make_bigrams(tokens)
        assert "응집력_결합력" in bigrams
        assert "결합력_모듈화" in bigrams

    def test_bigrams_empty(self, processor):
        assert processor.make_bigrams([]) == []
        assert processor.make_bigrams(["응집력"]) == []
