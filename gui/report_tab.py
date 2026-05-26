"""
gui/report_tab.py
리포트 탭 — matplotlib 차트 임베딩 + 누락 개념 목록 + 점수 요약
"""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QScrollArea, QSplitter, QListWidget, QListWidgetItem,
    QComboBox, QTabWidget, QSizePolicy,
)
from utils.config import COLOR, SCORE_PASS_THRESHOLD
from utils.logger import get_logger
from database import db_manager as db

logger = get_logger(__name__)
A=COLOR['primary']; AH=COLOR['primary_h']
TP=COLOR['text_pri']; TS=COLOR['text_sec']; BD=COLOR['border']
OK=COLOR['success']; ER=COLOR['danger']; WN=COLOR['warning']
BG=COLOR['bg_card']; BI=COLOR['bg_input']


# ── matplotlib Qt 캔버스 ────────────────────────
def _make_canvas(fig):
    """matplotlib Figure를 PyQt6 위젯으로 변환한다."""
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
    canvas = FigureCanvasQTAgg(fig)
    canvas.setStyleSheet("background:transparent;")
    canvas.setMinimumHeight(420)   # 차트 잘림 방지
    return canvas


# ── 점수 카드 위젯 ───────────────────────────────
class ScoreCard(QFrame):
    def __init__(self, label: str, value: str, color: str, parent=None):
        super().__init__(parent)
        self.setStyleSheet(
            f"QFrame{{background:{BI};border:1px solid {BD};"
            f"border-radius:10px;}}"
        )
        self.setFixedHeight(80)
        lay = QVBoxLayout(self); lay.setContentsMargins(14,10,14,10); lay.setSpacing(4)
        lbl = QLabel(label)
        lbl.setStyleSheet(f"font-size:11px;color:{TS};")
        val = QLabel(value)
        val.setStyleSheet(f"font-size:22px;font-weight:700;color:{color};")
        lay.addWidget(lbl); lay.addWidget(val)


# ── 리포트 탭 ────────────────────────────────────
class ReportTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._subject_id: Optional[int] = None
        self._current_doc_id: Optional[int] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20,16,20,16); root.setSpacing(10)

        # 헤더
        hdr = QHBoxLayout()
        title = QLabel("학습 리포트")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{TP};")
        sub = QLabel("챕터별 이해도 점수, 누락 개념, 점수 추이를 확인하세요.")
        sub.setStyleSheet(f"font-size:13px;color:{TS};")
        tc = QVBoxLayout(); tc.setSpacing(2); tc.addWidget(title); tc.addWidget(sub)
        hdr.addLayout(tc); hdr.addStretch()

        # 문서 선택 콤보
        self._doc_combo = QComboBox()
        self._doc_combo.setFixedWidth(220)
        self._doc_combo.setStyleSheet(
            f"QComboBox{{background:{BI};color:{TP};"
            f"border:1.5px solid {BD};border-radius:8px;"
            f"padding:6px 12px;font-size:13px;}}"
            f"QComboBox:focus{{border-color:{A};}}"
            f"QComboBox QAbstractItemView{{background:{BG};"
            f"color:{TP};selection-background-color:{A};}}"
        )
        self._doc_combo.currentIndexChanged.connect(self._on_doc_changed)

        self._refresh_btn = QPushButton("새로고침")
        self._refresh_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{A};"
            f"border:1.5px solid {A};border-radius:8px;"
            f"padding:7px 16px;font-size:12px;}}"
            f"QPushButton:hover{{background:rgba(91,95,217,0.1);}}"
        )
        self._refresh_btn.clicked.connect(self._refresh)
        hdr.addWidget(self._doc_combo); hdr.addWidget(self._refresh_btn)
        root.addLayout(hdr)

        # 점수 카드 행 — QScrollArea로 감싸 가로 스크롤 지원
        card_scroll = QScrollArea()
        card_scroll.setWidgetResizable(True)
        card_scroll.setFixedHeight(96)
        card_scroll.setHorizontalScrollBarPolicy(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        card_scroll.setVerticalScrollBarPolicy(
            __import__("PyQt6.QtCore", fromlist=["Qt"]).Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        card_scroll.setStyleSheet(
            "QScrollArea{border:none;background:transparent;}"
            f"QScrollBar:horizontal{{background:{BI};height:4px;border-radius:2px;}}"
            f"QScrollBar::handle:horizontal{{background:{A};border-radius:2px;}}"
        )
        self._card_widget = QWidget()
        self._card_widget.setStyleSheet("background:transparent;")
        self._card_row = QHBoxLayout(self._card_widget)
        self._card_row.setSpacing(10)
        self._card_row.setContentsMargins(0,0,0,0)
        # 초기 카드 4개
        for label, value, color in [
            ("최종 점수","--",TS),("퀴즈 점수","--",TS),
            ("커버리지","--",TS),("총 세션","--",A),
        ]:
            self._card_row.addWidget(ScoreCard(label, value, color))
        card_scroll.setWidget(self._card_widget)
        root.addWidget(card_scroll)

        # 메인 스플리터: 차트(좌) + 누락개념(우)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 차트 탭
        left = QFrame()
        left.setStyleSheet(f"QFrame{{background:{BG};border:1px solid {BD};border-radius:10px;}}")
        ll = QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(8)

        self._chart_tabs = QTabWidget()
        self._chart_tabs.setStyleSheet(
            f"QTabWidget::pane{{background:{BI};border:1px solid {BD};border-radius:8px;}}"
            f"QTabBar::tab{{background:{BI};color:{TS};border:none;"
            f"padding:7px 16px;border-radius:6px 6px 0 0;margin-right:2px;}}"
            f"QTabBar::tab:selected{{background:{BG};color:{TP};"
            f"border-top:2px solid {A};}}"
        )

        # 차트 페이지들 (스크롤 가능)
        self._dashboard_page = self._make_scroll_page()
        self._history_page   = self._make_scroll_page()
        self._breakdown_page = self._make_scroll_page()
        self._chapter_page   = self._make_scroll_page()

        self._chart_tabs.addTab(self._dashboard_page, "  종합  ")
        self._chart_tabs.addTab(self._history_page,   "  추이  ")
        self._chart_tabs.addTab(self._breakdown_page, "  세부 내역  ")
        self._chart_tabs.addTab(self._chapter_page,   "  챕터별  ")
        ll.addWidget(self._chart_tabs)

        # 오른쪽: 누락 개념 목록
        right = QFrame()
        right.setFixedWidth(230)
        right.setStyleSheet(f"QFrame{{background:{BG};border:1px solid {BD};border-radius:10px;}}")
        rl = QVBoxLayout(right); rl.setContentsMargins(12,12,12,12); rl.setSpacing(8)

        miss_hdr = QHBoxLayout()
        miss_title = QLabel("누락 개념")
        miss_title.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        self._miss_cnt = QLabel("0개")
        self._miss_cnt.setStyleSheet(f"font-size:12px;color:{ER};")
        miss_hdr.addWidget(miss_title); miss_hdr.addStretch(); miss_hdr.addWidget(self._miss_cnt)
        rl.addLayout(miss_hdr)

        self._miss_list = QListWidget()
        self._miss_list.setStyleSheet(
            f"QListWidget{{background:{BI};border:1px solid {BD};"
            f"border-radius:8px;padding:4px;}}"
            f"QListWidget::item{{padding:7px 10px;border-radius:6px;"
            f"color:{TP};}}"
            f"QListWidget::item:selected{{background:rgba(239,68,68,0.15);"
            f"color:{ER};}}"
        )
        rl.addWidget(self._miss_list, stretch=1)

        miss_note = QLabel("⚠  자주 틀린 개념과\n누락된 키워드 목록입니다.")
        miss_note.setWordWrap(True)
        miss_note.setStyleSheet(
            f"font-size:11px;color:{TS};"
            f"background:rgba(239,68,68,0.07);"
            "border-radius:6px;padding:8px;"
        )
        rl.addWidget(miss_note)

        splitter.addWidget(left); splitter.addWidget(right)
        splitter.setSizes([700, 230])
        root.addWidget(splitter, stretch=1)

        # 안내 배너 (데이터 없을 때)
        self._no_data = QLabel(
            "📊  퀴즈를 풀고 나면\n이해도 리포트가 여기에 표시됩니다."
        )
        self._no_data.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._no_data.setStyleSheet(
            f"font-size:14px;color:{TS};"
            f"background:rgba(91,95,217,0.07);"
            "border-radius:10px;padding:30px;"
        )
        self._no_data.setVisible(False)

    def _make_scroll_page(self) -> QScrollArea:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea{{border:none;background:{BI};}}")
        inner = QWidget()
        inner.setStyleSheet(f"background:{BI};")
        inner.setLayout(QVBoxLayout())
        inner.layout().setContentsMargins(8,8,8,8)
        scroll.setWidget(inner)
        return scroll

    # ── 외부 API ────────────────────────────
    def set_subject(self, subject_id: int):
        self._subject_id = subject_id
        self._refresh_combo()

    def _refresh_combo(self):
        if not self._subject_id: return
        self._doc_combo.blockSignals(True)
        self._doc_combo.clear()
        docs = db.get_documents_by_subject(self._subject_id)
        for doc in docs:
            self._doc_combo.addItem(doc.title, doc.id)
        self._doc_combo.blockSignals(False)
        if docs:
            self._on_doc_changed(0)

    def _on_doc_changed(self, idx: int):
        doc_id = self._doc_combo.itemData(idx)
        if doc_id:
            self._current_doc_id = doc_id
            self._refresh()

    def _refresh(self):
        if not self._current_doc_id: return
        from reports.report_gen import collect_report
        data = collect_report(self._current_doc_id)
        self._update_cards(data)
        self._update_missing(data)
        self._update_charts(data)

    # ── 카드 업데이트 ───────────────────────
    def _update_cards(self, data):
        """점수 카드를 전체 교체한다 (중복 방지)."""
        score_color = OK if data.total_score >= SCORE_PASS_THRESHOLD else ER

        new_cards = [
            ("최종 점수",
             f"{data.total_score:.0f}점 ({data.grade})" if data.has_data else "--",
             score_color),
            ("퀴즈 점수",
             f"{data.quiz_score:.0f}점" if data.has_data else "--",
             OK if data.quiz_score >= 60 else ER),
            ("커버리지",
             f"{data.coverage_score:.0f}점" if data.has_data else "--",
             OK if data.coverage_score >= 60 else WN),
            ("키워드 밀도",
             f"{data.keyword_density:.0f}점" if data.has_data else "--",
             OK if data.keyword_density >= 60 else WN),
            ("총 세션",
             f"{data.session_count}회", A),
            ("최고 점수",
             f"{data.best_score:.0f}점" if data.has_data else "--",
             OK if data.best_score >= 60 else ER),
        ]

        # 기존 카드 전체 제거 (setParent(None)으로 즉시 삭제)
        while self._card_row.count():
            item = self._card_row.takeAt(0)
            if item and item.widget():
                item.widget().setParent(None)

        # 새 카드 추가
        for label, value, color in new_cards:
            self._card_row.addWidget(ScoreCard(label, value, color))
        self._card_row.addStretch()

    # ── 누락 개념 ───────────────────────────
    def _update_missing(self, data):
        self._miss_list.clear()
        for word in data.missing_words:
            item = QListWidgetItem(f"✗  {word}")
            item.setForeground(
                __import__("PyQt6.QtGui", fromlist=["QColor"]).QColor(ER)
            )
            self._miss_list.addItem(item)
        self._miss_cnt.setText(f"{len(data.missing_words)}개")

    # ── 차트 업데이트 ───────────────────────
    def _update_charts(self, data):
        from reports.chart_builder import (
            build_dashboard, build_score_history,
            build_score_breakdown, build_coverage_donut, build_chapter_bar,
        )
        import matplotlib.pyplot as plt

        def _set_chart(page: QScrollArea, fig):
            inner = page.widget()
            lay   = inner.layout()
            # 기존 위젯 제거
            while lay.count():
                item = lay.takeAt(0)
                if item.widget(): item.widget().deleteLater()
            canvas = _make_canvas(fig)
            lay.addWidget(canvas)
            plt.close(fig)

        # 종합
        _set_chart(self._dashboard_page, build_dashboard(
            data.dates, data.history_scores,
            data.quiz_score, data.coverage_score,
            data.keyword_density, data.total_score,
            data.covered_count, data.partial_count, data.missing_count,
            data.chapters, data.chapter_scores,
        ))
        # 추이
        _set_chart(self._history_page,
                   build_score_history(data.dates, data.history_scores))
        # 세부
        _set_chart(self._breakdown_page,
                   build_score_breakdown(
                       data.quiz_score, data.coverage_score,
                       data.keyword_density, data.total_score))
        # 챕터
        _set_chart(self._chapter_page,
                   build_chapter_bar(data.chapters, data.chapter_scores))
