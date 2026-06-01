"""
tests/test_quiz.py
quiz/blank_type.py + quiz/ox_type.py 테스트

BUG-02: _PROP_STARTERS 필터 검증
"""
import pytest
from database.models import Quiz, QuizType
from quiz.blank_type import generate_blank_quizzes
from quiz.ox_type import generate_ox_quizzes

DOC_ID = 1  # 테스트용 더미 doc_id


@pytest.fixture
def good_sentences():
    """OX/빈칸 품질 조건을 통과하는 문장 목록"""
    return [
        "응집력은 모듈 내의 요소들이 얼마나 밀접하게 연관되어 있는지 정도이다.",
        "결합력은 모듈 간의 의존성 정도를 나타내며 낮을수록 좋다.",
        "모듈화는 복잡한 시스템을 독립적인 모듈로 분해하여 관리하는 방법이다.",
        "추상화는 복잡한 것의 본질만 추출하고 불필요한 세부사항을 감추는 기법이다.",
        "정보 은닉은 모듈 내부 절차와 자료를 감춰서 다른 모듈이 접근할 수 없게 한다.",
        "캡슐화는 데이터와 메소드를 하나로 묶고 내부를 감추는 객체지향 원칙이다.",
        "다형성은 같은 메소드 이름이 다르게 동작하는 특성을 의미한다.",
        "상속은 부모 클래스의 속성과 메소드를 자식 클래스가 물려받는 개념이다.",
        "높은 응집력과 낮은 결합력이 좋은 설계의 핵심 원칙으로 알려져 있다.",
        "Functional 응집력은 모든 요소가 하나의 기능을 수행하는 가장 높은 등급이다.",
    ]


@pytest.fixture
def keywords():
    return ["응집력", "결합력", "모듈화", "추상화", "캡슐화", "다형성", "상속"]


# ── 빈칸 채우기 퀴즈 ──────────────────────────────────────────
class TestBlankQuiz:
    def test_returns_list(self, good_sentences, keywords):
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        assert isinstance(result, list)

    def test_items_are_quiz(self, good_sentences, keywords):
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert isinstance(q, Quiz)

    def test_quiz_type_blank(self, good_sentences, keywords):
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.quiz_type == QuizType.BLANK

    def test_blank_marker_in_question(self, good_sentences, keywords):
        """[____] 마커가 문제에 포함"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert "[____]" in q.question, f"빈칸 마커 없음: {q.question}"

    def test_answer_is_keyword(self, good_sentences, keywords):
        """정답이 키워드 목록에 있어야 함"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.answer in keywords, f"정답 '{q.answer}'이 키워드에 없음"

    def test_answer_not_in_question(self, good_sentences, keywords):
        """정답이 문제에서 [____]로 대체되어야 함"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.answer not in q.question, \
                f"정답 '{q.answer}'이 문제에 남아있음: {q.question}"

    def test_count_limit(self, good_sentences, keywords):
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID, count=3)
        assert len(result) <= 3

    def test_no_quiz_empty_keywords(self, good_sentences):
        result = generate_blank_quizzes(good_sentences, [], DOC_ID)
        assert result == []

    def test_no_quiz_empty_sentences(self, keywords):
        result = generate_blank_quizzes([], keywords, DOC_ID)
        assert result == []

    def test_question_max_length(self, good_sentences, keywords):
        """문제 최대 100자 제한"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            # 말줄임표 포함해서 100자 + 여유
            assert len(q.question) <= 120, f"문제 너무 김: {len(q.question)}자"

    def test_context_stored(self, good_sentences, keywords):
        """원문 문맥이 저장되어야 함"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.context is not None
            assert len(q.context) > 0

    def test_no_duplicate_sentences(self, good_sentences, keywords):
        """같은 문장을 두 번 사용하지 않음"""
        result = generate_blank_quizzes(good_sentences, keywords, DOC_ID)
        contexts = [q.context for q in result]
        assert len(contexts) == len(set(contexts)), "중복 문장 사용됨"


# ── OX 퀴즈 ──────────────────────────────────────────────────
class TestOxQuiz:
    def test_returns_list(self, good_sentences, keywords):
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID)
        assert isinstance(result, list)

    def test_items_are_quiz(self, good_sentences, keywords):
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert isinstance(q, Quiz)

    def test_quiz_type_ox(self, good_sentences, keywords):
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.quiz_type == QuizType.OX

    def test_answer_o_or_x(self, good_sentences, keywords):
        """정답은 반드시 'O' 또는 'X'"""
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID)
        for q in result:
            assert q.answer in ("O", "X"), f"OX 답 오류: '{q.answer}'"

    def test_count_limit(self, good_sentences, keywords):
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID, count=4)
        assert len(result) <= 4

    def test_has_o_and_x(self, good_sentences, keywords):
        """O와 X 문제가 모두 생성 (충분한 문장/키워드 있을 때)"""
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID, count=6)
        answers = {q.answer for q in result}
        if len(result) >= 2:
            assert "O" in answers, "O 문제 없음"
            assert "X" in answers, "X 문제 없음"

    # ── BUG-02: _PROP_STARTERS 필터 ──────────────────────────
    def test_prop_starters_excluded(self, keywords):
        """BUG-02: 속성 열거형 문장은 OX 출제 제외"""
        prop_sentences = [
            "종류는 Content, Common, Control, Stamp, Data로 나뉜다.",
            "역할은 데이터를 저장하고 관리하는 것이다.",
            "유형은 과정 추상화, 데이터 추상화, 제어 추상화로 구분된다.",
            "방법은 인터페이스 사용, 의존성 주입, 이벤트 기반이 있다.",
            "단계는 분석, 설계, 구현, 테스트로 이루어진다.",
        ]
        result = generate_ox_quizzes(prop_sentences, keywords, DOC_ID)
        prop_starters = {
            "종류는", "역할은", "유형은", "방법은", "방식은",
            "형태는", "구조는", "개념은", "의미는", "목표는",
            "단계는", "절차는", "조건은", "결과는", "요소는",
        }
        for q in result:
            for starter in prop_starters:
                assert not q.question.startswith(starter), \
                    f"속성 열거 문장 출제됨: '{q.question}'"

    @pytest.mark.parametrize("starter,sentence", [
        ("종류는", "종류는 A, B, C로 분류된다는 것이 일반적인 견해이다."),
        ("역할은", "역할은 데이터를 저장하고 관리하는 것으로 알려져 있다."),
        ("단계는", "단계는 분석, 설계, 구현, 테스트로 이루어지는 것이다."),
        ("효과는", "효과는 변경 영향 최소화와 재사용성 증대로 나타난다."),
        ("정의는", "정의는 모듈 내 요소들의 연관성으로 정립되어 있다."),
    ])
    def test_individual_prop_starter(self, starter, sentence, keywords):
        """개별 속성 시작어 필터 확인"""
        result = generate_ox_quizzes([sentence], keywords, DOC_ID)
        for q in result:
            assert not q.question.startswith(starter), \
                f"'{starter}' 시작 문장 출제됨: {q.question}"

    def test_x_answer_modifies_keyword(self, good_sentences, keywords):
        """X 문제는 원본과 다른 키워드 포함"""
        result = generate_ox_quizzes(good_sentences, keywords, DOC_ID, count=10)
        x_quizzes = [q for q in result if q.answer == "X"]
        for q in x_quizzes:
            # X 문제의 질문은 원본 문장과 달라야 함
            assert q.question != q.context[:len(q.question)], \
                f"X 문제가 원본과 동일: {q.question}"
