#!/usr/bin/env python3
"""
把 Python 后端冻结成单文件可执行程序，供 Electron 客户端打包后独立运行。

用法（在各自目标系统上运行）：
    python build_backend.py
产物：
    rpa-client/resources/backend/rpa-backend          (macOS / Linux)
    rpa-client/resources/backend/rpa-backend.exe      (Windows)

注意：
- PyInstaller 只能产出「运行它的那个操作系统」的可执行文件。要同时得到 Windows 和
  macOS 版本，必须分别在 Windows 和 macOS 上各跑一次本脚本（或用双 runner 的 CI）。
- 目标机仍需安装 Google Chrome（DrissionPage 驱动系统 Chrome，不随包打入）。
"""
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Windows 默认控制台用 cp1252，打印中文/emoji 会 UnicodeEncodeError。强制 UTF-8。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
ENTRY = ROOT / "rpa_core" / "server_entry.py"
DEST = ROOT / "rpa-client" / "resources" / "backend"
NAME = "rpa-backend"
EXE = NAME + (".exe" if sys.platform.startswith("win") else "")


def ensure_pyinstaller() -> None:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("未检测到 PyInstaller，正在安装…")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller>=6.0"])


def build() -> None:
    ensure_pyinstaller()
    work = ROOT / "build" / "pyinstaller"
    dist = ROOT / "build" / "dist"

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--name", NAME,
        "--noconfirm", "--clean",
        "--distpath", str(dist),
        "--workpath", str(work),
        "--specpath", str(ROOT / "build"),
        "--paths", str(ROOT),
        # 这些库有动态导入 / 数据文件，需整包收集，否则冻结后运行时缺模块
        "--collect-all", "DrissionPage",
        "--collect-all", "uvicorn",
        "--collect-all", "websockets",
        "--collect-all", "anthropic",
        "--collect-submodules", "anyio",
        "--collect-submodules", "fastapi",
        "--collect-submodules", "starlette",
        "--hidden-import", "uvicorn.lifespan.on",
        "--hidden-import", "uvicorn.loops.auto",
        "--hidden-import", "uvicorn.protocols.http.auto",
        "--hidden-import", "uvicorn.protocols.websockets.auto",
        str(ENTRY),
    ]
    print("运行:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=ROOT)

    DEST.mkdir(parents=True, exist_ok=True)
    src = dist / EXE
    if not src.exists():
        raise SystemExit(f"未找到产物: {src}")
    target = DEST / EXE
    if target.exists():
        target.unlink()
    shutil.copy2(src, target)
    if not sys.platform.startswith("win"):
        os.chmod(target, 0o755)
    print(f"\n✅ 后端已冻结: {target}")
    print(f"   大小: {target.stat().st_size / 1_000_000:.1f} MB")


if __name__ == "__main__":
    build()
