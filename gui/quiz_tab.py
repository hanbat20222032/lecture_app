"""
gui/quiz_tab.py
퀴즈 탭 — 빈칸·OX 문제 생성 / 풀이 / 채점 / 이력
"""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QStackedWidget, QLineEdit, QButtonGroup, QRadioButton,
    QScrollArea, QMessageBox, QProgressDialog, QApplication,
    QSplitter,
)
from utils.config import COLOR, QUIZ_BLANK_COUNT, QUIZ_OX_COUNT
from utils.logger import get_logger
from database import db_manager as db
from database.models import Quiz, QuizType

logger = get_logger(__name__)
A=COLOR['primary']; AH=COLOR['primary_h']
TP=COLOR['text_pri']; TS=COLOR['text_sec']; BD=COLOR['border']
OK=COLOR['success']; ER=COLOR['danger']; WN=COLOR['warning']
BG=COLOR['bg_card']; BI=COLOR['bg_input']


# ── 퀴즈 생성 워커 ─────────────────────────────
class QuizGenWorker(QThread):
    finished = pyqtSignal(int, str)  # (생성 수, quiz_type)
    error    = pyqtSignal(str)

    def __init__(self, doc_id, content, keywords, quiz_type="all", parent=None):
        super().__init__(parent)
        self.doc_id    = doc_id
        self.content   = content
        self.keywords  = keywords
        self.quiz_type = quiz_type

    def run(self):
        try:
            from quiz.generator import QuizGenerator
            gen = QuizGenerator(QUIZ_BLANK_COUNT, QUIZ_OX_COUNT)
            result = gen.generate(
                self.doc_id, self.content, self.keywords,
                quiz_type=self.quiz_type
            )
            self.finished.emit(result.total_count, self.quiz_type)
        except Exception as e:
            self.error.emit(str(e))


# ── 단일 퀴즈 카드 ─────────────────────────────
class QuizCard(QFrame):
    answered = pyqtSignal(str)   # 사용자 답변

    def __init__(self, quiz: Quiz, index: int, total: int, parent=None):
        super().__init__(parent)
        self.quiz = quiz
        self._answered = False
        self.setStyleSheet(f"QFrame{{background:{BG};border:1px solid {BD};border-radius:12px;}}")
        self._build(index, total)

    def _build(self, index, total):
        lay = QVBoxLayout(self); lay.setContentsMargins(24,20,24,20); lay.setSpacing(14)

        # 헤더
        hdr = QHBoxLayout()
        badge_text = "빈칸 채우기" if self.quiz.quiz_type == QuizType.BLANK else "O / X"
        badge_color = A if self.quiz.quiz_type == QuizType.BLANK else "#1D9E75"
        badge = QLabel(badge_text)
        badge.setStyleSheet(
            f"background:{badge_color};color:#fff;border-radius:5px;"
            f"padding:3px 10px;font-size:12px;font-weight:600;"
        )
        progress = QLabel(f"{index} / {total}")
        progress.setStyleSheet(f"font-size:12px;color:{TS};")
        hdr.addWidget(badge); hdr.addStretch(); hdr.addWidget(progress)
        lay.addLayout(hdr)

        # 문제 텍스트
        q_lbl = QLabel(self.quiz.question)
        q_lbl.setWordWrap(True)
        q_lbl.setStyleSheet(f"font-size:15px;color:{TP};line-height:1.6;")
        lay.addWidget(q_lbl)

        # 답변 입력
        if self.quiz.quiz_type == QuizType.BLANK:
            self._input = QLineEdit()
            self._input.setPlaceholderText("정답을 입력하세요…")
            self._input.setStyleSheet(
                f"QLineEdit{{background:{BI};color:{TP};"
                f"border:1.5px solid {BD};border-radius:8px;"
                f"font-size:14px;padding:10px 14px;}}"
                f"QLineEdit:focus{{border-color:{A};}}"
            )
            self._input.returnPressed.connect(self._submit)
            lay.addWidget(self._input)
        else:
            ox_row = QHBoxLayout(); ox_row.setSpacing(10)
            self._o_btn = QPushButton("O  (맞다)")
            self._x_btn = QPushButton("X  (틀리다)")
            for btn, color in [(self._o_btn, OK), (self._x_btn, ER)]:
                btn.setFixedHeight(48)
                btn.setStyleSheet(
                    f"QPushButton{{background:transparent;color:{color};"
                    f"border:2px solid {color};border-radius:10px;"
                    f"font-size:14px;font-weight:600;}}"
                    f"QPushButton:hover{{background:rgba(0,0,0,0.08);}}"
                    f"QPushButton:disabled{{opacity:0.4;}}"
                )
            self._o_btn.clicked.connect(lambda: self._submit_ox("O"))
            self._x_btn.clicked.connect(lambda: self._submit_ox("X"))
            ox_row.addWidget(self._o_btn); ox_row.addWidget(self._x_btn)
            lay.addLayout(ox_row)
            self._input = None

        # 제출 버튼 (빈칸형)
        if self.quiz.quiz_type == QuizType.BLANK:
            self._submit_btn = QPushButton("제출")
            self._submit_btn.setFixedHeight(42)
            self._submit_btn.setStyleSheet(
                f"QPushButton{{background:{A};color:#fff;border:none;"
                f"border-radius:9px;font-size:14px;font-weight:700;}}"
                f"QPushButton:hover{{background:{AH};}}"
            )
            self._submit_btn.clicked.connect(self._submit)
            lay.addWidget(self._submit_btn)

        # 피드백 레이블
        self._feedback = QLabel()
        self._feedback.setVisible(False)
        self._feedback.setWordWrap(True)
        self._feedback.setStyleSheet(f"font-size:13px;padding:8px;border-radius:7px;")
        lay.addWidget(self._feedback)

    def _submit(self):
        if self._answered or not self._input:
            return
        ans = self._input.text().strip()
        if not ans:
            return
        self._finalize(ans)

    def _submit_ox(self, ans: str):
        if self._answered:
            return
        self._finalize(ans)

    def _finalize(self, ans: str):
        self._answered = True
        correct = (ans.lower().replace(" ","") ==
                   self.quiz.answer.lower().replace(" ","")) \
                  if self.quiz.quiz_type == QuizType.BLANK \
                  else ans.upper() == self.quiz.answer.upper()

        if correct:
            msg = f"✓ 정답입니다!"
            self._feedback.setStyleSheet(
                f"font-size:13px;padding:8px;border-radius:7px;"
                f"background:rgba(34,197,94,0.12);color:{OK};"
            )
        else:
            msg = f"✗ 오답  —  정답: {self.quiz.answer}"
            self._feedback.setStyleSheet(
                f"font-size:13px;padding:8px;border-radius:7px;"
                f"background:rgba(239,68,68,0.10);color:{ER};"
            )

        self._feedback.setText(msg)
        self._feedback.setVisible(True)

        # 입력 비활성화
        if self._input:
            self._input.setEnabled(False)
        if hasattr(self, '_submit_btn'):
            self._submit_btn.setEnabled(False)
        if hasattr(self, '_o_btn'):
            self._o_btn.setEnabled(False)
            self._x_btn.setEnabled(False)

        self.answered.emit(ans)


# ── 퀴즈 풀이 패널 ────────────────────────────
class QuizPlayPanel(QWidget):
    sessionDone   = pyqtSignal(int, int, list)   # correct, total, wrong_keywords
    exitRequested = pyqtSignal()                 # 나가기 요청

    def __init__(self, parent=None):
        super().__init__(parent)
        self._quizzes: list[Quiz] = []
        self._answers: list[tuple[Quiz, str]] = []
        self._current = 0
        self._build()

    def _build(self):
        self._lay = QVBoxLayout(self)
        self._lay.setContentsMargins(0,0,0,0); self._lay.setSpacing(12)

        # 진행 표시
        self._prog_lbl = QLabel("0 / 0")
        self._prog_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._prog_lbl.setStyleSheet(f"font-size:13px;color:{TS};")
        self._lay.addWidget(self._prog_lbl)

        # 카드 영역 (스크롤)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        self._card_container = QWidget()
        self._card_lay = QVBoxLayout(self._card_container)
        self._card_lay.setContentsMargins(0,0,0,0)
        self._scroll.setWidget(self._card_container)
        self._lay.addWidget(self._scroll, stretch=1)

        # 하단 버튼 행 (나가기 + 다음)
        btn_row = QHBoxLayout(); btn_row.setSpacing(8)

        self._exit_btn = QPushButton("나가기")
        self._exit_btn.setFixedHeight(44)
        self._exit_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{TS};"
            f"border:1.5px solid {BD};border-radius:10px;"
            f"font-size:13px;padding:0 16px;}}"
            f"QPushButton:hover{{color:{ER};border-color:{ER};}}"
        )
        self._exit_btn.clicked.connect(self._on_exit)

        self._next_btn = QPushButton("다음 문제 ▶")
        self._next_btn.setFixedHeight(44)
        self._next_btn.setEnabled(False)
        self._next_btn.setStyleSheet(
            f"QPushButton{{background:{A};color:#fff;border:none;"
            f"border-radius:10px;font-size:14px;font-weight:700;}}"
            f"QPushButton:hover:enabled{{background:{AH};}}"
            f"QPushButton:disabled{{background:{BD};color:{TS};}}"
        )
        self._next_btn.clicked.connect(self._next)

        btn_row.addWidget(self._exit_btn, 1)
        btn_row.addWidget(self._next_btn, 3)
        self._lay.addLayout(btn_row)

    def start(self, quizzes: list[Quiz]):
        self._quizzes  = quizzes
        self._answers  = []
        self._current  = 0
        self._show_card(0)

    def _show_card(self, idx: int):
        # 카드 초기화 - takeAt으로 위젯·스페이서 모두 제거
        while self._card_lay.count():
            item = self._card_lay.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)   # 즉시 제거 (deleteLater 지연 없음)

        if idx >= len(self._quizzes):
            self._finish()
            return

        quiz  = self._quizzes[idx]
        total = len(self._quizzes)
        card  = QuizCard(quiz, idx + 1, total)
        card.answered.connect(self._on_answered)
        self._card_lay.addWidget(card)
        self._card_lay.addStretch()
        self._prog_lbl.setText(f"{idx+1} / {total}")
        self._next_btn.setEnabled(False)
        self._next_btn.setText(
            "결과 보기 ▶" if idx == total - 1 else "다음 문제 ▶"
        )
        # 새 카드마다 스크롤 맨 위로
        self._scroll.verticalScrollBar().setValue(0)

    def _on_answered(self, user_ans: str):
        quiz = self._quizzes[self._current]
        self._answers.append((quiz, user_ans))
        self._next_btn.setEnabled(True)

    def _next(self):
        self._current += 1
        self._show_card(self._current)

    def _on_exit(self):
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self, "퀴즈 종료",
            "퀴즈를 중단하고 나가시겠습니까?\n풀지 않은 문제는 저장되지 않습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.exitRequested.emit()

    def _finish(self):
        correct = sum(
            1 for q, ua in self._answers
            if ua.lower().replace(" ","") == q.answer.lower().replace(" ","")
            or ua.upper() == q.answer.upper()
        )
        wrong_kws = list({
            q.keyword for q, ua in self._answers
            if ua.lower().replace(" ","") != q.answer.lower().replace(" ","")
            and ua.upper() != q.answer.upper()
            and q.keyword
        })
        self.sessionDone.emit(correct, len(self._answers), wrong_kws)


# ── 퀴즈 탭 메인 ──────────────────────────────
class QuizTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._subject_id: Optional[int] = None
        self._current_doc_id: Optional[int] = None
        self._last_doc_id: Optional[int] = None   # 이전 클릭 doc_id (토글 감지용)
        self._session_id: Optional[int] = None
        self._current_quiz_type: str = 'all'   # 마지막 생성 타입
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20,16,20,16); root.setSpacing(10)

        # 헤더
        hdr = QHBoxLayout()
        title = QLabel("퀴즈")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{TP};")
        sub = QLabel("핵심 키워드 기반 빈칸 채우기 / OX 문제")
        sub.setStyleSheet(f"font-size:13px;color:{TS};")
        tc = QVBoxLayout(); tc.setSpacing(2); tc.addWidget(title); tc.addWidget(sub)
        hdr.addLayout(tc); hdr.addStretch()
        self._gen_blank_btn = QPushButton("빈칸 문제 생성")
        self._gen_ox_btn    = QPushButton("OX 문제 생성")
        self._gen_all_btn   = QPushButton("전체 생성")
        self._gen_ox_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{A};"
            f"border:1.5px solid {A};border-radius:8px;padding:8px 14px;}}"
            f"QPushButton:hover{{background:rgba(91,95,217,0.1);}}"
        )
        self._gen_all_btn.setStyleSheet(
            f"QPushButton{{background:#1D9E75;color:#fff;"
            f"border:none;border-radius:8px;padding:8px 14px;}}"
            f"QPushButton:hover{{background:#0F6E56;}}"
        )
        for btn in (self._gen_blank_btn, self._gen_ox_btn, self._gen_all_btn):
            btn.setEnabled(False)
            hdr.addWidget(btn)
        self._gen_blank_btn.clicked.connect(lambda: self._on_gen_clicked("blank"))
        self._gen_ox_btn.clicked.connect(lambda: self._on_gen_clicked("ox"))
        self._gen_all_btn.clicked.connect(lambda: self._on_gen_clicked("all"))
        root.addLayout(hdr)

        # 스플리터: 문서 선택(좌) + 풀이/이력(우)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 문서 목록
        left = QFrame()
        left.setStyleSheet(f"QFrame{{background:{BG};border:1px solid {BD};border-radius:10px;}}")
        ll = QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(8)
        ll.addWidget(QLabel("문서 선택").also(lambda l: l.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")))
        from PyQt6.QtWidgets import QListWidget
        self._doc_list = QListWidget()
        self._doc_list.setToolTip("문서를 선택하세요. 같은 항목 클릭 시 선택 해제")
        self._doc_list.currentRowChanged.connect(self._on_doc_selected)
        self._doc_list.itemClicked.connect(self._on_doc_item_clicked)
        ll.addWidget(self._doc_list, stretch=1)

        # 퀴즈 수 정보
        self._quiz_info = QLabel("퀴즈 없음")
        self._quiz_info.setStyleSheet(f"font-size:12px;color:{TS};")
        ll.addWidget(self._quiz_info)

        # 시작 버튼
        self._start_btn = QPushButton("퀴즈 시작 ▶")
        self._start_btn.setEnabled(False)
        self._start_btn.setStyleSheet(
            f"QPushButton{{background:{A};color:#fff;border:none;"
            f"border-radius:9px;font-size:13px;font-weight:700;padding:10px;}}"
            f"QPushButton:hover:enabled{{background:{AH};}}"
            f"QPushButton:disabled{{background:{BD};color:{TS};}}"
        )
        self._start_btn.clicked.connect(self._start_quiz)
        ll.addWidget(self._start_btn)

        # 오른쪽: 스택 (풀이 / 결과 / 이력)
        right = QFrame()
        right.setStyleSheet(f"QFrame{{background:{BG};border:1px solid {BD};border-radius:10px;}}")
        rl = QVBoxLayout(right); rl.setContentsMargins(12,12,12,12); rl.setSpacing(8)

        self._stack = QStackedWidget()

        # 페이지 0: 안내
        guide = QWidget()
        gl = QVBoxLayout(guide); gl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g1 = QLabel("왼쪽에서 문서를 선택하고\n퀴즈를 생성하세요.")
        g1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        g1.setStyleSheet(f"font-size:15px;color:{TS};line-height:1.8;")
        gl.addWidget(g1)

        # 페이지 1: 풀이
        self._play_panel = QuizPlayPanel()
        self._play_panel.sessionDone.connect(self._on_session_done)
        self._play_panel.exitRequested.connect(self._on_exit_quiz)

        # 페이지 2: 결과
        result_widget = QWidget()
        rrl = QVBoxLayout(result_widget); rrl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_lbl = QLabel()
        self._result_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._result_lbl.setWordWrap(True)
        self._result_lbl.setStyleSheet(f"font-size:16px;color:{TP};line-height:1.8;")
        retry_btn = QPushButton("다시 풀기")
        retry_btn.setFixedWidth(160); retry_btn.clicked.connect(self._retry)
        rrl.addWidget(self._result_lbl); rrl.addWidget(retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # 페이지 3: 이력
        hist_widget = QWidget()
        hl = QVBoxLayout(hist_widget); hl.setContentsMargins(0,0,0,0)
        hl.addWidget(QLabel("채점 이력").also(lambda l: l.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")))
        self._hist = QTableWidget(0, 5)
        self._hist.setHorizontalHeaderLabels(["날짜","문서","총 문제","정답","점수"])
        self._hist.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._hist.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist.verticalHeader().setVisible(False)
        hl.addWidget(self._hist, stretch=1)

        self._stack.addWidget(guide)
        self._stack.addWidget(self._play_panel)
        self._stack.addWidget(result_widget)
        self._stack.addWidget(hist_widget)
        rl.addWidget(self._stack)

        splitter.addWidget(left); splitter.addWidget(right)
        splitter.setSizes([240, 660])
        root.addWidget(splitter, stretch=1)

    # ── 외부 API ────────────────────────────
    def set_subject(self, subject_id: int):
        self._subject_id = subject_id
        self._refresh_docs()

    # ── 문서 목록 ───────────────────────────
    def _refresh_docs(self):
        if not self._subject_id: return
        self._last_doc_id = None   # 목록 갱신 시 이전 선택 초기화
        docs = db.get_documents_by_subject(self._subject_id)
        self._doc_list.clear()
        from PyQt6.QtWidgets import QListWidgetItem
        from database.models import SourceType
        icons = {SourceType.PDF:"📄", SourceType.TXT:"📝", SourceType.TEXT:"✏️"}
        for d in docs:
            icon = icons.get(d.source_type, "📄")
            item = QListWidgetItem(f"{icon} {d.title}")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            self._doc_list.addItem(item)

    def _on_doc_item_clicked(self, item):
        """이미 선택된 문서를 다시 클릭하면 선택 해제."""
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        # currentRowChanged 가 먼저 실행되므로 currentRow 비교는 항상 True
        # → 이전 클릭 doc_id(_last_doc_id)와 비교해야 정확한 재클릭 감지 가능
        if doc_id == self._last_doc_id:
            # 재클릭 → 선택 해제
            self._last_doc_id = None
            self._doc_list.clearSelection()
            self._doc_list.setCurrentRow(-1)
            self._current_doc_id = None
            for btn in (self._gen_blank_btn, self._gen_ox_btn, self._gen_all_btn):
                btn.setEnabled(False)
            self._start_btn.setEnabled(False)
            self._quiz_info.setText("문서를 선택하세요.")
            self._stack.setCurrentIndex(0)
        else:
            # 새 항목 클릭 → _last_doc_id 갱신 (다음 재클릭 감지용)
            self._last_doc_id = doc_id

    def _on_doc_selected(self, row: int):
        item = self._doc_list.item(row)
        if not item: return
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        self._current_doc_id = doc_id
        quizzes = db.get_quizzes(doc_id)
        kws     = db.get_keywords(doc_id)
        has_kw  = len(kws) > 0
        has_quiz= len(quizzes) > 0
        for btn in (self._gen_blank_btn, self._gen_ox_btn, self._gen_all_btn):
            btn.setEnabled(has_kw)
        self._start_btn.setEnabled(has_quiz)
        self._quiz_info.setText(
            f"키워드 {len(kws)}개  |  퀴즈 {len(quizzes)}개" if has_kw
            else "분석 탭에서 먼저 분석을 실행하세요."
        )
        self._load_history()
        self._stack.setCurrentIndex(3 if has_quiz else 0)

    # ── 퀴즈 생성 ───────────────────────────
    def _on_gen_clicked(self, quiz_type: str = "all"):
        if not self._current_doc_id:
            QMessageBox.warning(self, "문서 미선택",
                "왼쪽 목록에서 문서를 먼저 선택하세요.")
            return
        doc = db.get_document(self._current_doc_id)
        if not doc or not doc.content:
            QMessageBox.warning(self,"내용 없음","텍스트가 없는 문서입니다."); return
        kws = db.get_keywords(self._current_doc_id)
        if not kws:
            QMessageBox.warning(self,"키워드 없음","분석 탭에서 먼저 분석을 실행하세요."); return

        dlg = QProgressDialog("퀴즈 생성 중…", None, 0, 0, self)
        dlg.setWindowTitle("퀴즈 생성"); dlg.setModal(True); dlg.show()
        QApplication.processEvents()

        self._gen_worker = QuizGenWorker(
            self._current_doc_id, doc.content, kws, quiz_type, self
        )
        self._gen_worker.finished.connect(lambda n, t: self._on_gen_done(n, t, dlg))
        self._gen_worker.error.connect(lambda e: (dlg.close(), QMessageBox.critical(self,"오류",e)))
        self._gen_worker.start()

    def _on_gen_done(self, count: int, quiz_type: str, dlg):
        dlg.close()
        if count == 0:
            QMessageBox.warning(self, "퀴즈 생성 실패",
                "퀴즈를 생성하지 못했습니다.\n"
                "키워드가 문서 문장에 포함되어 있는지 확인하세요.\n"
                "(분석 탭 → 분석 실행을 먼저 해주세요.)")
            return
        type_label = {"blank":"빈칸 채우기","ox":"OX","all":"전체"}.get(quiz_type,"")
        self._current_quiz_type = quiz_type   # 타입 기억
        row = self._doc_list.currentRow()
        self._refresh_docs()
        if row >= 0:
            self._doc_list.setCurrentRow(row)
        self._on_doc_selected(self._doc_list.currentRow())
        QMessageBox.information(self, "완료",
            f"{type_label} 퀴즈 {count}개 생성 완료!")

    # ── 퀴즈 시작 ───────────────────────────
    def _start_quiz(self):
        if not self._current_doc_id: return
        from database.models import QuizType
        # 마지막 생성 타입에 맞게 필터링
        qt = self._current_quiz_type
        if qt == "blank":
            quizzes = db.get_quizzes(self._current_doc_id, QuizType.BLANK)
        elif qt == "ox":
            quizzes = db.get_quizzes(self._current_doc_id, QuizType.OX)
        else:
            quizzes = db.get_quizzes(self._current_doc_id)
        if not quizzes:
            QMessageBox.warning(self,"퀴즈 없음","먼저 퀴즈를 생성하세요."); return
        import random; random.shuffle(quizzes)
        session = db.create_session(self._current_doc_id)
        self._session_id = session.id
        self._play_panel.start(quizzes)
        self._stack.setCurrentIndex(1)

    # ── 세션 완료 ───────────────────────────
    def _on_session_done(self, correct: int, total: int, wrong_kws: list):
        from quiz.evaluator import evaluate_session
        quizzes = db.get_quizzes(self._current_doc_id)
        answers = self._play_panel._answers
        report  = evaluate_session(
            self._session_id, self._current_doc_id, answers
        )
        bd = report.breakdown
        self._result_lbl.setText(
            f"채점 완료\n\n"
            f"정답: {correct} / {total}\n"
            f"퀴즈 점수: {bd.quiz_score:.1f}점\n"
            f"최종 점수: {bd.total_score:.1f}점  ({bd.grade})\n"
            f"{'✅ 통과' if bd.passed else '❌ 미통과'}"
        )
        self._load_history()
        self._stack.setCurrentIndex(2)

    def _on_exit_quiz(self):
        """퀴즈 중간 나가기 — 이력 탭으로 돌아간다."""
        self._load_history()
        self._stack.setCurrentIndex(3)   # 이력 탭

    def _retry(self):
        self._start_quiz()

    # ── 이력 ────────────────────────────────
    def _load_history(self):
        if not self._subject_id: return
        self._hist.setRowCount(0)
        docs = db.get_documents_by_subject(self._subject_id)
        for doc in docs:
            for s in db.get_sessions(doc.id):
                r = self._hist.rowCount(); self._hist.insertRow(r)
                date = s.completed_at.strftime("%m-%d %H:%M") if s.completed_at else "-"
                self._hist.setItem(r,0,QTableWidgetItem(date))
                self._hist.setItem(r,1,QTableWidgetItem(doc.title))
                self._hist.setItem(r,2,QTableWidgetItem(str(s.total_questions)))
                self._hist.setItem(r,3,QTableWidgetItem(str(s.correct_count)))
                self._hist.setItem(r,4,QTableWidgetItem(f"{s.score:.1f}점"))


# QLabel용 .also() 헬퍼 (인라인 스타일 설정)
def _also(self, fn):
    fn(self); return self
QLabel.also = _also
