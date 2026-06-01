"""
conftest.py
pytest 공통 픽스처
"""
import pytest
import sys, os

# 프로젝트 루트를 sys.path에 추가
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


# ── 샘플 문장 픽스처 ─────────────────────────────────────────
@pytest.fixture
def sample_sentences_ko():
    """한국어 강의 자료 샘플 문장 (handout_week05 기반)"""
    return [
        "응집력은 모듈 내의 요소들이 얼마나 밀접하게 연관되어 있는지 정도이다.",
        "결합력은 모듈 간의 의존성 정도를 나타낸다.",
        "높은 응집력과 낮은 결합력이 좋은 설계의 핵심 원칙이다.",
        "Functional 응집력은 모든 요소가 하나의 기능을 수행하는 최고 등급이다.",
        "Sequential 응집력은 출력이 입력으로 연결되는 구조이다.",
        "모듈화는 복잡한 시스템을 독립적인 모듈로 분해하여 관리하는 방법이다.",
        "추상화는 복잡한 것의 본질만 추출하고 불필요한 세부사항을 감추는 기법이다.",
        "정보 은닉은 모듈 내부 절차와 자료를 감춰서 다른 모듈이 접근 불가능하게 한다.",
        "캡슐화는 데이터와 메소드를 하나로 묶고 내부를 감추는 객체지향 원칙이다.",
        "다형성은 같은 메소드 이름이 다르게 동작하는 특성이다.",
        "상속은 부모 클래스의 속성과 메소드를 자식 클래스가 물려받는 개념이다.",
    ]


@pytest.fixture
def sample_keywords():
    """샘플 키워드 목록"""
    return ["응집력", "결합력", "모듈화", "추상화", "정보은닉", "캡슐화", "다형성", "상속"]


@pytest.fixture
def weak_subject_sentences():
    """속성 레이블이 주어인 문장 (필터링 대상)"""
    return [
        "종류는 컴파일다형성과 런타임다형성으로 나뉜다.",
        "역할은 데이터를 저장하고 검색하는 것이다.",
        "유형은 과정 추상화, 데이터 추상화, 제어 추상화로 구분된다.",
        "방법은 인터페이스 사용, 의존성 주입, 이벤트 기반이 있다.",
        "효과는 변경 영향 최소화와 재사용성 증대이다.",
    ]


@pytest.fixture
def prop_starter_sentences():
    """속성 열거형 문장 (OX 출제 제외 대상)"""
    return [
        "종류는 Content, Common, Control, Stamp, Data로 나뉜다.",
        "역할은 의존성을 줄이는 것이다.",
        "단계는 분석, 설계, 구현, 테스트로 구성된다.",
        "형태는 정적 타입과 동적 타입으로 구분된다.",
    ]


@pytest.fixture
def table_lines_cohesion():
    """응집력 7가지 등급 표 라인 (PDF 추출 시뮬레이션)"""
    return [
        "응집력의 7가지 등급",
        "등급 이름 설명 예시 평가",          # 단일 공백 헤더
        "7  Functional  모든요소가하나의  숫자계산, 문자열  매우좋음",
        "기능을수행  변환",                    # 줄바꿈 연속 행 (2컬럼)
        "6  Sequential  출력이입력으로  읽기→검증→저장  좋음",
        "연결됨",                             # 줄바꿈 연속 행 (1컬럼)
        "5  Communicational  같은데이터처리  사용자정보관리  중간",
        "4  Procedural  순서대로실행  A후에B  약함",
        "3  Temporal  같은시간에실행  초기화루틴  약함",
        "2  Logical  논리적카테고리  입력처리모음  매우약함",
        "1  Coincidental  무관한요소들  무작위함수모음  피해야함",
    ]
