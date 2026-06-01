"""
gui/session_tab.py
세션 관리 탭 — 과목별 히스토리 + 역색인 검색 결과
"""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QTableWidget, QTableWidgetItem, QHeaderView, QSplitter,
)
from utils.config import COLOR
from utils.logger import get_logger
from database import db_manager as db

logger = get_logger(__name__)
TP=COLOR['text_pri']; TS=COLOR['text_sec']; BD=COLOR['border']


class SessionTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._subject_id: Optional[int] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16); root.setSpacing(12)

        # 헤더
        title = QLabel("세션 관리")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{TP};")
        sub = QLabel("과목별 학습 이력 및 키워드 검색 결과를 확인하세요.")
        sub.setStyleSheet(f"font-size:13px;color:{TS};")
        root.addWidget(title); root.addWidget(sub)

        splitter = QSplitter(Qt.Orientation.Vertical)

        # 검색 결과 패널
        search_frame = QFrame()
        search_frame.setStyleSheet(f"QFrame{{background:{COLOR['bg_card']};border:1px solid {BD};border-radius:10px;}}")
        sl = QVBoxLayout(search_frame); sl.setContentsMargins(12,12,12,12); sl.setSpacing(8)
        sh = QHBoxLayout()
        stitle = QLabel("키워드 검색 결과")
        stitle.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        self._search_cnt = QLabel("결과 없음")
        self._search_cnt.setStyleSheet(f"font-size:12px;color:{TS};")
        sh.addWidget(stitle); sh.addStretch(); sh.addWidget(self._search_cnt)
        sl.addLayout(sh)

        self._search_tbl = QTableWidget(0, 3)
        self._search_tbl.setHorizontalHeaderLabels(["키워드", "문서 제목", "빈도"])
        self._search_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._search_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._search_tbl.verticalHeader().setVisible(False)
        sl.addWidget(self._search_tbl)

        # 이력 패널
        hist_frame = QFrame()
        hist_frame.setStyleSheet(f"QFrame{{background:{COLOR['bg_card']};border:1px solid {BD};border-radius:10px;}}")
        hl = QVBoxLayout(hist_frame); hl.setContentsMargins(12,12,12,12); hl.setSpacing(8)
        htitle = QLabel("학습 이력")
        htitle.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        hl.addWidget(htitle)

        self._hist_tbl = QTableWidget(0, 5)
        self._hist_tbl.setHorizontalHeaderLabels(["날짜", "문서", "점수", "통과", "누락 개념 수"])
        self._hist_tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self._hist_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._hist_tbl.verticalHeader().setVisible(False)
        hl.addWidget(self._hist_tbl)

        splitter.addWidget(search_frame)
        splitter.addWidget(hist_frame)
        splitter.setSizes([300, 300])
        root.addWidget(splitter, stretch=1)

    def set_subject(self, subject_id: int):
        self._subject_id = subject_id
        self._load_history()

    def show_search_results(self, results: list[dict], query: str):
        """역색인 검색 결과를 표에 표시한다."""
        self._search_tbl.setRowCount(0)
        for item in results:
            r = self._search_tbl.rowCount(); self._search_tbl.insertRow(r)
            self._search_tbl.setItem(r, 0, QTableWidgetItem(item.get("word", "")))
            self._search_tbl.setItem(r, 1, QTableWidgetItem(item.get("title", "")))
            self._search_tbl.setItem(r, 2, QTableWidgetItem(str(item.get("frequency", 0))))
        cnt = len(results)
        self._search_cnt.setText(f"'{query}' — {cnt}건")
        logger.debug("검색 결과 표시: query=%s  count=%d", query, cnt)

    def _load_history(self):
        if not self._subject_id:
            return
        self._hist_tbl.setRowCount(0)
        import json
        docs = db.get_documents_by_subject(self._subject_id)
        for doc in docs:
            scores = db.get_scores(doc.id)
            for sc in scores:
                r = self._hist_tbl.rowCount(); self._hist_tbl.insertRow(r)
                date_str = sc.measured_at.strftime("%Y-%m-%d %H:%M") if sc.measured_at else "-"
                try:
                    missing = json.loads(sc.missing_concepts)
                    missing_cnt = str(len(missing))
                except Exception:
                    missing_cnt = "0"
                self._hist_tbl.setItem(r, 0, QTableWidgetItem(date_str))
                self._hist_tbl.setItem(r, 1, QTableWidgetItem(doc.title))
                self._hist_tbl.setItem(r, 2, QTableWidgetItem(f"{sc.total_score:.1f}점"))
                from utils.config import SCORE_PASS_THRESHOLD
                passed = "통과" if sc.total_score >= SCORE_PASS_THRESHOLD else "미통과"
                self._hist_tbl.setItem(r, 3, QTableWidgetItem(passed))
                self._hist_tbl.setItem(r, 4, QTableWidgetItem(missing_cnt))
