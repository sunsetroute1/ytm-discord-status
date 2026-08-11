# -*- coding: utf-8 -*-
"""Build a standalone Windows exe with PyInstaller."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
NAME = "ytm-discord"


def main() -> int:
    venv_python = ROOT / ".venv" / "Scripts" / "python.exe"
    py = str(venv_python if venv_python.exists() else sys.executable)

    subprocess.check_call([py, "-m", "pip", "install", "-e", ".", "pyinstaller"])

    if DIST.exists():
        shutil.rmtree(DIST)
    if BUILD.exists():
        shutil.rmtree(BUILD)

    cmd = [
        py,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--console",
        f"--name={NAME}",
        "--paths",
        str(ROOT / "src"),
        "--hidden-import=winrt.windows.media.control",
        "--hidden-import=winrt.windows.foundation",
        "--hidden-import=winrt.windows.foundation.collections",
        "--collect-all",
        "winrt",
        str(ROOT / "scripts" / "run_entry.py"),
    ]
    subprocess.check_call(cmd, cwd=ROOT)

    exe = DIST / f"{NAME}.exe"
    if not exe.exists():
        print("Build failed: exe missing", file=sys.stderr)
        return 1

    shutil.copy2(ROOT / "config.example.json", DIST / "config.example.json")
    shutil.copy2(ROOT / "docs" / "INSTALL.md", DIST / "INSTALL.md")
    print(f"Built {exe}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
