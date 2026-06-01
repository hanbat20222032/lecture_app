# 강의 이해도 측정기

> PDF · TXT · 직접 입력 기반 핵심 개념 추출 및 이해도 측정 데스크탑 앱  
> 소프트웨어 공학 프로젝트 #2 — 20222032 오은석

---

## 주요 기능

| 기능 | 설명 |
|---|---|
| **소스 입력** | PDF, TXT 파일 업로드 / 텍스트 직접 입력 (한국어·영어 지원) |
| **핵심 개념 추출** | TF-IDF + TextRank 결합 (외부 ML 라이브러리 없음) |
| **퀴즈 생성** | 빈칸 채우기 / OX 퀴즈 자동 생성 및 채점 |
| **이해도 점수화** | 퀴즈 60% + 커버리지 30% + 키워드 밀도 10% 가중 합산 |
| **누락 개념 탐지** | PDF 키워드 대비 필기 누락 항목 자동 감지 |
| **시각화** | matplotlib 차트 4종 (추이·세부·도넛·챕터) |
| **역색인 검색** | 키워드로 문서 즉시 검색 |
| **세션 관리** | 과목별 분류, 채점 이력, 점수 변화 추이 |

**완전 오프라인 동작** — LLM API 키 불필요

---

## 기술 스택

```
GUI          PyQt6
PDF 파싱     pymupdf (fitz)
알고리즘     TF-IDF · TextRank · 코사인 유사도 (직접 구현)
시각화       matplotlib
DB           SQLite (내장)
수치 연산    numpy
```

---

## 설치 및 실행

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. 앱 실행

```bash
python main.py
```

### 3. 테스트 실행

```bash
# 전체 테스트
python -m pytest tests/ -v

# 모듈별
python -m pytest tests/test_core.py -v
python -m pytest tests/test_analysis.py -v
python -m pytest tests/test_quiz.py -v
python -m pytest tests/test_gui.py -v
```

---

## 폴더 구조

```
lecture_app/
├── main.py                  # 앱 진입점
├── requirements.txt
├── setup.py                 # PyInstaller 패키징
│
├── core/                    # 알고리즘 레이어
│   ├── pdf_parser.py        # pymupdf 텍스트 추출 + 챕터 분리
│   ├── text_processor.py    # 정규화 · 토큰화 · 불용어 제거
│   ├── tfidf_engine.py      # TF-IDF 직접 구현
│   ├── textrank.py          # PageRank 기반 TextRank
│   ├── cosine_sim.py        # 코사인 유사도 · 커버리지
│   ├── inverted_index.py    # 역색인 구축 / 검색
│   └── pipeline.py          # QThread 분석 파이프라인
│
├── gui/                     # PyQt6 UI
│   ├── main_window.py       # 메인 윈도우 + 사이드바
│   ├── upload_tab.py        # 소스 입력 (PDF/TXT/텍스트)
│   ├── analysis_tab.py      # 개념 추출 결과
│   ├── quiz_tab.py          # 퀴즈 생성 · 풀이 · 채점
│   ├── report_tab.py        # 차트 · 리포트
│   ├── session_tab.py       # 검색 · 이력
│   └── styles.qss           # 다크 테마
│
├── analysis/                # 이해도 측정
│   ├── concept_extractor.py # TF-IDF + TextRank 결합
│   ├── coverage_calc.py     # 소스 vs 대상 커버리지
│   ├── gap_detector.py      # 누락 개념 탐지
│   └── scorer.py            # 이해도 점수 산출
│
├── quiz/                    # 퀴즈
│   ├── generator.py         # 생성 파이프라인
│   ├── blank_type.py        # 빈칸 채우기
│   ├── ox_type.py           # OX 퀴즈
│   └── evaluator.py         # 채점 · 세션 완료
│
├── reports/                 # 시각화
│   ├── chart_builder.py     # matplotlib 차트 5종
│   └── report_gen.py        # DB 데이터 집계
│
├── database/
│   ├── db_manager.py        # SQLite CRUD
│   ├── models.py            # 데이터 모델
│   └── migrations/
│       └── 001_initial.sql  # 초기 스키마
│
├── utils/
│   ├── config.py            # 전역 설정
│   ├── logger.py            # 로깅
│   ├── file_utils.py        # 파일 헬퍼
│   └── stopwords_ko.py      # 한국어·영어 불용어
│
└── tests/
    ├── test_core.py         # core 단위 테스트 (40개)
    ├── test_analysis.py     # analysis 단위 테스트 (26개)
    ├── test_quiz.py         # quiz 단위 테스트 (25개)
    └── test_gui.py          # GUI 초기화 테스트 (23개)
```

---

## 사용 흐름

```
1. 사이드바 → 과목 추가
2. 업로드 탭 → PDF / TXT / 텍스트 입력 → 분석 시작
3. 분석 탭 → 키워드 확인 / 수동 편집 → 분석 실행
4. 퀴즈 탭 → 퀴즈 생성 → 풀기 → 채점 결과 확인
5. 리포트 탭 → 차트로 이해도 추이 확인, 누락 개념 점검
6. 세션 탭 → 키워드 검색, 학습 이력 조회
```

---

## 패키징 (Windows 배포)

```bash
python setup.py
# dist/강의이해도측정기/강의이해도측정기.exe 생성
```
