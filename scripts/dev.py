#!/usr/bin/env python3
"""Start the local development services and own their complete process groups."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
children: list[subprocess.Popen] = []


def stop(signum, _frame):
    raise SystemExit(130 if signum == signal.SIGINT else 143)


def spawn(command, cwd):
    # Separate groups include npm's shell/Vite and uvicorn's reload workers.
    child = subprocess.Popen(command, cwd=cwd, start_new_session=True)
    children.append(child)
    return child


def install(command, cwd):
    child = spawn(command, cwd)
    code = child.wait()
    children.remove(child)
    if code:
        raise SystemExit(code)


def cleanup():
    # Further Ctrl+C presses must not interrupt cleanup halfway through.
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if children:
        print("\n正在关闭前后端…", flush=True)
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        alive = False
        for child in children:
            child.poll()  # Reap exited leaders while also checking their workers.
            try:
                os.killpg(child.pid, 0)
                alive = True
            except ProcessLookupError:
                pass
        if not alive:
            break
        time.sleep(0.1)
    for child in children:
        try:
            os.killpg(child.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        child.wait()


def main():
    if len(sys.argv) > 1:
        print("用法：./dev.sh\n首次运行自动安装缺失依赖；Ctrl+C 同时停止所有服务。")
        return 0 if sys.argv[1] in ("-h", "--help") else 2
    if not shutil.which("npm"):
        print("请先安装 Node.js 和 npm。", file=sys.stderr)
        return 1
    uv = shutil.which("uv")
    if not uv:
        print("请先安装 uv：https://docs.astral.sh/uv/getting-started/installation/", file=sys.stderr)
        return 1
    python = ROOT / "backend/.venv/bin/python"
    if not python.exists():
        print("使用 uv 创建后端虚拟环境…", flush=True)
        install([uv, "venv", "--python", sys.executable, str(python.parent.parent)], ROOT)
    # uv can install into an existing environment even when ensurepip/pip is absent.
    # Reconcile requirements on every start, so dependency changes are picked up.
    print("使用 uv 同步后端依赖…", flush=True)
    install([uv, "pip", "install", "--python", str(python), "-r", "requirements.txt"], ROOT / "backend")
    if not (ROOT / "frontend/node_modules/.bin/vite").exists():
        print("安装前端依赖…", flush=True)
        install(["npm", "ci"], ROOT / "frontend")

    print("启动后端：http://localhost:8000\n启动前端：http://localhost:5173\n按 Ctrl+C 同时停止两个服务。", flush=True)
    backend = spawn([str(python), "-m", "uvicorn", "app.main:app", "--reload",
                     "--host", "127.0.0.1", "--port", "8000"], ROOT / "backend")
    frontend = spawn(["npm", "run", "dev", "--", "--host", "127.0.0.1"], ROOT / "frontend")
    while True:
        for name, child in (("后端", backend), ("前端", frontend)):
            code = child.poll()
            if code is not None:
                print(f"{name}已退出（状态 {code}），关闭其余服务。", file=sys.stderr, flush=True)
                return code if code > 0 else 1
        time.sleep(0.2)


if __name__ == "__main__":
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)
    try:
        sys.exit(main())
    except OSError as exc:
        print(f"启动失败：{exc}", file=sys.stderr)
        sys.exit(1)
    finally:
        cleanup()
