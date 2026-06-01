"""
gui/main_window.py
메인 윈도우 — 사이드바(과목 관리) + 5탭 레이아웃 + 메뉴바 + 상태바
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QAction, QFont, QIcon, QKeySequence
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QSplitter, QTabWidget, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QLineEdit, QFrame,
    QStatusBar, QMessageBox, QInputDialog, QSizePolicy,
)

from utils.config import (
    APP_NAME, APP_VERSION, WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT,
    WINDOW_TITLE, COLOR,
)
from utils.logger import get_logger
from database import db_manager as db
from database.models import Subject

from gui.upload_tab   import UploadTab
from gui.analysis_tab import AnalysisTab
from gui.quiz_tab     import QuizTab
from gui.report_tab   import ReportTab
from gui.session_tab  import SessionTab

logger = get_logger(__name__)


# ──────────────────────────────────────────────
# 사이드바 — 과목 목록 + 검색
# ──────────────────────────────────────────────


# ──────────────────────────────────────────────
# 재클릭 선택 해제를 지원하는 QListWidget
# ──────────────────────────────────────────────
class _ToggleListWidget(QListWidget):
    """
    이미 선택된 항목을 다시 클릭하면 선택을 해제하는 QListWidget.
    mousePressEvent에서 클릭 전 상태를 미리 기록하여
    신호 타이밍 문제 없이 안정적으로 동작한다.
    """
    toggleRequested = pyqtSignal()   # 재클릭 감지 시 발생

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pre_selected = False   # 클릭 직전 선택 상태

    def mousePressEvent(self, event):
        """마우스를 누르기 직전에 선택 상태를 기록한다."""
        item = self.itemAt(event.pos())
        # 클릭 전 이미 선택된 항목인지 기록
        self._pre_selected = (item is not None and item.isSelected())
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        """마우스를 뗄 때 재클릭이면 선택 해제 신호를 보낸다."""
        item = self.itemAt(event.pos())
        super().mouseReleaseEvent(event)
        if item is not None and self._pre_selected:
            # 클릭 전에 선택돼 있던 항목을 다시 클릭 → 해제
            self.toggleRequested.emit()
        self._pre_selected = False

class SubjectSidebar(QWidget):
    """왼쪽 사이드바: 과목 목록, 추가/삭제, 키워드 검색."""

    subjectSelected  = pyqtSignal(int, str)   # (subject_id, name)
    subjectDeleted   = pyqtSignal(int)
    searchRequested  = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._subjects: list[Subject] = []
        self.setFixedWidth(240)
        self._build_ui()
        self.refresh_subjects()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 16, 12, 16)
        root.setSpacing(10)

        # 제목
        title = QLabel("과목 관리")
        title.setStyleSheet(
            f"font-size: 15px; font-weight: 700; color: {COLOR['text_pri']};"
        )
        root.addWidget(title)

        # 검색창
        self._search = QLineEdit()
        self._search.setPlaceholderText("키워드 검색…")
        self._search.setToolTip("역색인 기반 키워드로 문서 검색")
        self._search.returnPressed.connect(self._on_search)
        root.addWidget(self._search)

        # 과목 리스트 — 재클릭으로 선택 해제 지원
        self._list = _ToggleListWidget()
        self._list.setToolTip("과목을 선택하면 해당 자료만 표시됩니다\n같은 항목 다시 클릭 시 선택 해제")
        self._list.currentRowChanged.connect(self._on_select)
        self._list.toggleRequested.connect(self._on_toggle_deselect)
        root.addWidget(self._list, stretch=1)

        # 추가 / 삭제 버튼
        btn_row = QHBoxLayout()
        btn_row.setSpacing(6)

        self._add_btn = QPushButton("+ 과목 추가")
        self._add_btn.setToolTip("새 과목을 추가합니다")
        self._add_btn.clicked.connect(self._add_subject)
        self._add_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLOR['primary']};
                color: #fff; border: none;
                border-radius: 7px; font-size: 12px;
                font-weight: 600; padding: 7px 0;
            }}
            QPushButton:hover {{ background: {COLOR['primary_h']}; }}
        """)

        self._del_btn = QPushButton("삭제")
        self._del_btn.setToolTip("선택한 과목과 모든 자료를 삭제합니다")
        self._del_btn.setEnabled(False)
        self._del_btn.setProperty("danger", "true")
        self._del_btn.clicked.connect(self._delete_subject)
        self._del_btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                color: {COLOR['danger']};
                border: 1.5px solid {COLOR['danger']};
                border-radius: 7px; font-size: 12px;
                padding: 7px 0;
            }}
            QPushButton:hover {{
                background: rgba(239,68,68,0.12);
            }}
            QPushButton:disabled {{
                color: #5A5A7A; border-color: #2E2E4A;
            }}
        """)

        btn_row.addWidget(self._add_btn, 2)
        btn_row.addWidget(self._del_btn, 1)
        root.addLayout(btn_row)

        # 과목 수 표시
        self._count_lbl = QLabel("과목 0개")
        self._count_lbl.setStyleSheet(
            f"font-size: 11px; color: {COLOR['text_sec']};"
        )
        self._count_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._count_lbl)

    # ── 과목 목록 갱신 ──────────────────────
    def refresh_subjects(self):
        self._subjects = db.get_all_subjects()
        self._list.clear()
        for s in self._subjects:
            stats = db.get_subject_stats(s.id)
            item = QListWidgetItem(
                f"{s.name}\n  문서 {stats['document_count']}개  "
                f"평균 {stats['avg_score']:.0f}점"
            )
            item.setData(Qt.ItemDataRole.UserRole, s.id)
            self._list.addItem(item)
        self._count_lbl.setText(f"과목 {len(self._subjects)}개")
        self._del_btn.setEnabled(False)
        logger.debug("사이드바 갱신: %d개 과목", len(self._subjects))

    # ── 이벤트 핸들러 ───────────────────────
    def _on_item_clicked(self, item):
        """이미 선택된 항목을 다시 클릭하면 선택을 해제한다."""
        from PyQt6.QtWidgets import QListWidgetItem
        row = self._list.row(item)
        # 같은 행을 클릭했고 이미 선택 상태이면 해제
        if row == self._list.currentRow() and item.isSelected():
            self._list.clearSelection()
            self._list.setCurrentRow(-1)
            self._del_btn.setEnabled(False)
            self.subjectSelected.emit(-1, "")   # 선택 해제 알림

    def _on_toggle_deselect(self):
        """_ToggleListWidget 재클릭 감지 시 호출 — 선택 해제."""
        self._list.clearSelection()
        self._list.setCurrentRow(-1)
        self._del_btn.setEnabled(False)
        self.subjectSelected.emit(-1, "")

    def _on_select(self, row: int):
        if row < 0 or row >= len(self._subjects):
            self._del_btn.setEnabled(False)
            return
        s = self._subjects[row]
        self._del_btn.setEnabled(True)
        self.subjectSelected.emit(s.id, s.name)
        logger.debug("과목 선택: id=%d  name=%s", s.id, s.name)

    def _on_search(self):
        query = self._search.text().strip()
        if query:
            self.searchRequested.emit(query)

    def _add_subject(self):
        name, ok = QInputDialog.getText(
            self, "과목 추가", "과목 이름을 입력하세요:"
        )
        if not ok or not name.strip():
            return
        desc, ok2 = QInputDialog.getText(
            self, "과목 추가", "설명 (선택사항):"
        )
        try:
            db.create_subject(name.strip(), desc.strip() if ok2 else "")
            self.refresh_subjects()
            logger.info("과목 추가: %s", name)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"과목 추가 실패:\n{e}")

    def _delete_subject(self):
        row = self._list.currentRow()
        if row < 0:
            return
        s = self._subjects[row]
        reply = QMessageBox.question(
            self, "과목 삭제",
            f"'{s.name}' 과목과 모든 자료를 삭제할까요?\n이 작업은 되돌릴 수 없습니다.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            db.delete_subject(s.id)
            self.subjectDeleted.emit(s.id)
            self.refresh_subjects()
            logger.info("과목 삭제: id=%d  name=%s", s.id, s.name)
        except Exception as e:
            QMessageBox.critical(self, "오류", f"삭제 실패:\n{e}")

    # ── 외부 API ─────────────────────────────
    def current_subject_id(self) -> Optional[int]:
        row = self._list.currentRow()
        if 0 <= row < len(self._subjects):
            return self._subjects[row].id
        return None


# ──────────────────────────────────────────────
# 메인 윈도우
# ──────────────────────────────────────────────
class MainWindow(QMainWindow):
    """앱 최상위 윈도우."""

    def __init__(self):
        super().__init__()
        self._current_subject_id: Optional[int] = None
        self._setup_window()
        self._apply_stylesheet()
        self._build_menu()
        self._build_ui()
        self._connect_signals()
        self._start_status_clock()
        logger.info("메인 윈도우 초기화 완료")

    # ── 기본 설정 ────────────────────────────
    def _setup_window(self):
        self.setWindowTitle(WINDOW_TITLE)
        self.setMinimumSize(WINDOW_MIN_WIDTH, WINDOW_MIN_HEIGHT)
        self.resize(1280, 800)
        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("준비")

    def _apply_stylesheet(self):
        qss_path = Path(__file__).parent / "styles.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text(encoding="utf-8"))
        else:
            logger.warning("styles.qss 파일을 찾을 수 없습니다: %s", qss_path)

    # ── 메뉴바 ───────────────────────────────
    def _build_menu(self):
        menu = self.menuBar()

        # 파일
        file_menu = menu.addMenu("파일(&F)")

        new_subject = QAction("새 과목 추가", self)
        new_subject.setShortcut(QKeySequence("Ctrl+N"))
        new_subject.triggered.connect(lambda: self._sidebar._add_subject())
        file_menu.addAction(new_subject)

        file_menu.addSeparator()

        quit_action = QAction("종료", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # 보기
        view_menu = menu.addMenu("보기(&V)")

        refresh_action = QAction("새로고침", self)
        refresh_action.setShortcut(QKeySequence("F5"))
        refresh_action.triggered.connect(self._refresh_all)
        view_menu.addAction(refresh_action)

        # 도움말
        help_menu = menu.addMenu("도움말(&H)")

        about_action = QAction(f"{APP_NAME} 정보", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    # ── 메인 UI 구성 ─────────────────────────
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ── 사이드바 구분선 ──
        self._sidebar = SubjectSidebar()
        sidebar_frame = QFrame()
        sidebar_frame.setStyleSheet(
            f"background-color: {COLOR['bg_card']};"
            f"border-right: 1px solid {COLOR['border']};"
        )
        sidebar_layout = QVBoxLayout(sidebar_frame)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.addWidget(self._sidebar)

        # ── 탭 위젯 ──
        self._tabs = QTabWidget()
        self._tabs.setDocumentMode(False)

        # 탭 생성
        self._upload_tab   = UploadTab()
        self._analysis_tab = AnalysisTab()
        self._quiz_tab     = QuizTab()
        self._report_tab   = ReportTab()
        self._session_tab  = SessionTab()

        self._tabs.addTab(self._upload_tab,   "  업로드  ")
        self._tabs.addTab(self._analysis_tab, "  분석    ")
        self._tabs.addTab(self._quiz_tab,     "  퀴즈    ")
        self._tabs.addTab(self._report_tab,   "  리포트  ")
        self._tabs.addTab(self._session_tab,  "  세션 관리")

        # 탭 콘텐츠 영역 패딩
        content_frame = QFrame()
        content_frame.setStyleSheet(f"background-color: {COLOR['bg_dark']};")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(16, 12, 16, 12)
        content_layout.addWidget(self._tabs)

        main_layout.addWidget(sidebar_frame)
        main_layout.addWidget(content_frame, stretch=1)

    # ── 시그널 연결 ──────────────────────────
    def _connect_signals(self):
        # 사이드바
        self._sidebar.subjectSelected.connect(self._on_subject_selected)
        self._sidebar.subjectDeleted.connect(self._on_subject_deleted)
        self._sidebar.searchRequested.connect(self._on_search)

        # 업로드 탭
        self._upload_tab.pdfReady.connect(self._on_pdf_ready)
        self._upload_tab.textReady.connect(self._on_text_ready)

        # 탭 전환
        self._tabs.currentChanged.connect(self._on_tab_changed)

    # ── 이벤트 핸들러 ────────────────────────
    def _on_subject_selected(self, subject_id: int, name: str):
        if subject_id == -1:   # 선택 해제
            self._current_subject_id = None
            self.statusBar().showMessage("과목 선택 해제")
            return
        self._current_subject_id = subject_id
        self._analysis_tab.set_subject(subject_id)
        self._quiz_tab.set_subject(subject_id)
        self._report_tab.set_subject(subject_id)
        self._session_tab.set_subject(subject_id)
        self.statusBar().showMessage(f"선택된 과목: {name}")
        logger.debug("과목 선택 → 탭 동기화: id=%d", subject_id)

    def _on_subject_deleted(self, subject_id: int):
        self._current_subject_id = None
        self._refresh_all()
        self.statusBar().showMessage("과목이 삭제되었습니다.")

    def _on_search(self, query: str):
        """사이드바 검색창 → 키워드 DB 직접 조회."""
        q = query.strip().lower()
        if not q:
            return

        # 과목이 선택된 경우 해당 과목만, 아니면 전체 과목 검색
        if self._current_subject_id:
            docs = db.get_documents_by_subject(self._current_subject_id)
        else:
            subjects = db.get_all_subjects()
            docs = []
            for s in subjects:
                docs.extend(db.get_documents_by_subject(s.id))

        results: list[dict] = []
        seen: set[tuple] = set()
        for doc in docs:
            keywords = db.get_keywords(doc.id)
            for kw in keywords:
                if q in kw.word.lower():
                    key = (kw.word, doc.id)
                    if key not in seen:
                        seen.add(key)
                        results.append({
                            "word":      kw.word,
                            "title":     doc.title,
                            "frequency": kw.frequency,
                        })

        # 빈도 내림차순 정렬
        results.sort(key=lambda x: x["frequency"], reverse=True)

        self._session_tab.show_search_results(results, query)
        self._tabs.setCurrentWidget(self._session_tab)
        self.statusBar().showMessage(f"'{query}' 검색 결과: {len(results)}건")

    def _on_tab_changed(self, index: int):
        tab_names = ["업로드", "분석", "퀴즈", "리포트", "세션 관리"]
        self.statusBar().showMessage(f"{tab_names[index]} 탭")
        # 탭 전환 시 문서 목록 최신화
        sid = self._current_subject_id
        if sid:
            if index == 2:   # 퀴즈 탭
                self._quiz_tab.set_subject(sid)
            elif index == 3:  # 리포트 탭
                self._report_tab.set_subject(sid)
            elif index == 4:  # 세션 탭
                self._session_tab.set_subject(sid)

    def _on_pdf_ready(self, path: str):
        if not self._current_subject_id:
            QMessageBox.warning(
                self, "과목 미선택",
                "왼쪽 사이드바에서 과목을 먼저 선택하거나 추가해 주세요."
            )
            return
        self.statusBar().showMessage(f"PDF 분석 준비: {Path(path).name}")
        self._analysis_tab.load_pdf(path, self._current_subject_id)
        self._tabs.setCurrentWidget(self._analysis_tab)

    def _on_text_ready(self, content: str, label: str):
        if not self._current_subject_id:
            QMessageBox.warning(
                self, "과목 미선택",
                "왼쪽 사이드바에서 과목을 먼저 선택하거나 추가해 주세요."
            )
            return
        self.statusBar().showMessage(f"텍스트 분석 준비: {label}")
        self._analysis_tab.load_text(content, label, self._current_subject_id)
        self._tabs.setCurrentWidget(self._analysis_tab)

    # ── 새로고침 ─────────────────────────────
    def _refresh_all(self):
        self._sidebar.refresh_subjects()
        subject_id = self._current_subject_id
        if subject_id:
            self._analysis_tab.set_subject(subject_id)
            self._report_tab.set_subject(subject_id)
            self._session_tab.set_subject(subject_id)

    # ── 상태바 시계 ──────────────────────────
    def _start_status_clock(self):
        from datetime import datetime
        self._clock = QTimer(self)
        self._clock.timeout.connect(
            lambda: self.statusBar().showMessage(
                datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            ) if self.statusBar().currentMessage().count("-") == 2
            else None
        )

    # ── 정보 다이얼로그 ──────────────────────
    def _show_about(self):
        QMessageBox.information(
            self,
            f"{APP_NAME} 정보",
            f"{APP_NAME}\n버전: {APP_VERSION}\n\n"
            "PDF·TXT 기반 핵심 개념 추출 및\n이해도 측정 데스크탑 앱\n\n"
            "완전 오프라인 동작 | 한국어·영어 지원\n"
            "20222032 오은석",
        )

    # ── 종료 이벤트 ──────────────────────────
    def closeEvent(self, event):
        reply = QMessageBox.question(
            self, "종료 확인", "앱을 종료할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            logger.info("앱 종료")
            event.accept()
        else:
            event.ignore()
