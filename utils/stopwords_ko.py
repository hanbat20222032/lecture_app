"""
utils/stopwords_ko.py
한국어 + 영어 불용어 사전
TF-IDF / TextRank 전처리 시 해당 단어를 제외한다.
"""

from __future__ import annotations

# ──────────────────────────────────────────────
# 한국어 불용어
# ──────────────────────────────────────────────

STOPWORDS_KO: frozenset[str] = frozenset({
    # 조사
    "이", "가", "을", "를", "은", "는", "에", "의", "와", "과",
    "도", "로", "으로", "에서", "까지", "부터", "에게", "한테",
    "이라", "라", "이며", "며", "이고", "고", "이나", "나",
    "이든", "든", "이랑", "랑", "하고",
    # 어미/접속어
    "그리고", "그러나", "그런데", "그래서", "그러므로", "따라서",
    "하지만", "또한", "즉", "왜냐하면", "때문에", "하여", "하여서",
    "이어서", "게다가", "뿐만", "아니라", "더불어", "비롯한",
    # 대명사
    "이것", "그것", "저것", "이런", "그런", "저런", "여기", "거기",
    "이곳", "저곳", "나", "우리", "저", "그", "그녀", "그들",
    # 수식어 / 관형사
    "이", "그", "저", "각", "모든", "여러", "어떤", "각각",
    "같은", "다른", "어느", "여러", "무슨",
    # 일반 동사/형용사 (의미 없는)
    "있다", "없다", "하다", "되다", "이다", "아니다", "같다",
    "보다", "오다", "가다", "알다", "모르다", "크다", "작다",
    "많다", "적다", "좋다", "나쁘다",
    # 부사
    "매우", "아주", "너무", "정말", "꽤", "다소", "약간",
    "거의", "항상", "자주", "가끔", "종종", "이미", "아직",
    "바로", "곧", "여전히", "더", "덜", "가장", "훨씬",
    # 숫자 표현
    "첫번째", "두번째", "세번째", "번째", "가지", "개",
    # 공통 학술 표현
    "통해", "통한", "대한", "관한", "위한", "위해",
    "방법", "경우", "다음", "이후", "이전", "현재", "기준",
    "또는", "혹은", "즉", "예를", "들어", "예컨대",
})


# ──────────────────────────────────────────────
# 영어 불용어
# ──────────────────────────────────────────────

# 프로그래밍 언어 예약어 (코드 예제 PDF에서 키워드로 추출되는 것 방지)
_PROG_KEYWORDS: frozenset[str] = frozenset({
    "public","private","protected","static","void","class","int",
    "string","return","new","this","true","false","null","final",
    "abstract","interface","implements","extends","import","package",
    "if","else","for","while","do","switch","case","break","continue",
    "try","catch","throw","throws","finally","def","self","none",
    "var","let","const","function","async","await","list","dict",
    "float","double","long","char","byte","short","bool","obj","arr",
    "lic","tic","str","num","ect",
    # 일반 영어 단어
    "user","users","db","stack","queue","list","node","data",
    "repo","price","service","processor","factory","handler",
    "manager","controller","helper","util","utils","config","app",
    "coupling","cohesion","code","type","name","size","test",
    "view","model","api","url","id","key","value","item",
    "get","set","add","run","use","new","old","max","min",
})

STOPWORDS_EN: frozenset[str] = frozenset({
    # 관사
    "a", "an", "the",
    # 전치사
    "in", "on", "at", "by", "for", "with", "about", "against",
    "between", "into", "through", "during", "before", "after",
    "above", "below", "to", "from", "up", "down", "of", "off",
    "over", "under", "again", "out", "around", "upon",
    # 접속사
    "and", "but", "or", "nor", "so", "yet", "both", "either",
    "neither", "not", "only", "whether", "although", "because",
    "since", "while", "if", "unless", "until", "when", "where",
    "as", "than", "that", "which", "who", "whom", "whose",
    # 대명사
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves",
    "you", "your", "yours", "yourself", "he", "him", "his",
    "she", "her", "hers", "it", "its", "they", "them", "their",
    "this", "that", "these", "those", "what", "each", "few",
    "more", "most", "other", "some", "such", "no", "any",
    # 조동사 / be동사
    "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did",
    "can", "could", "will", "would", "shall", "should",
    "may", "might", "must", "ought",
    # 부사
    "very", "just", "also", "too", "only", "now", "then",
    "here", "there", "often", "always", "never", "sometimes",
    "already", "still", "yet", "even", "however",
    # 학술 표현
    "thus", "therefore", "hence", "moreover", "furthermore",
    "however", "nevertheless", "consequently", "therefore",
    "according", "based", "using", "used", "use",
    "one", "two", "three", "first", "second", "third",
})


# ──────────────────────────────────────────────
# 공통 인터페이스
# ──────────────────────────────────────────────

def get_stopwords(lang: str = "ko") -> frozenset[str]:
    """
    언어 코드에 따라 불용어 집합을 반환한다.

    Args:
        lang: "ko" (한국어), "en" (영어), "all" (전체)
    """
    if lang == "ko":
        return STOPWORDS_KO
    if lang == "en":
        return STOPWORDS_EN
    if lang == "all":
        return STOPWORDS_KO | STOPWORDS_EN
    raise ValueError(f"지원하지 않는 언어 코드: {lang}  (ko / en / all)")


def is_stopword(word: str, lang: str = "all") -> bool:
    """단어가 불용어인지 확인한다."""
    return word.lower() in get_stopwords(lang)


def filter_tokens(tokens: list[str], lang: str = "all") -> list[str]:
    """토큰 리스트에서 불용어를 제거한다."""
    sw = get_stopwords(lang)
    return [t for t in tokens if t.lower() not in sw and t.lower() not in _PROG_KEYWORDS and len(t) > 1]
