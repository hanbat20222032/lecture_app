"""
quiz/blank_type.py
빈칸 채우기 문제 생성 — 개선판
· 문장 최대 길이 제한 (100자)
· 키워드 주변 문맥만 잘라내기
· 문제 품질 검증
"""
from __future__ import annotations
import random
import re
from database.models import Quiz, QuizType
from utils.config import QUIZ_BLANK_COUNT, QUIZ_MIN_SENT_LEN
from utils.logger import get_logger

logger = get_logger(__name__)

_BLANK        = "[____]"
_MAX_Q_LEN    = 100   # 문제 최대 글자 수
_CONTEXT_SIDE = 35    # 키워드 앞뒤 문맥 글자 수


# ── 유틸 ─────────────────────────────────────────────

def _trim_around_keyword(sentence: str, keyword: str) -> str:
    """
    긴 문장에서 키워드 앞뒤 문맥만 잘라낸다.
    잘린 시작점을 공백/구두점 경계로 정렬하여 어색한 시작을 방지한다.
    """
    idx = sentence.find(keyword)
    if idx == -1:
        return sentence

    start = max(0, idx - _CONTEXT_SIDE)
    end   = min(len(sentence), idx + len(keyword) + _CONTEXT_SIDE)

    # 시작점을 공백 경계로 정렬 (단어 중간에서 자르지 않음)
    if start > 0:
        next_space = sentence.find(" ", start)
        if next_space != -1 and next_space < idx - 2:
            start = next_space + 1  # 다음 단어 시작부터

    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(sentence) else ""
    trimmed = prefix + sentence[start:end].strip() + suffix

    # 여전히 길면 추가 절삭
    if len(trimmed) > _MAX_Q_LEN:
        keyword_in = trimmed.find(keyword)
        if keyword_in == -1:
            return trimmed[:_MAX_Q_LEN] + "…"
        half = _MAX_Q_LEN // 2
        s2 = max(0, keyword_in - half)
        # s2도 공백 경계로 정렬
        if s2 > 0:
            sp = trimmed.find(" ", s2)
            if sp != -1 and sp < keyword_in - 2:
                s2 = sp + 1
        e2 = min(len(trimmed), keyword_in + len(keyword) + half)
        trimmed = ("…" if s2 > 0 else "") + trimmed[s2:e2].strip() + ("…" if e2 < len(trimmed) else "")

    return trimmed


def _mask(sentence: str, keyword: str) -> str:
    """첫 번째 키워드만 [____]으로 치환."""
    return re.sub(re.escape(keyword), _BLANK, sentence, count=1)


def _is_good_sentence(sentence: str, keyword: str) -> bool:
    """문제로 사용하기 적합한 문장인지 판별."""
    if keyword not in sentence:
        return False
    if len(sentence) < QUIZ_MIN_SENT_LEN:
        return False
    if len(keyword) / max(len(sentence), 1) > 0.5:
        return False
    # PDF 정답/해설 섹션 제외
    skip_markers = ("정답:", "해설:", "풀이:", "답:", "출제:")
    if any(m in sentence for m in skip_markers):
        return False
    # 코드 블록 문장 제외 (프로그래밍 코드)
    code_markers = ("@startuml", "@enduml", "class ", "def ", "void ", "import ",
                    "```", "startuml", "enduml", "{", "}", "public ", "private ")
    if any(m in sentence for m in code_markers):
        return False
    # 불릿 리스트 형식 제외 (" - " 3개 이상 → 항목 나열 문장)
    if sentence.count(" - ") >= 3:
        return False
    # 숫자/점으로 끝나는 단편 제외 ("흐름 3.", "구성 1.1" 등)
    import re as _re
    if _re.search(r"\s+\d+\.?\s*$", sentence.rstrip()):
        return False
    # 섹션 번호 끝 제외 ("7-4.", "1.1.", "2-3" 등)
    if _re.search(r"\d+[-\.]\d+\.?\s*$", sentence.rstrip()):
        return False
    # 문제 지문형 문장 제외
    problem_starters = ("당신이", "여러분이", "다음과 같은 대학", "당신은", "다음을 보고")
    if any(sentence.startswith(p) or p in sentence[:20] for p in problem_starters):
        return False
    return True


def _make_question(sentence: str, keyword: str) -> str:
    """
    1. 문장이 _MAX_Q_LEN 이하면 그대로 사용
    2. 길면 키워드 주변만 잘라낸 후 마스킹
    """
    if len(sentence) <= _MAX_Q_LEN:
        return _mask(sentence, keyword)

    trimmed = _trim_around_keyword(sentence, keyword)
    return _mask(trimmed, keyword)


# ── 메인 함수 ─────────────────────────────────────────

def generate_blank_quizzes(
    sentences: list[str],
    keywords:  list[str],
    doc_id:    int,
    count:     int = QUIZ_BLANK_COUNT,
) -> list[Quiz]:
    """
    빈칸 채우기 문제를 생성한다.

    개선 사항:
    - 문제 최대 100자 제한
    - 키워드 주변 문맥만 추출
    - [____]가 문제 안에 없는 경우 제외
    - 같은 문장 재사용 방지
    """
    quizzes: list[Quiz] = []
    used_sentences: set[str] = set()

    for keyword in keywords:
        if len(quizzes) >= count:
            break
        if len(keyword) < 2:
            continue

        candidates = [
            s for s in sentences
            if _is_good_sentence(s, keyword) and s not in used_sentences
        ]
        if not candidates:
            continue

        # 짧은 문장 우선 (150자 이하) → 그 다음 긴 문장
        candidates.sort(key=lambda s: (len(s) > 150, -len(keyword)))
        sentence  = candidates[0]
        question  = _make_question(sentence, keyword)

        # [____] 포함 여부 최종 확인
        if _BLANK not in question:
            continue

        # 문제가 키워드만으로 이루어진 경우 제외
        question_without_blank = question.replace(_BLANK, "").replace("…", "").strip()
        if len(question_without_blank) < 12:   # 최소 12자 맥락 필요
            continue

        quizzes.append(Quiz(
            document_id = doc_id,
            quiz_type   = QuizType.BLANK,
            question    = question,
            answer      = keyword,
            context     = sentence[:200],   # 원문 최대 200자
            keyword     = keyword,
        ))
        used_sentences.add(sentence)

    random.shuffle(quizzes)
    logger.info("빈칸 문제 생성: %d개 (요청=%d)", len(quizzes), count)
    return quizzes[:count]
