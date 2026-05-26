"""
main.py — 강의 이해도 측정기 진입점
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from utils.logger import get_logger
from utils.config import APP_NAME, APP_VERSION
from database.db_manager import initialize_db

logger = get_logger(__name__)

def main():
    logger.info("=== %s v%s 시작 ===", APP_NAME, APP_VERSION)
    try:
        initialize_db()
    except Exception as exc:
        logger.critical("DB 초기화 실패: %s", exc); sys.exit(1)

    try:
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QPalette, QColor
        app = QApplication(sys.argv)
        app.setApplicationName(APP_NAME)
        app.setApplicationVersion(APP_VERSION)
        app.setStyle("Fusion")

        # 다크 기본 팔레트 (QSS 로드 전 깜빡임 방지)
        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,      QColor("#0F0F1A"))
        palette.setColor(QPalette.ColorRole.WindowText,  QColor("#E2E2F0"))
        palette.setColor(QPalette.ColorRole.Base,        QColor("#13131F"))
        palette.setColor(QPalette.ColorRole.Text,        QColor("#E2E2F0"))
        palette.setColor(QPalette.ColorRole.Button,      QColor("#1E1E2E"))
        palette.setColor(QPalette.ColorRole.ButtonText,  QColor("#E2E2F0"))
        palette.setColor(QPalette.ColorRole.Highlight,   QColor("#5B5FD9"))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
        app.setPalette(palette)

        from gui.main_window import MainWindow
        window = MainWindow()
        window.show()
        logger.info("메인 윈도우 표시 완료")
        sys.exit(app.exec())

    except ImportError as exc:
        logger.critical("PyQt6 로드 실패: %s", exc); sys.exit(1)
    except Exception as exc:
        logger.critical("앱 실행 오류: %s", exc, exc_info=True); sys.exit(1)

if __name__ == "__main__":
    main()

