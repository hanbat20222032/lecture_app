"""
tests/test_gui.py  — GUI 모듈 임포트·초기화 테스트 (오프스크린)
실행: python -m pytest tests/test_gui.py -v
"""
import sys, os
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import pytest
from database.db_manager import initialize_db
initialize_db()

@pytest.fixture(scope="module")
def app():
    from PyQt6.QtWidgets import QApplication
    return QApplication.instance() or QApplication(sys.argv)


class TestStylesheet:
    def test_qss_exists(self):
        from pathlib import Path
        qss = Path(__file__).parent.parent / "gui" / "styles.qss"
        assert qss.exists()

    def test_qss_nonempty(self):
        from pathlib import Path
        qss = Path(__file__).parent.parent / "gui" / "styles.qss"
        assert len(qss.read_text(encoding="utf-8")) > 500

    def test_qss_has_key_selectors(self):
        from pathlib import Path
        content = (Path(__file__).parent.parent / "gui" / "styles.qss").read_text(encoding="utf-8")
        for sel in ("QTabWidget", "QPushButton", "QListWidget", "QScrollBar"):
            assert sel in content, f"{sel} 선택자 없음"


class TestUploadTab:
    def test_import(self, app):
        from gui.upload_tab import UploadTab
        assert UploadTab is not None

    def test_instantiate(self, app):
        from gui.upload_tab import UploadTab
        tab = UploadTab()
        assert tab is not None

    def test_mode_constants(self, app):
        from gui.upload_tab import UploadTab
        assert UploadTab.MODE_PDF == 0
        assert UploadTab.MODE_TEXT == 1

    def test_has_signals(self, app):
        from gui.upload_tab import UploadTab
        tab = UploadTab()
        assert hasattr(tab, "pdfReady")
        assert hasattr(tab, "textReady")

    def test_initial_mode(self, app):
        from gui.upload_tab import UploadTab
        tab = UploadTab()
        assert tab.current_mode == UploadTab.MODE_PDF

    def test_reset_all(self, app):
        from gui.upload_tab import UploadTab
        tab = UploadTab()
        tab.reset_all()   # 예외 없이 실행


class TestAnalysisTab:
    def test_import(self, app):
        from gui.analysis_tab import AnalysisTab
        assert AnalysisTab is not None

    def test_instantiate(self, app):
        from gui.analysis_tab import AnalysisTab
        tab = AnalysisTab()
        assert tab is not None

    def test_set_subject_no_crash(self, app):
        from gui.analysis_tab import AnalysisTab
        tab = AnalysisTab()
        tab.set_subject(9999)   # 없는 subject_id여도 예외 없음


class TestQuizTab:
    def test_import(self, app):
        from gui.quiz_tab import QuizTab
        assert QuizTab is not None

    def test_instantiate(self, app):
        from gui.quiz_tab import QuizTab
        tab = QuizTab()
        assert tab is not None

    def test_set_subject_no_crash(self, app):
        from gui.quiz_tab import QuizTab
        tab = QuizTab()
        tab.set_subject(9999)


class TestReportTab:
    def test_import(self, app):
        from gui.report_tab import ReportTab
        assert ReportTab is not None

    def test_instantiate(self, app):
        from gui.report_tab import ReportTab
        tab = ReportTab()
        assert tab is not None

    def test_set_subject_no_crash(self, app):
        from gui.report_tab import ReportTab
        tab = ReportTab()
        tab.set_subject(9999)


class TestSessionTab:
    def test_import(self, app):
        from gui.session_tab import SessionTab
        assert SessionTab is not None

    def test_instantiate(self, app):
        from gui.session_tab import SessionTab
        tab = SessionTab()
        assert tab is not None

    def test_show_search_results(self, app):
        from gui.session_tab import SessionTab
        tab = SessionTab()
        results = [{"word":"소프트웨어","title":"문서1","frequency":5}]
        tab.show_search_results(results, "소프트웨어")


class TestMainWindow:
    def test_import(self, app):
        from gui.main_window import MainWindow
        assert MainWindow is not None

    def test_instantiate(self, app):
        from gui.main_window import MainWindow
        win = MainWindow()
        assert win is not None
        win.destroy()
