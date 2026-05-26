"""
setup.py
강의 이해도 측정기 — PyInstaller 패키징 스크립트

사용법:
    pip install pyinstaller
    python setup.py          # .spec 파일 생성 후 빌드
    또는 직접 빌드:
    pyinstaller lecture_app.spec
"""

import os
import sys
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent

SPEC_CONTENT = '''# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

ROOT = Path(SPECPATH)

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / "gui" / "styles.qss"),   "gui"),
        (str(ROOT / "database" / "migrations"), "database/migrations"),
        (str(ROOT / "utils" / "stopwords_ko.py"), "utils"),
    ],
    hiddenimports=[
        "PyQt6.QtCore",
        "PyQt6.QtGui",
        "PyQt6.QtWidgets",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_agg",
        "numpy",
        "scipy",
        "fitz",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "unittest", "pytest"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="강의이해도측정기",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # GUI 앱: 콘솔 창 숨김
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,              # 아이콘 경로 추가 시: icon="app.ico"
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="강의이해도측정기",
)
'''


def write_spec():
    spec_path = ROOT / "lecture_app.spec"
    spec_path.write_text(SPEC_CONTENT, encoding="utf-8")
    print(f"[setup] .spec 파일 생성: {spec_path}")
    return spec_path


def check_pyinstaller():
    try:
        import PyInstaller
        print(f"[setup] PyInstaller {PyInstaller.__version__} 확인")
        return True
    except ImportError:
        print("[setup] PyInstaller 없음. 설치 중...")
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "pyinstaller"],
            check=True,
        )
        return True


def build(spec_path: Path):
    print("[setup] 빌드 시작...")
    result = subprocess.run(
        ["pyinstaller", "--clean", str(spec_path)],
        cwd=str(ROOT),
    )
    if result.returncode == 0:
        print("\n[setup] 빌드 완료!")
        print(f"  실행 파일: dist/강의이해도측정기/강의이해도측정기.exe")
    else:
        print("\n[setup] 빌드 실패. 위 오류 메시지를 확인하세요.")
    return result.returncode


def run_tests():
    """빌드 전 테스트 실행."""
    print("[setup] 테스트 실행 중...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest",
         "tests/test_core.py",
         "tests/test_analysis.py",
         "tests/test_quiz.py",
         "-v", "--tb=short"],
        cwd=str(ROOT),
    )
    return result.returncode == 0


if __name__ == "__main__":
    print("=" * 50)
    print(" 강의 이해도 측정기 — 패키징 스크립트")
    print("=" * 50)

    # 1. 테스트
    if "--skip-tests" not in sys.argv:
        if not run_tests():
            print("\n[setup] 테스트 실패. 빌드를 중단합니다.")
            print("  테스트를 건너뛰려면: python setup.py --skip-tests")
            sys.exit(1)
        print("[setup] 모든 테스트 통과\n")

    # 2. .spec 생성
    spec = write_spec()

    # 3. PyInstaller 확인
    check_pyinstaller()

    # 4. 빌드
    code = build(spec)
    sys.exit(code)
