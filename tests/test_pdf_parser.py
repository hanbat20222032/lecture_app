"""
tests/test_pdf_parser.py
core/pdf_parser.py 테스트

BUG-03: 표 줄바꿈 연속 행 처리 수정 검증
- PDFParser.__init__은 fitz.open을 호출하지 않으므로
  _doc을 직접 mock으로 교체하여 테스트
"""
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from core.pdf_parser import PDFParser


def make_parser_with_lines(line_groups: list[list[str]]) -> PDFParser:
    """
    PDFParser 인스턴스를 생성하고 _doc을 mock으로 교체한다.

    Args:
        line_groups: 페이지별 라인 목록
                     [[page1_line1, page1_line2, ...], [page2_line1, ...]]
    """
    parser = PDFParser("fake_test.pdf")

    # 각 페이지 mock 생성
    pages = []
    for lines in line_groups:
        mock_page = MagicMock()
        mock_page.get_text.return_value = "\n".join(lines)
        pages.append(mock_page)

    # _doc을 mock으로 교체 (iterable)
    mock_doc = MagicMock()
    mock_doc.__iter__ = MagicMock(return_value=iter(pages))
    parser._doc = mock_doc
    return parser


# ── PDFParser 초기화 ──────────────────────────────────────────
class TestInit:
    def test_init_with_string_path(self):
        parser = PDFParser("test.pdf")
        assert parser.path == Path("test.pdf")

    def test_init_with_path_object(self):
        parser = PDFParser(Path("test.pdf"))
        assert isinstance(parser.path, Path)

    def test_doc_initially_none(self):
        parser = PDFParser("test.pdf")
        assert parser._doc is None

    def test_init_does_not_open_file(self):
        """__init__에서 fitz.open 호출 안 함"""
        with patch('fitz.open') as mock_open:
            PDFParser("nonexistent.pdf")
            mock_open.assert_not_called()


# ── 헤더 감지 ─────────────────────────────────────────────────
class TestHeaderDetection:
    def test_double_space_header(self):
        """다중 공백 헤더 → 컬럼 분리"""
        parser = make_parser_with_lines([[
            "응집력의 7가지 등급",
            "항목  내용  비고",
            "7  Functional  모든요소가하나의기능을수행한다  중요",
        ]])
        results = parser._extract_table_sentences()
        assert len(results) > 0

    def test_single_space_header_detected(self):
        """BUG-03: 단일 공백 헤더 행도 감지 (PDF 폰트 특성)"""
        parser = make_parser_with_lines([[
            "응집력의 7가지 등급",
            "등급 이름 설명 예시 평가",        # 단일 공백 헤더
            "7  Functional  모든요소가하나의기능을수행  숫자계산  매우좋음",
        ]])
        results = parser._extract_table_sentences()
        # 헤더 감지 후 Pattern D 형식이어야 함
        pattern_d = [s for s in results if "이름:" in s or "설명:" in s or "등급:" in s]
        assert len(pattern_d) > 0, f"Pattern D 출력 없음. 전체 출력: {results}"

    def test_header_row_not_output_as_sentence(self):
        """헤더 행 자체가 문장으로 출력되면 안 됨"""
        parser = make_parser_with_lines([[
            "등급 이름 설명 예시 평가",
            "7  Functional  모든요소가하나의기능을수행  숫자계산  매우좋음",
        ]])
        results = parser._extract_table_sentences()
        for s in results:
            assert s.strip() != "등급 이름 설명 예시 평가", \
                f"헤더 행이 문장으로 출력됨"


# ── 줄바꿈 연속 행 병합 ──────────────────────────────────────
class TestContinuationRow:
    def test_single_col_continuation_merged(self):
        """BUG-03: 단일 컬럼 연속 행 → 설명 컬럼에 병합"""
        parser = make_parser_with_lines([[
            "등급 이름 설명 예시 평가",
            "6  Sequential  출력이입력으로  읽기→검증→저장  좋음",
            "연결됨",    # 단일 컬럼 연속 행
        ]])
        results = parser._extract_table_sentences()
        # "연결됨"이 Sequential 행에 포함되어야 함
        sequential = [s for s in results if "Sequential" in s]
        assert len(sequential) > 0, f"Sequential 문장 없음: {results}"
        assert any("연결됨" in s for s in sequential), \
            f"'연결됨'이 Sequential에 병합 안 됨: {sequential}"

    def test_multi_col_continuation_merged(self):
        """BUG-03 핵심: 다중 컬럼 연속 행 → 헤더 덮어쓰기 방지 + 컬럼별 병합"""
        parser = make_parser_with_lines([[
            "등급 이름 설명 예시 평가",
            "7  Functional  모든요소가하나의  숫자계산  매우좋음",
            "기능을수행  변환",   # 2컬럼 연속 행 → 설명+예시에 병합
        ]])
        results = parser._extract_table_sentences()
        functional = [s for s in results if "Functional" in s]
        assert len(functional) > 0, f"Functional 문장 없음: {results}"
        assert any("기능을수행" in s for s in functional), \
            f"'기능을수행' 병합 안 됨: {functional}"

    def test_current_headers_preserved_after_continuation(self):
        """BUG-03: 연속 행 처리 후 current_headers 유지 → 이후 행도 Pattern D"""
        parser = make_parser_with_lines([[
            "등급 이름 설명 예시 평가",
            "7  Functional  모든요소가하나의  숫자계산  매우좋음",
            "기능을수행  변환",   # 연속 행 → headers 유지해야 함
            "6  Sequential  출력이입력으로  읽기→검증→저장  좋음",
            "5  Communicational  같은데이터처리  사용자정보관리  중간",
            "4  Procedural  순서대로실행  A후에B  약함",
        ]])
        results = parser._extract_table_sentences()
        # 5~7등급 모두 Pattern D 형식 (헤더:값)
        pattern_d = [s for s in results if ":" in s and
                     any(n in s for n in ["Functional","Sequential","Communicational","Procedural"])]
        assert len(pattern_d) >= 3, \
            f"연속 행 이후 Pattern D 유지 실패 ({len(pattern_d)}개). 출력: {results}"

    def test_continuation_not_standalone_sentence(self):
        """연속 행이 독립 문장으로 남으면 안 됨"""
        parser = make_parser_with_lines([[
            "등급 이름 설명 예시 평가",
            "7  Functional  모든요소가하나의  숫자계산  매우좋음",
            "기능을수행",   # 단일 컬럼 연속 행
        ]])
        results = parser._extract_table_sentences()
        standalone = [s for s in results if s.strip() == "기능을수행"]
        assert len(standalone) == 0, f"연속 행이 독립 문장으로 남음"


# ── 응집력 7가지 등급 표 전체 ──────────────────────────────────
class TestCohesionTable:
    @pytest.fixture
    def cohesion_parser(self):
        return make_parser_with_lines([[
            "응집력의 7가지 등급",
            "등급 이름 설명 예시 평가",
            "7  Functional  모든요소가하나의  숫자계산, 문자열  매우좋음",
            "기능을수행  변환",
            "6  Sequential  출력이입력으로  읽기→검증→저장  좋음",
            "연결됨",
            "5  Communicational  같은데이터처리  사용자정보관리  중간",
            "4  Procedural  순서대로실행  A후에B  약함",
            "3  Temporal  같은시간에실행  초기화루틴  약함",
            "2  Logical  논리적카테고리  입력처리모음  매우약함",
            "1  Coincidental  무관한요소들  무작위함수모음  피해야함",
        ]])

    def test_all_seven_grades_present(self, cohesion_parser):
        results = cohesion_parser._extract_table_sentences()
        grade_names = ["Functional", "Sequential", "Communicational",
                       "Procedural", "Temporal", "Logical", "Coincidental"]
        for name in grade_names:
            assert any(name in s for s in results), \
                f"'{name}' 등급 누락. 출력: {results}"

    def test_sequential_contains_연결됨(self, cohesion_parser):
        results = cohesion_parser._extract_table_sentences()
        seq = [s for s in results if "Sequential" in s]
        assert len(seq) > 0
        assert any("연결됨" in s for s in seq), \
            f"Sequential에 '연결됨' 없음: {seq}"

    def test_functional_contains_기능을수행(self, cohesion_parser):
        results = cohesion_parser._extract_table_sentences()
        func = [s for s in results if "Functional" in s]
        assert len(func) > 0
        assert any("기능을수행" in s for s in func), \
            f"Functional에 '기능을수행' 없음: {func}"
