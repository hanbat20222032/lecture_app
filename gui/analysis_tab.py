"""
gui/analysis_tab.py
분석 탭 — 문서 목록 + 키워드 결과 표시
Phase 4에서 TF-IDF / TextRank 엔진 연결 예정
"""
from __future__ import annotations
from typing import Optional
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QSplitter, QMessageBox, QTabWidget,
    QTextEdit,
)
from utils.config import COLOR
from utils.logger import get_logger
from database import db_manager as db
from database.models import Document, SourceType

logger = get_logger(__name__)
A=COLOR['primary']; AH=COLOR['primary_h']; TP=COLOR['text_pri']; TS=COLOR['text_sec']; BD=COLOR['border']
ER=COLOR['danger']


class AnalysisTab(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._subject_id: Optional[int] = None
        self._current_doc: Optional[Document] = None
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(12)

        # 헤더
        hdr = QHBoxLayout()
        title = QLabel("콘텐츠 분석")
        title.setStyleSheet(f"font-size:20px;font-weight:700;color:{TP};")
        sub = QLabel("업로드된 자료의 핵심 키워드를 확인하고 관리하세요.")
        sub.setStyleSheet(f"font-size:13px;color:{TS};")
        tc = QVBoxLayout(); tc.setSpacing(2)
        tc.addWidget(title); tc.addWidget(sub)
        hdr.addLayout(tc); hdr.addStretch()
        self._analyze_btn = QPushButton("  분석 실행  ")
        self._analyze_btn.setEnabled(False)
        self._analyze_btn.clicked.connect(self._run_analysis)
        hdr.addWidget(self._analyze_btn)
        root.addLayout(hdr)

        # 스플리터: 문서 목록(좌) + 키워드 결과(우)
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # 왼쪽: 문서 목록
        left = QFrame()
        left.setStyleSheet(f"QFrame{{background:{COLOR['bg_card']};border:1px solid {BD};border-radius:10px;}}")
        ll = QVBoxLayout(left); ll.setContentsMargins(12,12,12,12); ll.setSpacing(8)
        doc_hdr = QLabel("문서 목록")
        doc_hdr.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        self._doc_list = QListWidget()
        self._doc_list.setToolTip("문서를 선택하세요. 같은 항목 클릭 시 선택 해제")
        self._doc_list.currentRowChanged.connect(self._on_doc_selected)
        ll.addWidget(doc_hdr); ll.addWidget(self._doc_list)

        # 문서 삭제 버튼
        del_btn = QPushButton("문서 삭제")
        del_btn.setStyleSheet(f"QPushButton{{background:transparent;color:{COLOR['danger']};border:1px solid {COLOR['danger']};border-radius:7px;font-size:12px;padding:6px;}}QPushButton:hover{{background:rgba(239,68,68,0.1);}}")
        del_btn.clicked.connect(self._delete_doc)
        ll.addWidget(del_btn)

        # 오른쪽: 탭 위젯 (키워드 / 문장)
        right = QTabWidget()
        right.setStyleSheet(
            f"QTabWidget::pane{{background:{COLOR['bg_card']};border:1px solid {BD};"
            f"border-radius:10px;}}"
            f"QTabBar::tab{{background:{COLOR['bg_card']};color:{TS};"
            f"border:1px solid {BD};border-bottom:none;"
            f"border-top-left-radius:8px;border-top-right-radius:8px;"
            f"padding:6px 18px;font-size:13px;}}"
            f"QTabBar::tab:selected{{background:{COLOR['bg_card']};color:{TP};"
            f"font-weight:600;border-bottom:2px solid {A};}}"
        )

        # ── 탭1: 핵심 키워드 ──────────────────────────────
        kw_tab = QFrame()
        rl = QVBoxLayout(kw_tab); rl.setContentsMargins(12,12,12,12); rl.setSpacing(8)

        kw_hdr = QHBoxLayout()
        kw_title = QLabel("핵심 키워드")
        kw_title.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        self._kw_count = QLabel("0개")
        self._kw_count.setStyleSheet(f"font-size:12px;color:{TS};")
        kw_hdr.addWidget(kw_title); kw_hdr.addStretch(); kw_hdr.addWidget(self._kw_count)
        rl.addLayout(kw_hdr)

        self._kw_table = QTableWidget(0, 4)
        self._kw_table.setHorizontalHeaderLabels(["키워드", "TF-IDF", "TextRank", "빈도"])
        self._kw_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self._kw_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self._kw_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._kw_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self._kw_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._kw_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._kw_table.verticalHeader().setVisible(False)
        rl.addWidget(self._kw_table)

        kw_btns = QHBoxLayout()
        self._add_kw_btn = QPushButton("+ 키워드 추가")
        self._add_kw_btn.setEnabled(False)
        self._add_kw_btn.clicked.connect(self._add_keyword)
        self._del_kw_btn = QPushButton("선택 제거")
        self._del_kw_btn.setEnabled(False)
        self._del_kw_btn.clicked.connect(self._remove_keyword)
        for b in (self._add_kw_btn, self._del_kw_btn): kw_btns.addWidget(b)
        rl.addLayout(kw_btns)

        self._phase_banner = QLabel(
            "⚙️  Phase 4에서 TF-IDF + TextRank 엔진이 연결되면\n"
            "       자동으로 키워드가 추출됩니다."
        )
        self._phase_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._phase_banner.setStyleSheet(
            f"font-size:13px;color:{TS};"
            f"background:rgba(91,95,217,0.07);"
            "border-radius:8px;padding:20px;"
        )
        rl.addWidget(self._phase_banner)

        right.addTab(kw_tab, "핵심 키워드")

        # ── 탭2: 추출 문장 ────────────────────────────────
        sent_tab = QFrame()
        sl = QVBoxLayout(sent_tab); sl.setContentsMargins(12,12,12,12); sl.setSpacing(8)

        sent_hdr = QHBoxLayout()
        sent_title = QLabel("추출 문장")
        sent_title.setStyleSheet(f"font-size:13px;font-weight:600;color:{TP};")
        self._sent_count = QLabel("0개")
        self._sent_count.setStyleSheet(f"font-size:12px;color:{TS};")
        sent_hdr.addWidget(sent_title); sent_hdr.addStretch()
        sent_hdr.addWidget(self._sent_count)
        sl.addLayout(sent_hdr)

        # 상단: 문장 목록 (클릭 선택)
        self._sent_list = QListWidget()
        self._sent_list.setWordWrap(True)
        self._sent_list.setSpacing(2)
        self._sent_list.setStyleSheet(
            f"QListWidget{{background:{COLOR['bg_card']};border:none;}}"
            f"QListWidget::item{{padding:8px 6px;border-bottom:1px solid {BD};"
            f"color:{TP};font-size:13px;}}"
            f"QListWidget::item:selected{{background:rgba(91,95,217,0.12);"
            f"color:{TP};}}"
        )
        self._sent_list.currentItemChanged.connect(self._on_sent_selected)
        sl.addWidget(self._sent_list, stretch=3)

        # 하단: 편집 패널
        edit_frame = QFrame()
        edit_frame.setStyleSheet(
            f"QFrame{{background:{COLOR['bg_input']};border:1px solid {BD};"
            f"border-radius:8px;}}"
        )
        el = QVBoxLayout(edit_frame); el.setContentsMargins(8,8,8,8); el.setSpacing(6)

        edit_lbl = QLabel("선택한 문장 편집")
        edit_lbl.setStyleSheet(f"font-size:11px;color:{TS};")
        el.addWidget(edit_lbl)

        self._sent_edit = QTextEdit()
        self._sent_edit.setPlaceholderText("목록에서 문장을 클릭하면 여기서 편집할 수 있습니다.")
        self._sent_edit.setFixedHeight(90)
        self._sent_edit.setStyleSheet(
            f"QTextEdit{{background:{COLOR['bg_card']};color:{TP};"
            f"border:1px solid {BD};border-radius:6px;"
            f"padding:6px;font-size:13px;}}"
            f"QTextEdit:focus{{border-color:{A};}}"
        )
        self._sent_edit.setEnabled(False)
        el.addWidget(self._sent_edit)

        edit_btns = QHBoxLayout(); edit_btns.setSpacing(6)
        self._sent_apply_btn = QPushButton("✏️ 수정 적용")
        self._sent_apply_btn.setToolTip("편집 내용을 선택된 항목에 반영합니다")
        self._sent_apply_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{A};"
            f"border:1.5px solid {A};border-radius:7px;"
            f"font-size:12px;padding:5px 12px;}}"
            f"QPushButton:hover{{background:rgba(91,95,217,0.1);}}"
            f"QPushButton:disabled{{color:#5A5A7A;border-color:#2E2E4A;}}"
        )
        self._sent_apply_btn.setEnabled(False)
        self._sent_apply_btn.clicked.connect(self._apply_sent_edit)

        self._sent_add_btn = QPushButton("➕ 문장 추가")
        self._sent_add_btn.setToolTip("편집 칸의 내용을 새 문장으로 추가합니다")
        self._sent_add_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:#22C55E;"
            f"border:1.5px solid #22C55E;border-radius:7px;"
            f"font-size:12px;padding:5px 12px;}}"
            f"QPushButton:hover{{background:rgba(34,197,94,0.1);}}"
            f"QPushButton:disabled{{color:#5A5A7A;border-color:#2E2E4A;}}"
        )
        self._sent_add_btn.setEnabled(False)
        self._sent_add_btn.clicked.connect(self._add_new_sentence)
        # 편집 칸에 내용이 있으면 추가 버튼 활성화
        self._sent_edit.textChanged.connect(
            lambda: self._sent_add_btn.setEnabled(
                bool(self._sent_edit.toPlainText().strip()) and
                self._current_doc is not None
            )
        )

        self._sent_del_btn = QPushButton("🗑 선택 삭제")
        self._sent_del_btn.setStyleSheet(
            f"QPushButton{{background:transparent;color:{ER};"
            f"border:1.5px solid {ER};border-radius:7px;"
            f"font-size:12px;padding:5px 12px;}}"
            f"QPushButton:hover{{background:rgba(239,68,68,0.1);}}"
            f"QPushButton:disabled{{color:#5A5A7A;border-color:#2E2E4A;}}"
        )
        self._sent_del_btn.setEnabled(False)
        self._sent_del_btn.clicked.connect(self._delete_selected_sentence)

        self._sent_save_btn = QPushButton("💾 전체 저장")
        self._sent_save_btn.setToolTip("현재 목록을 DB에 저장합니다")
        self._sent_save_btn.setStyleSheet(
            f"QPushButton{{background:{A};color:#fff;"
            f"border:none;border-radius:7px;"
            f"font-size:12px;padding:5px 12px;}}"
            f"QPushButton:hover{{background:{AH};}}"
            f"QPushButton:disabled{{background:#2E2E4A;color:#5A5A7A;}}"
        )
        self._sent_save_btn.setEnabled(False)
        self._sent_save_btn.clicked.connect(self._save_sentence_edits)

        edit_btns.addWidget(self._sent_apply_btn)
        edit_btns.addWidget(self._sent_add_btn)
        edit_btns.addWidget(self._sent_del_btn)
        edit_btns.addStretch()
        edit_btns.addWidget(self._sent_save_btn)
        el.addLayout(edit_btns)
        sl.addWidget(edit_frame, stretch=0)

        self._sent_empty = QLabel("문서를 선택한 뒤\n분석 실행을 눌러주세요.")
        self._sent_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sent_empty.setStyleSheet(
            f"font-size:13px;color:{TS};"
            f"background:rgba(91,95,217,0.07);"
            "border-radius:8px;padding:20px;"
        )
        sl.addWidget(self._sent_empty)

        right.addTab(sent_tab, "추출 문장")

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([260, 640])
        root.addWidget(splitter, stretch=1)

    # ── 외부 API ────────────────────────────
    def set_subject(self, subject_id: int):
        self._subject_id = subject_id
        self._refresh_doc_list()

    def load_pdf(self, path: str, subject_id: int):
        """UploadTab에서 PDF 분석 시작 요청 — 텍스트 추출 후 DB 저장."""
        self._subject_id = subject_id
        from pathlib import Path as P
        from database.models import Document, SourceType, Language
        from PyQt6.QtWidgets import QProgressDialog, QApplication

        # ── 진행 다이얼로그 ──
        dlg = QProgressDialog("PDF 텍스트 추출 중…", None, 0, 0, self)
        dlg.setWindowTitle("PDF 파싱")
        dlg.setModal(True)
        dlg.show()
        QApplication.processEvents()

        try:
            from core.pdf_parser import PDFParser
            parser = PDFParser(path)
            parsed = parser.parse()
            full_text = parsed.full_text
            page_count = parsed.page_count
            title = parsed.title or P(path).stem
        except Exception as exc:
            dlg.close()
            QMessageBox.critical(self, "PDF 파싱 오류", str(exc))
            return
        finally:
            dlg.close()

        if not full_text.strip():
            QMessageBox.warning(
                self, "텍스트 없음",
                "이 PDF에서 텍스트를 추출할 수 없습니다.\n"
                "이미지 전용(스캔) PDF이거나 텍스트 레이어가 없습니다."
            )
            return

        doc = db.create_document(Document(
            subject_id=subject_id,
            title=title,
            source_type=SourceType.PDF,
            language=Language.KO,
            file_path=path,
            content=full_text,
            page_count=page_count,
        ))
        self._current_doc = doc
        self._refresh_doc_list()
        self._analyze_btn.setEnabled(True)
        logger.info(
            "PDF 문서 등록: id=%d  pages=%d  chars=%d",
            doc.id, page_count, len(full_text),
        )

    def load_text(self, content: str, label: str, subject_id: int):
        """UploadTab에서 텍스트 분석 시작 요청."""
        self._subject_id = subject_id
        from database.models import Document, SourceType, Language
        doc = db.create_document(Document(
            subject_id=subject_id,
            title=label,
            source_type=SourceType.TEXT,
            language=Language.KO,
            content=content,
        ))
        self._current_doc = doc
        self._refresh_doc_list()
        self._analyze_btn.setEnabled(True)
        logger.info("텍스트 문서 등록: id=%d  len=%d", doc.id, len(content))

    # ── 내부 메서드 ─────────────────────────
    def _refresh_doc_list(self):
        if not self._subject_id:
            return
        docs = db.get_documents_by_subject(self._subject_id)
        self._doc_list.clear()
        icons = {SourceType.PDF: "📄", SourceType.TXT: "📝", SourceType.TEXT: "✏️"}
        for d in docs:
            icon = icons.get(d.source_type, "📄")
            item = QListWidgetItem(f"{icon} {d.title}\n   {d.char_count:,}자")
            item.setData(Qt.ItemDataRole.UserRole, d.id)
            self._doc_list.addItem(item)
        # 문서가 없으면 문장 탭도 초기화
        if not docs:
            self._current_doc = None
            self._sent_list.clear()
            self._sent_count.setText("0개")
            self._sent_list.setVisible(False)
            self._sent_empty.setVisible(True)

    def _on_doc_item_clicked(self, item):
        """이미 선택된 문서를 다시 클릭하면 선택 해제."""
        row = self._doc_list.row(item)
        if row == self._doc_list.currentRow() and item.isSelected():
            self._doc_list.clearSelection()
            self._doc_list.setCurrentRow(-1)
            self._current_doc = None
            self._analyze_btn.setEnabled(False)
            self._kw_table.setRowCount(0)
            self._kw_count.setText("0개")
            self._phase_banner.setVisible(True)
            self._add_kw_btn.setEnabled(False)
            self._sent_list.clear()
            self._sent_count.setText("0개")
            self._sent_list.setVisible(False)
            self._sent_empty.setVisible(True)

    def _on_doc_selected(self, row: int):
        if row < 0:
            return
        item = self._doc_list.item(row)
        if not item:
            return
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        doc = db.get_document(doc_id)
        if doc:
            self._current_doc = doc
            self._load_keywords(doc_id)
            # 키워드(분석 결과)가 있을 때만 문장 로드
            keywords = db.get_keywords(doc_id)
            if keywords:
                self._load_sentences(doc)
            else:
                self._sent_list.clear()
                self._sent_count.setText("0개")
                self._sent_list.setVisible(False)
                self._sent_empty.setText("분석 실행을 눌러주세요.")
                self._sent_empty.setVisible(True)
                self._sent_save_btn.setEnabled(False)
            self._analyze_btn.setEnabled(True)
            self._add_kw_btn.setEnabled(True)

    def _load_keywords(self, doc_id: int):
        keywords = db.get_keywords(doc_id)
        self._kw_table.setRowCount(0)
        for kw in keywords:
            row = self._kw_table.rowCount()
            self._kw_table.insertRow(row)
            self._kw_table.setItem(row, 0, QTableWidgetItem(kw.word))
            self._kw_table.setItem(row, 1, QTableWidgetItem(f"{kw.tfidf_score:.4f}"))
            self._kw_table.setItem(row, 2, QTableWidgetItem(f"{kw.textrank_score:.4f}"))
            self._kw_table.setItem(row, 3, QTableWidgetItem(str(kw.frequency)))
            self._kw_table.item(row, 0).setData(Qt.ItemDataRole.UserRole, kw.id)
        self._kw_count.setText(f"{len(keywords)}개")
        self._phase_banner.setVisible(len(keywords) == 0)
        self._del_kw_btn.setEnabled(len(keywords) > 0)

    def _run_analysis(self):
        if not self._current_doc:
            QMessageBox.warning(self, "문서 미선택", "분석할 문서를 먼저 선택하세요.")
            return
        doc = self._current_doc
        # PDF 파일이 있으면 최신 content로 갱신 (표 문장 포함)
        from pathlib import Path as _P
        if doc.file_path and _P(doc.file_path).exists():
            try:
                from core.pdf_parser import PDFParser
                parsed = PDFParser(doc.file_path).parse()
                if len(parsed.full_text) > len(doc.content or ""):
                    doc.content = parsed.full_text
                    from database.db_manager import update_document_content
                    update_document_content(doc.id, doc.content)
                    logger.info("PDF content 갱신: %d자", len(doc.content))
            except Exception as _e:
                logger.warning("content 갱신 실패: %s", _e)
        content_text = doc.content or ""
        if not content_text:
            QMessageBox.warning(self, "내용 없음", "텍스트 내용이 없는 문서입니다.")
            return

        from core.text_processor import TextProcessor
        from analysis.concept_extractor import ConceptExtractor
        from PyQt6.QtWidgets import QProgressDialog

        dlg = QProgressDialog("분석 중…", None, 0, 0, self)
        dlg.setWindowTitle("개념 추출")
        dlg.setModal(True)
        dlg.show()
        from PyQt6.QtWidgets import QApplication
        QApplication.processEvents()

        try:
            processor = TextProcessor()
            processed = processor.process(content_text)
            extractor = ConceptExtractor(max_keywords=50)
            result    = extractor.extract(processed, doc.id, save_to_db=True)
            self._load_keywords(doc.id)
            self._load_sentences(doc)
            self._phase_banner.setVisible(False)
            total_sents = self._sent_list.count()
            QMessageBox.information(
                self, "완료",
                f"키워드 {result.keyword_count}개 추출 완료\n"
                f"언어: {result.language}  |  문장: {total_sents}개",
            )
        except Exception as exc:
            QMessageBox.critical(self, "오류", str(exc))
        finally:
            dlg.close()

    # ── 긴 문장 2차 분리 ────────────────────────────
    @staticmethod
    def _refine_sentences(sentences: list[str], max_len: int = 150) -> list[str]:
        """
        표·목차가 한 줄로 뭉쳐진 긴 문장을 세부 조각으로 분리한다.

        분리 전략 (순서대로 적용):
          1. 숫자 항목 경계   "... 2 모듈화의원칙..." → 번호 앞에서 분리
          2. 구조 헤더 키워드 앞에서 분리 (학습목표, 핵심개념요약 등)
          3. 표 행 패턴       "개념 정의 핵심포인트" → 공백 경계로 분리
        """
        import re
        _MIN = 15  # 조각 최소 길이

        # 구조 헤더: 이 단어 앞에서 줄 바꿈
        _HEADERS = re.compile(
            r'(?<!\A)'           # 문자열 맨 앞 제외
            r'\s+(?='
            r'학습목표|핵심개념요약|상세학습내용|핵심포인트|실무적용'
            r'|핵심키워드|개념\s|정의\s|번호\s|학습\s목표'
            r'|학습개요|학습내용|핵심내용|주요내용'
            r')'
        )
        # 숫자 항목 경계: 공백 + 1~2자리 숫자 + 공백 + 한글/영어/괄호
        _NUM_ITEM  = re.compile(r'\s+(?=\d{1,2}\s+[\uAC00-\uD7A3A-Za-z(])')
        _NUM_BOUND = re.compile(r'(?<=다)\s+(?=\d{1,2}[\.\)]\s*[\uAC00-\uD7A3A-Z])')
        _KO_BOUND  = re.compile(r'(?<=다)\s+(?=[\uAC00-\uD7A3A-Z\(])')
        _PROP_SPLIT = re.compile(
            r'\s+(?=정\s*의:|왜\s+필요|실무\s+예시:|특\s*징:|목적:|배경:|개요:|효과:|원칙:'
            r'|구성\s+요소:|종류:|방법:|단계:|기\s*능:|역할:|적용:|의미:'
            r'|기\s*호:|표\s*기:|속\s*성:|주\s*의:|예\s*:'
            r')'
        )

        def _title_prefix_split(s: str) -> list[str]:
            parts = _PROP_SPLIT.split(s)
            if len(parts) <= 1:
                return [s]
            first = parts[0].strip()
            m = re.match(
                r'^(.+?)\s+(?:-\s*)?(정의:|왜\s+필요|실무\s+예시:|특징:|목적:|배경:|개요:|기호:|표기:|속성:|주의:)',
                first
            )
            title = m.group(1).strip() if m else first
            out = [first] if m else []
            for p in parts[1:]:
                p = re.sub(r'^-\s*', '', p.strip()).strip()
                if p and len(p) >= 10:
                    out.append(f"{title} {p}")
            return [r for r in out if len(r) >= 15]

        result: list[str] = []
        for sent in sentences:
            # 0단계: 섹션 제목+속성 레이블 패턴 → "DFD 정의:..." / "DFD 왜 필요:..."
            pre_parts = _title_prefix_split(sent) if len(sent) > max_len else [sent]
            for pre in pre_parts:
                # key:value 구조 문장(패턴D)은 분리하지 않고 그대로 유지
                if len(pre) <= max_len or re.search(r'\w+:\S', pre):
                    result.append(pre)
                    continue

                # 1단계: 번호 매김 경계 분리 ("~다 2. 자료사전...")
                bound_parts = _NUM_BOUND.split(pre)

                # 2단계: 마침표 없는 한국어 문장 경계 분리 (긴 조각만)
                ko_parts: list[str] = []
                for bp in bound_parts:
                    if len(bp) > 60:
                        ko_parts.extend(_KO_BOUND.split(bp))
                    else:
                        ko_parts.append(bp)

                # 3단계: 구조 헤더 앞 분리
                header_parts: list[str] = []
                for kp in ko_parts:
                    header_parts.extend(_HEADERS.split(kp))

                # 4단계: 남은 긴 조각은 숫자 항목 경계로 추가 분리
                refined: list[str] = []
                for part in header_parts:
                    if len(part) > max_len:
                        sub = _NUM_ITEM.split(part)
                        refined.extend(sub)
                    else:
                        refined.append(part)

                # 최소 길이 필터 후 추가
                for frag in refined:
                    frag = frag.strip()
                    if len(frag) >= _MIN:
                        result.append(frag)

        return result

    def _load_sentences(self, doc) -> None:
        """문서 content에서 문장을 추출해 문장 탭에 표시한다."""
        self._sent_list.clear()
        content = doc.content or ""
        if not content.strip():
            self._sent_empty.setVisible(True)
            self._sent_list.setVisible(False)
            self._sent_count.setText("0개")
            return

        from core.text_processor import split_sentences
        raw_sentences = split_sentences(content)
        sentences = self._refine_sentences(raw_sentences)

        # 현재 키워드 목록 (강조용)
        keywords: list[str] = []
        if doc.id:
            kws = db.get_keywords(doc.id)
            keywords = [k.word for k in kws]

        self._sent_list.clear()
        for i, sent in enumerate(sentences):
            label = f"{i+1:>3}.  {sent}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, sent)
            if any(kw in sent for kw in keywords):
                item.setBackground(
                    __import__('PyQt6.QtGui', fromlist=['QColor']).QColor(91, 95, 217, 25)
                )
            self._sent_list.addItem(item)

        count = len(sentences)
        self._sent_count.setText(f"{count:,}개")
        has_sents = count > 0
        self._sent_list.setVisible(has_sents)
        self._sent_empty.setVisible(not has_sents)
        self._sent_save_btn.setEnabled(has_sents)

    def _add_new_sentence(self) -> None:
        """편집 칸의 내용을 새 문장으로 목록 맨 끝에 추가."""
        new_text = self._sent_edit.toPlainText().strip()
        if not new_text:
            return
        count = self._sent_list.count()
        item = QListWidgetItem(f"{count+1:>3}.  {new_text}")
        self._sent_list.addItem(item)
        self._sent_list.setCurrentItem(item)
        self._sent_list.scrollToItem(item)
        self._sent_count.setText(f"{count+1:,}개")
        self._sent_save_btn.setEnabled(True)
        self._sent_list.setVisible(True)
        self._sent_empty.setVisible(False)

    def _on_sent_selected(self, current, previous) -> None:
        """목록에서 문장 선택 시 편집 패널에 로드."""
        if current is None:
            self._sent_edit.clear()
            self._sent_edit.setEnabled(False)
            self._sent_apply_btn.setEnabled(False)
            self._sent_del_btn.setEnabled(False)
            return
        import re as _re
        raw = current.text()
        clean = _re.sub(r'^\s*\d+\.\s+', '', raw).strip()
        self._sent_edit.setPlainText(clean)
        self._sent_edit.setEnabled(True)
        self._sent_apply_btn.setEnabled(True)
        self._sent_del_btn.setEnabled(self._current_doc is not None)

    def _apply_sent_edit(self) -> None:
        """편집 패널의 내용을 선택된 목록 항목에 반영."""
        item = self._sent_list.currentItem()
        if not item:
            return
        new_text = self._sent_edit.toPlainText().strip()
        if not new_text:
            return
        row = self._sent_list.row(item)
        item.setText(f"{row+1:>3}.  {new_text}")
        self._sent_save_btn.setEnabled(True)

    def _delete_selected_sentence(self) -> None:
        """선택된 문장을 목록에서 제거하고 번호를 재정렬."""
        row = self._sent_list.currentRow()
        if row < 0:
            return
        self._sent_list.takeItem(row)
        self._sent_edit.clear()
        self._sent_edit.setEnabled(False)
        self._sent_apply_btn.setEnabled(False)
        self._sent_del_btn.setEnabled(False)
        import re as _re
        for i in range(self._sent_list.count()):
            text = _re.sub(r'^\s*\d+\.\s+', '', self._sent_list.item(i).text()).strip()
            self._sent_list.item(i).setText(f"{i+1:>3}.  {text}")
        self._sent_count.setText(f"{self._sent_list.count():,}개")
        self._sent_save_btn.setEnabled(self._sent_list.count() > 0)

    def _save_sentence_edits(self) -> None:
        """현재 목록의 문장을 doc.content에 반영하고 DB를 갱신한다."""
        doc = self._current_doc
        if not doc:
            return
        sentences: list[str] = []
        import re as _re
        for i in range(self._sent_list.count()):
            clean = _re.sub(r'^\s*\d+\.\s+', '', self._sent_list.item(i).text()).strip()
            if clean:
                sentences.append(clean)
        if not sentences:
            return
        new_content = "\n".join(sentences)
        try:
            db.update_document_content(doc.id, new_content)
            self._sent_count.setText(f"{len(sentences):,}개")
            QMessageBox.information(self, "저장 완료",
                                    f"문장 {len(sentences)}개가 DB에 저장되었습니다.")
        except Exception as e:
            QMessageBox.warning(self, "저장 실패", str(e))

    def _add_keyword(self):
        from PyQt6.QtWidgets import QInputDialog
        word, ok = QInputDialog.getText(self, "키워드 추가", "추가할 키워드:")
        if ok and word.strip() and self._current_doc:
            db.add_user_keyword(self._current_doc.id, word.strip())
            self._load_keywords(self._current_doc.id)

    def _remove_keyword(self):
        row = self._kw_table.currentRow()
        if row < 0 or not self._kw_table.item(row, 0):
            return
        kw_id = self._kw_table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if kw_id:
            db.update_keyword_removed(kw_id, True)
            self._load_keywords(self._current_doc.id)

    def _delete_doc(self):
        item = self._doc_list.currentItem()
        if not item:
            return
        doc_id = item.data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "문서 삭제", "이 문서와 관련 키워드·퀴즈를 모두 삭제할까요?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            db.delete_document(doc_id)
            self._refresh_doc_list()
            self._kw_table.setRowCount(0)


# ──────────────────────────────────────────────
# Phase 3 파이프라인 연결 (AnalysisTab 확장)
# ──────────────────────────────────────────────

from PyQt6.QtCore import QThread
from PyQt6.QtWidgets import QProgressBar, QApplication
from database.models import SourceType


class _PipelineRunner:
    """AnalysisTab에 믹스인 형태로 파이프라인 실행 기능을 추가한다."""

    def _init_pipeline_ui(self):
        """분석 진행 바 + 상태 레이블을 탭에 추가한다."""
        from PyQt6.QtWidgets import QProgressBar, QLabel
        self._prog_bar = QProgressBar()
        self._prog_bar.setVisible(False)
        self._prog_bar.setTextVisible(False)
        self._prog_bar.setFixedHeight(4)
        from utils.config import COLOR
        self._prog_bar.setStyleSheet(
            f"QProgressBar{{background:{COLOR['border']};border-radius:2px;border:none;}}"
            f"QProgressBar::chunk{{background:{COLOR['primary']};border-radius:2px;}}"
        )
        self._prog_lbl = QLabel("")
        self._prog_lbl.setStyleSheet(f"font-size:12px;color:{COLOR['text_sec']};")
        # 레이아웃의 맨 위에 삽입
        layout = self.layout()
        layout.insertWidget(1, self._prog_bar)
        layout.insertWidget(2, self._prog_lbl)

    def _start_pipeline(
        self,
        subject_id:   int,
        source_type:  SourceType,
        file_path:    str = None,
        text_content: str = None,
        text_label:   str = None,
    ):
        from core.pipeline import AnalysisWorker
        self._worker = AnalysisWorker(
            subject_id   = subject_id,
            source_type  = source_type,
            parent       = self,
            file_path    = file_path,
            text_content = text_content,
            text_label   = text_label,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.status.connect(self._on_status)
        self._worker.finished.connect(self._on_pipeline_done)
        self._worker.error.connect(self._on_pipeline_error)

        self._prog_bar.setVisible(True)
        self._prog_bar.setValue(0)
        self._analyze_btn.setEnabled(False)
        self._worker.start()

    def _on_progress(self, value: int):
        self._prog_bar.setValue(value)

    def _on_status(self, msg: str):
        self._prog_lbl.setText(msg)

    def _on_pipeline_done(self, result):
        self._prog_bar.setVisible(False)
        self._prog_lbl.setText(
            f"완료  |  {result.token_count:,}개 토큰  |  "
            f"{result.sentence_count}개 문장  |  언어={result.language}"
        )
        self._refresh_doc_list()
        if result.doc_id:
            self._load_keywords(result.doc_id)
        self._analyze_btn.setEnabled(True)

    def _on_pipeline_error(self, msg: str):
        self._prog_bar.setVisible(False)
        self._prog_lbl.setText(f"오류: {msg}")
        self._analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "분석 오류", msg)
