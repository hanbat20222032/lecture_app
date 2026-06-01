"""
tests/test_stopwords.py
utils/stopwords_ko.py 테스트

BUG-04: _PROG_KEYWORDS import 오류 수정 검증
"""
import pytest
from utils.stopwords_ko import (
    STOPWORDS_KO, STOPWORDS_EN, _PROG_KEYWORDS,
    get_stopwords, is_stopword, filter_tokens,
)


# ── _PROG_KEYWORDS ────────────────────────────────────────────
class TestProgKeywords:
    def test_importable(self):
        """BUG-04: _PROG_KEYWORDS 정상 import"""
        assert _PROG_KEYWORDS is not None
        assert isinstance(_PROG_KEYWORDS, frozenset)

    def test_python_keywords(self):
        """Python 예약어 포함"""
        for kw in ["def", "class", "return", "import", "for", "while",
                   "if", "else", "elif", "try", "except", "with", "yield",
                   "lambda", "pass", "break", "continue"]:
            assert kw in _PROG_KEYWORDS, f"Python 예약어 '{kw}' 누락"

    def test_java_keywords(self):
        """Java 예약어 포함"""
        for kw in ["public", "private", "protected", "class", "void",
                   "static", "final", "interface", "extends", "implements",
                   "new", "this", "super", "abstract"]:
            assert kw in _PROG_KEYWORDS, f"Java 예약어 '{kw}' 누락"

    def test_common_identifiers(self):
        """일반 영어 식별자 포함"""
        for kw in ["get", "set", "str", "int", "self", "null", "true", "false"]:
            assert kw in _PROG_KEYWORDS, f"공통 식별자 '{kw}' 누락"

    def test_not_empty(self):
        """충분한 수의 키워드 포함 (60개 이상)"""
        assert len(_PROG_KEYWORDS) >= 60

    def test_all_lowercase(self):
        """모두 소문자로 저장"""
        for kw in _PROG_KEYWORDS:
            assert kw == kw.lower(), f"대문자 포함: '{kw}'"


# ── STOPWORDS_KO ─────────────────────────────────────────────
class TestStopwordsKo:
    def test_not_empty(self):
        assert len(STOPWORDS_KO) >= 30

    def test_particles(self):
        """조사 포함"""
        for w in ["이", "가", "을", "를", "은", "는", "에", "의"]:
            assert w in STOPWORDS_KO, f"조사 '{w}' 누락"

    def test_conjunctions(self):
        """접속어 포함"""
        for w in ["그리고", "그러나", "따라서", "하지만"]:
            assert w in STOPWORDS_KO, f"접속어 '{w}' 누락"

    def test_content_word_not_included(self):
        """개념어는 불용어가 아님"""
        for w in ["응집력", "캡슐화", "다형성", "추상화", "모듈화"]:
            assert w not in STOPWORDS_KO, f"개념어 '{w}'가 불용어에 포함됨"


# ── STOPWORDS_EN ─────────────────────────────────────────────
class TestStopwordsEn:
    def test_articles(self):
        for w in ["a", "an", "the"]:
            assert w in STOPWORDS_EN

    def test_prepositions(self):
        for w in ["in", "on", "at", "by", "for", "with", "of"]:
            assert w in STOPWORDS_EN

    def test_be_verbs(self):
        for w in ["is", "are", "was", "were", "be", "been"]:
            assert w in STOPWORDS_EN


# ── get_stopwords ─────────────────────────────────────────────
class TestGetStopwords:
    def test_ko(self):
        sw = get_stopwords("ko")
        assert "이" in sw
        assert "the" not in sw

    def test_en(self):
        sw = get_stopwords("en")
        assert "the" in sw
        assert "이" not in sw

    def test_all(self):
        sw = get_stopwords("all")
        assert "이" in sw
        assert "the" in sw

    def test_invalid_lang_raises(self):
        with pytest.raises(ValueError, match="지원하지 않는"):
            get_stopwords("jp")


# ── is_stopword ───────────────────────────────────────────────
class TestIsStopword:
    def test_korean_stopword(self):
        assert is_stopword("이", "ko") is True

    def test_korean_content_word(self):
        assert is_stopword("응집력", "ko") is False

    def test_english_stopword(self):
        assert is_stopword("THE", "en") is True  # 대소문자 무시

    def test_prog_keyword_via_all(self):
        # _PROG_KEYWORDS는 filter_tokens에서 사용, is_stopword는 ko/en/all 대상
        assert is_stopword("def", "en") is False  # 영어 불용어 아님 (별도 집합)


# ── filter_tokens ─────────────────────────────────────────────
class TestFilterTokens:
    def test_removes_ko_stopwords(self):
        tokens = ["응집력", "이", "결합력", "은", "중요하다"]
        result = filter_tokens(tokens, "ko")
        assert "이" not in result
        assert "은" not in result
        assert "응집력" in result
        assert "결합력" in result

    def test_removes_en_stopwords(self):
        tokens = ["cohesion", "is", "important", "the", "concept"]
        result = filter_tokens(tokens, "en")
        assert "is" not in result
        assert "the" not in result
        assert "cohesion" in result

    def test_removes_single_char(self):
        """길이 1 이하 토큰 제거"""
        tokens = ["응집력", "A", "B", "모듈"]
        result = filter_tokens(tokens, "all")
        assert "A" not in result
        assert "B" not in result

    def test_preserves_content_words(self):
        tokens = ["응집력", "결합력", "캡슐화", "다형성"]
        result = filter_tokens(tokens, "all")
        assert result == tokens

    def test_empty_list(self):
        assert filter_tokens([], "all") == []

    def test_all_stopwords(self):
        tokens = ["이", "가", "을", "를"]
        assert filter_tokens(tokens, "ko") == []
