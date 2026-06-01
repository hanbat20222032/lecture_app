"""
gui/upload_tab.py
업로드 탭 — PDF / TXT 파일 / 텍스트 직접 입력 통합 위젯
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import Optional
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QPalette
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QTextEdit, QFrame, QStackedWidget,
    QSizePolicy, QProgressBar, QLineEdit,
)
from utils.config import COLOR
from utils.logger import get_logger

logger = get_logger(__name__)
A = COLOR['primary']; AH = COLOR['primary_h']
BG = COLOR['bg_input']; TP = COLOR['text_pri']; TS = COLOR['text_sec']
BD = COLOR['border']; OK = COLOR['success']; ER = COLOR['danger']

class FileReaderThread(QThread):
    finished = pyqtSignal(str, str)
    error    = pyqtSignal(str)
    progress = pyqtSignal(int)
    def __init__(self, filepath, parent=None):
        super().__init__(parent); self.filepath = filepath
    def run(self):
        try:
            path = Path(self.filepath); total = path.stat().st_size
            chunks = []; read = 0
            for enc in ("utf-8","cp949","latin-1"):
                try:
                    with open(self.filepath,"r",encoding=enc) as f:
                        while True:
                            chunk = f.read(65536)
                            if not chunk: break
                            chunks.append(chunk); read += len(chunk.encode(enc,errors="ignore"))
                            self.progress.emit(min(int(read/max(total,1)*100),99))
                    break
                except UnicodeDecodeError:
                    chunks=[]; read=0; continue
            if not chunks: self.error.emit("파일 인코딩을 인식할 수 없습니다."); return
            self.progress.emit(100); self.finished.emit("".join(chunks), self.filepath)
        except Exception as exc: self.error.emit(str(exc))

class ModeButton(QPushButton):
    _ON  = f"QPushButton{{background:{COLOR['primary']};color:#fff;border:none;border-radius:8px;font-weight:600;font-size:13px;padding:8px 20px;}}"
    _OFF = f"QPushButton{{background:transparent;color:{COLOR['text_sec']};border:none;border-radius:8px;font-size:13px;padding:8px 20px;}}QPushButton:hover{{color:{COLOR['text_pri']};background:rgba(91,95,217,0.12);}}"
    def __init__(self, label, parent=None):
        super().__init__(label, parent); self.setCheckable(True); self.setActive(False)
    def setActive(self, v): self.setChecked(v); self.setStyleSheet(self._ON if v else self._OFF)

class DropZone(QFrame):
    fileAccepted = pyqtSignal(str); fileRejected = pyqtSignal(str)
    _IDLE = f"QFrame{{background:{COLOR['bg_input']};border:2px dashed {COLOR['border']};border-radius:16px;}}"
    _HOVR = f"QFrame{{background:rgba(91,95,217,0.08);border:2px dashed {COLOR['primary']};border-radius:16px;}}"
    _EROR = f"QFrame{{background:rgba(239,68,68,0.06);border:2px dashed {COLOR['danger']};border-radius:16px;}}"
    _GOOD = f"QFrame{{background:rgba(34,197,94,0.06);border:2px dashed {COLOR['success']};border-radius:16px;}}"
    def __init__(self, exts, label, parent=None):
        super().__init__(parent); self.exts=[e.lower() for e in exts]; self.label=label
        self._loaded_path: Optional[str] = None          # ← 추가
        self.setAcceptDrops(True); self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,QSizePolicy.Policy.Expanding)
        self._build(); self.setStyleSheet(self._IDLE)
    def _build(self):
        lay=QVBoxLayout(self); lay.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.setSpacing(12)
        self._ico=QLabel("📂"); self._ico.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ico.setStyleSheet("font-size:38px;border:none;background:transparent;")
        self._ttl=QLabel(f"{self.label} 파일을 여기에 드롭하세요")
        self._ttl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._ttl.setStyleSheet(f"font-size:15px;font-weight:600;color:{TP};border:none;background:transparent;")
        ext_s=" / ".join(e.upper() for e in self.exts)
        self._sub=QLabel(f"지원: {ext_s}  ·  최대 100MB")
        self._sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._sub.setStyleSheet(f"font-size:12px;color:{TS};border:none;background:transparent;")
        self._btn=QPushButton("파일 선택"); self._btn.setFixedWidth(130)
        self._btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._btn.setStyleSheet(f"QPushButton{{background:{A};color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:600;padding:8px;}}QPushButton:hover{{background:{AH};}}")
        self._btn.clicked.connect(self._open)
        self._prog=QProgressBar(); self._prog.setVisible(False); self._prog.setTextVisible(False)
        self._prog.setFixedHeight(4)
        self._prog.setStyleSheet(f"QProgressBar{{background:{BD};border-radius:2px;border:none;}}QProgressBar::chunk{{background:{A};border-radius:2px;}}")
        self._info=QLabel(); self._info.setAlignment(Qt.AlignmentFlag.AlignCenter); self._info.setVisible(False)
        for w in(self._ico,self._ttl,self._sub): lay.addWidget(w)
        lay.addWidget(self._btn,alignment=Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(self._prog); lay.addWidget(self._info)
    def dragEnterEvent(self,e:QDragEnterEvent):
        if e.mimeData().hasUrls():
            ext=Path(e.mimeData().urls()[0].toLocalFile()).suffix.lower().lstrip(".")
            if ext in self.exts: e.acceptProposedAction(); self.setStyleSheet(self._HOVR); return
        e.ignore()
    def dragLeaveEvent(self,_): self.setStyleSheet(self._IDLE)
    def dropEvent(self,e:QDropEvent):
        self.setStyleSheet(self._IDLE)
        if e.mimeData().hasUrls(): self._handle(e.mimeData().urls()[0].toLocalFile())
    def _open(self):
        ext_f=" ".join(f"*.{e}" for e in self.exts)
        ext_l="/".join(e.upper() for e in self.exts)
        path,_=QFileDialog.getOpenFileName(self,f"{ext_l} 파일 선택","",f"{ext_l} 파일 ({ext_f});;모든 파일 (*)")
        if path: self._handle(path)
    def _handle(self,path):
        ext=Path(path).suffix.lower().lstrip(".")
        if ext not in self.exts: self._state("err",f"지원 안 함: .{ext}"); self.fileRejected.emit(f"지원 안 함: .{ext}"); return
        mb=os.path.getsize(path)/1024/1024
        if mb>100: self._state("err",f"크기 초과: {mb:.1f}MB"); self.fileRejected.emit("크기 초과"); return
        self._loaded_path = path
        self._state("ok",f"✓  {Path(path).name}  ({mb:.2f} MB)"); self.fileAccepted.emit(path)
    def _state(self,s,msg):
        css={"ok":self._GOOD,"err":self._EROR}.get(s,self._IDLE)
        self.setStyleSheet(css); self._info.setVisible(True)
        color=OK if s=="ok" else ER
        self._info.setStyleSheet(f"font-size:12px;color:{color};border:none;background:transparent;")
        self._info.setText(msg)
    def reset(self):
        self._loaded_path = None
        self._info.setVisible(False); self.setStyleSheet(self._IDLE)
    @property
    def loaded_path(self) -> Optional[str]:
        return self._loaded_path

class PdfInputPanel(QWidget):
    fileReady=pyqtSignal(str)
    def __init__(self,parent=None):
        super().__init__(parent); self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        root.addWidget(QLabel("PDF 교재 업로드"))
        self._dz=DropZone(["pdf"],"PDF"); self._dz.fileAccepted.connect(self._on_ok)
        self._dz.fileRejected.connect(self._on_rej); root.addWidget(self._dz)
        self._meta=QLabel(); self._meta.setVisible(False)
        self._meta.setStyleSheet(f"font-size:12px;color:{TS};")
        root.addWidget(self._meta)
        bot=QHBoxLayout()
        self._st=QLabel("PDF 파일을 드롭하거나 버튼으로 선택하세요.")
        self._st.setStyleSheet(f"font-size:12px;color:{TS};")
        self._abtn=QPushButton("  분석 시작  ▶"); self._abtn.setEnabled(False)
        self._abtn.setStyleSheet(f"QPushButton{{background:{A};color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;padding:9px 24px;}}QPushButton:hover:enabled{{background:{AH};}}QPushButton:disabled{{background:{BD};color:{TS};}}")
        self._abtn.clicked.connect(lambda:self.fileReady.emit(self._dz.loaded_path) if self._dz.loaded_path else None)
        bot.addWidget(self._st); bot.addStretch(); bot.addWidget(self._abtn)
        root.addLayout(bot); self._dz.fileAccepted.connect(self._loaded)
    def _loaded(self,path):
        self._abtn.setEnabled(True)
        self._st.setText(f"✓  {Path(path).name}")
        self._st.setStyleSheet(f"font-size:12px;color:{OK};")
        try:
            import fitz; doc=fitz.open(path)
            self._meta.setText(f"페이지: {doc.page_count}쪽  |  제목: {doc.metadata.get('title',Path(path).stem)}"); doc.close()
            self._meta.setVisible(True)
        except: self._meta.setVisible(False)
    def _on_ok(self,path): pass
    def _on_rej(self,msg): self._st.setText(f"⚠  {msg}"); self._st.setStyleSheet(f"font-size:12px;color:{ER};")
    def reset(self): self._dz.reset(); self._abtn.setEnabled(False); self._meta.setVisible(False)

class TextInputPanel(QWidget):
    contentReady=pyqtSignal(str,str); cleared=pyqtSignal()
    MAX=500_000
    def __init__(self,parent=None):
        super().__init__(parent); self._reader=None; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(0,0,0,0); root.setSpacing(10)
        tb=QHBoxLayout(); tb.setSpacing(8)
        ttl=QLabel("텍스트 직접 입력"); ttl.setStyleSheet(f"font-size:14px;font-weight:600;color:{TP};")
        self._cl=QLabel("0 / 500,000자"); self._cl.setStyleSheet(f"font-size:12px;color:{TS};")
        lb=QPushButton("TXT 불러오기"); lb.setCursor(Qt.CursorShape.PointingHandCursor)
        lb.setStyleSheet(f"QPushButton{{background:transparent;color:{A};border:1.5px solid {A};border-radius:7px;font-size:12px;font-weight:600;padding:5px 14px;}}QPushButton:hover{{background:rgba(91,95,217,0.12);}}")
        lb.clicked.connect(self._load_txt)
        cb=QPushButton("초기화"); cb.setCursor(Qt.CursorShape.PointingHandCursor)
        cb.setStyleSheet(f"QPushButton{{background:transparent;color:{TS};border:1.5px solid {BD};border-radius:7px;font-size:12px;padding:5px 14px;}}QPushButton:hover{{color:{ER};border-color:{ER};}}")
        cb.clicked.connect(self._clear)
        tb.addWidget(ttl); tb.addStretch(); tb.addWidget(self._cl); tb.addWidget(lb); tb.addWidget(cb)
        root.addLayout(tb)
        lr=QHBoxLayout(); lr.setSpacing(8)
        ll=QLabel("출처 이름"); ll.setFixedWidth(70); ll.setStyleSheet(f"font-size:12px;color:{TS};")
        self._src=QLineEdit(); self._src.setPlaceholderText("예: 1주차 강의 노트…")
        self._src.setStyleSheet(f"QLineEdit{{background:{BG};color:{TP};border:1.5px solid {BD};border-radius:8px;font-size:13px;padding:6px 12px;}}QLineEdit:focus{{border-color:{A};}}")
        lr.addWidget(ll); lr.addWidget(self._src); root.addLayout(lr)
        self._ed=QTextEdit()
        self._ed.setPlaceholderText("강의 노트, 필기, 교재 요약 등을 여기에 붙여넣으세요.\n\n한국어·영어 모두 지원됩니다.\n'TXT 불러오기'로 파일을 불러올 수도 있습니다.")
        self._ed.setStyleSheet(f"QTextEdit{{background:{BG};color:{TP};border:1.5px solid {BD};border-radius:12px;font-size:13px;padding:14px;selection-background-color:{A};}}QTextEdit:focus{{border-color:{A};}}")
        self._ed.setMinimumHeight(260); self._ed.textChanged.connect(self._changed)
        root.addWidget(self._ed)
        self._pb=QProgressBar(); self._pb.setVisible(False); self._pb.setTextVisible(False); self._pb.setFixedHeight(4)
        self._pb.setStyleSheet(f"QProgressBar{{background:{BD};border-radius:2px;border:none;}}QProgressBar::chunk{{background:{A};border-radius:2px;}}")
        root.addWidget(self._pb)
        bot=QHBoxLayout()
        self._st=QLabel("텍스트를 입력하거나 TXT 파일을 불러오세요.")
        self._st.setStyleSheet(f"font-size:12px;color:{TS};")
        self._abtn=QPushButton("  분석 시작  ▶"); self._abtn.setEnabled(False)
        self._abtn.setStyleSheet(f"QPushButton{{background:{A};color:#fff;border:none;border-radius:9px;font-size:13px;font-weight:700;padding:9px 24px;}}QPushButton:hover:enabled{{background:{AH};}}QPushButton:disabled{{background:{BD};color:{TS};}}")
        self._abtn.clicked.connect(self._emit)
        bot.addWidget(self._st); bot.addStretch(); bot.addWidget(self._abtn)
        root.addLayout(bot)
    def _load_txt(self):
        path,_=QFileDialog.getOpenFileName(self,"TXT 파일 선택","","텍스트 파일 (*.txt);;모든 파일 (*)")
        if path: self._start_reader(path)
    def _start_reader(self,path):
        if self._reader and self._reader.isRunning(): self._reader.quit()
        self._pb.setVisible(True); self._pb.setValue(0)
        self._st.setText(f"읽는 중: {Path(path).name} …")
        self._reader=FileReaderThread(path,self)
        self._reader.progress.connect(self._pb.setValue)
        self._reader.finished.connect(self._loaded); self._reader.error.connect(self._err)
        self._reader.start()
    def _loaded(self,content,filepath):
        self._pb.setVisible(False)
        if not self._src.text(): self._src.setText(Path(filepath).stem)
        self._ed.setPlainText(content)
        self._st.setText(f"✓  {Path(filepath).name}  ({len(content):,}자)")
        self._st.setStyleSheet(f"font-size:12px;color:{OK};")
    def _err(self,msg):
        self._pb.setVisible(False)
        self._st.setText(f"오류: {msg}"); self._st.setStyleSheet(f"font-size:12px;color:{ER};")
    def _changed(self):
        text=self._ed.toPlainText(); n=len(text)
        if n>self.MAX:
            c=self._ed.textCursor(); pos=c.position()
            self._ed.blockSignals(True); self._ed.setPlainText(text[:self.MAX])
            c.setPosition(min(pos,self.MAX)); self._ed.setTextCursor(c)
            self._ed.blockSignals(False); n=self.MAX
        color=COLOR['warning'] if n>self.MAX*0.9 else TS
        self._cl.setText(f"{n:,} / {self.MAX:,}자")
        self._cl.setStyleSheet(f"font-size:12px;color:{color};")
        self._abtn.setEnabled(n>=20)
    def _clear(self):
        self._ed.clear(); self._src.clear()
        self._cl.setText("0 / 500,000자")
        self._st.setText("텍스트를 입력하거나 TXT 파일을 불러오세요.")
        self._st.setStyleSheet(f"font-size:12px;color:{TS};"); self.cleared.emit()
    def _emit(self):
        text=self._ed.toPlainText().strip(); src=self._src.text().strip() or "직접 입력 텍스트"
        if len(text)>=20: self.contentReady.emit(text,src)
    @property
    def text(self): return self._ed.toPlainText()
    @property
    def source_name(self): return self._src.text().strip() or "직접 입력 텍스트"

class UploadTab(QWidget):
    pdfReady  = pyqtSignal(str)
    textReady = pyqtSignal(str,str)
    MODE_PDF=0; MODE_TEXT=1
    def __init__(self,parent=None):
        super().__init__(parent); self._mode=self.MODE_PDF; self._build()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(24,20,24,20); root.setSpacing(16)
        hdr=QHBoxLayout()
        t=QLabel("소스 입력"); t.setStyleSheet(f"font-size:20px;font-weight:700;color:{TP};")
        s=QLabel("분석할 콘텐츠 소스를 선택하세요."); s.setStyleSheet(f"font-size:13px;color:{TS};margin-top:2px;")
        tc=QVBoxLayout(); tc.setSpacing(2); tc.addWidget(t); tc.addWidget(s)
        hdr.addLayout(tc); hdr.addStretch(); root.addLayout(hdr)
        tf=QFrame()
        tf.setStyleSheet(f"QFrame{{background:{BG};border:1.5px solid {BD};border-radius:12px;}}")
        tf.setFixedHeight(46); tl=QHBoxLayout(tf); tl.setContentsMargins(4,4,4,4); tl.setSpacing(4)
        self._bp=ModeButton("📄  PDF 파일"); self._bt=ModeButton("✏️  텍스트 입력")
        self._bp.setActive(True)
        self._bp.clicked.connect(lambda:self._switch(self.MODE_PDF))
        self._bt.clicked.connect(lambda:self._switch(self.MODE_TEXT))
        tl.addWidget(self._bp); tl.addWidget(self._bt); root.addWidget(tf)
        sep=QFrame(); sep.setFrameShape(QFrame.Shape.HLine)
        sep.setStyleSheet(f"color:{BD};"); root.addWidget(sep)
        self._stack=QStackedWidget(); self._stack.setStyleSheet("background:transparent;")
        self._pp=PdfInputPanel(); self._tp=TextInputPanel()
        self._pp.fileReady.connect(self.pdfReady); self._tp.contentReady.connect(self.textReady)
        self._stack.addWidget(self._pp); self._stack.addWidget(self._tp); root.addWidget(self._stack,stretch=1)
        hint=QLabel("💡  PDF와 텍스트를 각각 업로드하면 소스 간 커버리지를 비교 분석합니다.")
        hint.setWordWrap(True)
        hint.setStyleSheet(f"font-size:12px;color:{TS};background:rgba(91,95,217,0.07);border-radius:8px;padding:10px 14px;")
        root.addWidget(hint)
    def _switch(self,mode):
        if mode==self._mode: return
        self._mode=mode; self._bp.setActive(mode==self.MODE_PDF)
        self._bt.setActive(mode==self.MODE_TEXT); self._stack.setCurrentIndex(mode)
    def reset_all(self): self._pp.reset(); self._tp._clear()
    @property
    def current_mode(self): return self._mode
