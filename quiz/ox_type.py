"""
quiz/ox_type.py
OX 퀴즈 생성 — 개선판 v3

핵심 변경:
  - 필터 완화 (특수문자 비율, 숫자 비율, 최소 길이)
  - X 답 생성 전략 개선: 대체어가 없으면 문장 앞부분 부정 방식 사용
  - O:X ≈ 1:1
"""
from __future__ import annotations
import random
import re
from database.models import Quiz, QuizType
from utils.config import QUIZ_OX_COUNT, QUIZ_MIN_SENT_LEN
from utils.logger import get_logger

logger = get_logger(__name__)

_OX_MIN_LEN = 20    # 최소 문장 길이 (완화)
_OX_MAX_LEN = 120   # 최대 문장 길이


# ── 문장 품질 판별 ──────────────────────────────
def _is_good_sentence(sentence: str) -> bool:
    s = sentence.strip().lstrip("·-•①②③④⑤⑥⑦⑧⑨⑩() \t")

    if len(s) < _OX_MIN_LEN:
        return False

    # 질문형 제외
    if s.rstrip().endswith("?") or s.rstrip().endswith("？"):
        return False

    # 속성 행 시작 문장 제외 ("효과는", "정의는" 등 — 어느 개념인지 불명확)
    _PROP_STARTERS = {
        "효과는", "정의는", "중요성은", "보안성은", "독립성은", "명확성은",
        "원칙은", "목적은", "비유는", "특징은", "이점은", "핵심은",
        "항목은", "내용은", "구현은", "장점은", "예시는",
        # 속성 레이블: 어떤 개념의 종류/역할인지 주어가 없는 문장
        "종류는", "역할은", "유형은", "방법은", "방식은", "형태는",
        "구조는", "개념은", "의미는", "목표는", "단계는", "절차는",
        "조건은", "결과는", "요소는",
    }
    if any(s.startswith(w) for w in _PROP_STARTERS):
        return False

    # 숫자·점만 있는 단편 제외
    if re.search(r"[\d\-]{1,5}[\.\)]?\s*$", s.rstrip()):
        return False

    # 한글 최소 6자 (완화: 8→6)
    if len(re.findall(r"[\uAC00-\uD7A3]", s)) < 6:
        return False

    # 특수문자 비율 35% 이하 (완화: 25%→35%)
    special = len(re.findall(r"[^\uAC00-\uD7A3A-Za-z0-9\s①②③④⑤⑥⑦⑧⑨⑩]", s))
    if special / max(len(s), 1) > 0.35:
        return False

    # 단어 수 3개 미만 제외
    if len(s.split()) < 3:
        return False

    # 정답·해설 섹션 제외
    skip_markers = ("정답:", "해설:", "풀이:", "답:", "출제:", "정답 :", "해설 :", "답 :")
    if any(m in s for m in skip_markers):
        return False

    # 문제 지문형 제외
    problem_starters = ("당신이", "여러분이", "다음과 같은 대학", "당신은", "다음을 보고")
    if any(s.startswith(p) or p in s[:20] for p in problem_starters):
        return False

    # 지시문 제외
    if re.search(r"(하시오|쓰시오|설명하시오|구하시오|답하시오|나열하시오|서술하시오)[\.\。]?\s*$", s):
        return False

    # 코드 블록 제외
    code_markers = ("@startuml", "@enduml", "```", "startuml", "public ", "private ")
    if any(m in s for m in code_markers):
        return False
    # CamelCase 식별자: 패턴 제외 (UserValidator: 같은 코드 예제)
    if re.search(r"[A-Z][a-z]+[A-Z]\w*:", s):
        return False
    # "클래스이름: 설명" 코드 주석 패턴
    if re.search(r"\w+\s*:\s+\w+,\s*\w+", s):
        return False

    # 숫자로 시작하는 단편 제외
    if re.match(r"^\d", s.lstrip()):
        return False

    # 12자+ 연결 한국어 구절이 있으면 제외 (너무 불가독)
    if re.search(r"[\uAC00-\uD7A3]{12,}", s):
        return False

    return True


def _trim(sentence: str) -> str:
    if len(sentence) <= _OX_MAX_LEN:
        return sentence
    cut = sentence[:_OX_MAX_LEN]
    last_space = cut.rfind(" ")
    if last_space > _OX_MAX_LEN // 2:
        cut = cut[:last_space]
    return cut.rstrip(".,;:-(") + "…"


# ── 대체어 품질 확인 ────────────────────────────
def _bad_replacement(sentence: str, original: str, replacement: str) -> bool:
    if replacement in sentence:
        return True
    if original in replacement or replacement in original:
        return True
    if len(original) <= 2 and abs(len(original) - len(replacement)) <= 1:
        return True
    # 영어/숫자 전용 토큰은 한국어 문장에 부적절
    if re.match(r"^[a-zA-Z0-9_\.]+$", replacement):
        return True
    # 공백 없는 8자+ 순수 한국어 = 연결 토큰 (불량)
    if (len(replacement) > 7
            and re.match(r"^[\uAC00-\uD7A3]+$", replacement)
            and " " not in replacement):
        return True
    return False


# ── 메인 함수 ───────────────────────────────────
def generate_ox_quizzes(
    sentences: list[str],
    keywords:  list[str],
    doc_id:    int,
    count:     int = QUIZ_OX_COUNT,
) -> list[Quiz]:
    """
    OX 퀴즈 생성.

    X 답 전략:
      1순위: 다른 키워드로 교체
      2순위: 앞에 '비(非)' 추가
    """
    quizzes:        list[Quiz] = []
    used_sentences: set[str]  = set()
    want_x = False

    # 한국어 키워드만 후보 풀에 포함
    ko_keywords = [k for k in keywords if re.search(r"[\uAC00-\uD7A3]", k) and len(k) >= 2]
    shuffled_kws = list(keywords)
    random.shuffle(shuffled_kws)

    for keyword in shuffled_kws:
        if len(quizzes) >= count:
            break
        if len(keyword) < 2:
            continue

        candidates = [
            s for s in sentences
            if keyword in s
            and _is_good_sentence(s)
            and s not in used_sentences
        ]
        if not candidates:
            continue

        candidates.sort(key=len)
        sentence = candidates[0]
        trimmed  = _trim(sentence)

        if want_x:
            # ── X 답: 1순위 = 다른 키워드 교체 ──
            pool = [
                k for k in ko_keywords
                if k != keyword
                and not _bad_replacement(trimmed, keyword, k)
            ]
            pool.sort(key=lambda r: abs(len(r) - len(keyword)), reverse=True)

            if pool:
                replacement = pool[0]
                # 키워드 뒤에 붙은 조사(은/는/이/가)를 교체어에 맞게 재계산
                def _fix_josa(m):
                    rep = replacement
                    suffix = m.group(1) or ""
                    if suffix in ("은","는"):
                        code = ord(rep[-1]) - 0xAC00
                        suffix = "은" if (code >= 0 and code % 28 > 0) else "는"
                    elif suffix in ("이","가"):
                        code = ord(rep[-1]) - 0xAC00
                        suffix = "이" if (code >= 0 and code % 28 > 0) else "가"
                    return rep + suffix
                false_sent = re.sub(
                    re.escape(keyword) + r"(은|는|이|가)?",
                    _fix_josa, trimmed, count=1
                )
            else:
                # ── X 답: 2순위 = '비(非)' 부정 ──
                false_sent = trimmed.replace(keyword, f"비(非){keyword}", 1)
                if false_sent == trimmed:
                    continue

            quizzes.append(Quiz(
                document_id=doc_id, quiz_type=QuizType.OX,
                question=false_sent, answer="X",
                context=sentence[:200], keyword=keyword,
            ))
        else:
            # ── O 답: 원문 그대로 ──
            quizzes.append(Quiz(
                document_id=doc_id, quiz_type=QuizType.OX,
                question=trimmed, answer="O",
                context=sentence[:200], keyword=keyword,
            ))

        used_sentences.add(sentence)
        want_x = not want_x

    random.shuffle(quizzes)
    o_cnt = sum(1 for q in quizzes if q.answer == "O")
    x_cnt = sum(1 for q in quizzes if q.answer == "X")
    logger.info("OX 문제 생성: %d개 (O=%d X=%d)", len(quizzes), o_cnt, x_cnt)
    return quizzes[:count]
