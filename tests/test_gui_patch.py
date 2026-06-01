"""
tests/test_gui_patch.py
test_gui.py의 UnicodeDecodeError 수정 패치

기존 test_gui.py::TestStylesheet::test_qss_has_key_selectors 에서
styles.qss를 열 때 encoding 미지정 → Windows cp949 오류 발생

수정: open(..., encoding='utf-8') 명시
"""
import pytest
import os


QSS_PATH = os.path.join(os.path.dirname(__file__), "..", "gui", "styles.qss")


class TestStylesheetFixed:
    def test_qss_file_exists(self):
        """styles.qss 파일 존재 확인"""
        assert os.path.exists(QSS_PATH), f"styles.qss 없음: {QSS_PATH}"

    def test_qss_readable_utf8(self):
        """styles.qss를 UTF-8로 읽을 수 있어야 함"""
        with open(QSS_PATH, encoding='utf-8') as f:
            content = f.read()
        assert len(content) > 0

    def test_qss_has_key_selectors(self):
        """주요 Qt 위젯 셀렉터 포함 확인"""
        with open(QSS_PATH, encoding='utf-8') as f:
            content = f.read()
        key_selectors = ["QWidget", "QPushButton", "QListWidget"]
        for sel in key_selectors:
            assert sel in content, f"셀렉터 '{sel}' 없음"
