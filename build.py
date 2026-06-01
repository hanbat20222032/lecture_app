"""
build.py
PyInstaller를 사용한 강의 이해도 측정기 단일 실행 파일 빌드 스크립트

사용법:
    pip install pyinstaller
    python build.py
"""
import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DIST = ROOT / "dist"
BUILD = ROOT / "build_tmp"
APP_NAME = "강의이해도측정기"


def clean():
    """이전 빌드 결과물을 정리한다."""
    for d in (DIST, BUILD, ROOT / f"{APP_NAME}.spec"):
        if Path(str(d)).exists():
            if Path(str(d)).is_dir():
                shutil.rmtree(str(d))
            else:
                os.remove(str(d))
    print("이전 빌드 정리 완료")


def build():
    """PyInstaller로 단일 실행 파일을 생성한다."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",                            # 단일 exe
        "--windowed",                           # 콘솔 창 숨김 (GUI 앱)
        "--name", APP_NAME,
        "--distpath", str(DIST),
        "--workpath", str(BUILD),
        # 데이터 파일
        "--add-data", f"gui/styles.qss{os.pathsep}gui",
        "--add-data", f"database/migrations{os.pathsep}database/migrations",
        # 숨겨진 import (matplotlib 백엔드)
        "--hidden-import", "matplotlib.backends.backend_qtagg",
        "--hidden-import", "matplotlib.backends.backend_agg",
        "--hidden-import", "PyQt6.QtCore",
        "--hidden-import", "PyQt6.QtWidgets",
        "--hidden-import", "PyQt6.QtGui",
        "--hidden-import", "fitz",
        "--hidden-import", "numpy",
        "--hidden-import", "scipy.sparse",
        # 제외 (불필요한 패키지)
        "--exclude-module", "tkinter",
        "--exclude-module", "pytest",
        "--exclude-module", "IPython",
        "main.py",
    ]

    print("빌드 시작...")
    print(f"명령: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode == 0:
        exe = DIST / f"{APP_NAME}.exe"
        if exe.exists():
            size_mb = exe.stat().st_size / 1024 / 1024
            print(f"\n빌드 성공: {exe}")
            print(f"파일 크기: {size_mb:.1f} MB")
        else:
            # Linux/Mac
            exe = DIST / APP_NAME
            if exe.exists():
                print(f"\n빌드 성공: {exe}")
    else:
        print("\n빌드 실패. 위 오류 메시지를 확인하세요.")
        sys.exit(1)


def check_requirements():
    """필수 패키지가 설치되어 있는지 확인한다."""
    required = ["PyInstaller", "PyQt6", "fitz", "matplotlib", "numpy"]
    missing = []
    for pkg in required:
        try:
            __import__(pkg.lower().replace("-", "_"))
        except ImportError:
            missing.append(pkg)
    if missing:
        print(f"누락 패키지: {', '.join(missing)}")
        print("설치 명령: pip install " + " ".join(missing))
        sys.exit(1)
    print("모든 필수 패키지 확인 완료")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="강의 이해도 측정기 빌드")
    parser.add_argument("--clean", action="store_true", help="빌드 결과물만 정리")
    parser.add_argument("--no-clean", action="store_true", help="정리 단계 건너뜀")
    args = parser.parse_args()

    if args.clean:
        clean()
        sys.exit(0)

    check_requirements()
    if not args.no_clean:
        clean()
    build()
