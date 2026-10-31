"""PyInstaller entry point — starts the FastAPI backend."""
import multiprocessing
import os
import platform
import sys


def _get_data_dir() -> str:
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    elif system == "Darwin":
        base = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
    else:
        base = os.environ.get("XDG_DATA_HOME") or os.path.join(
            os.path.expanduser("~"), ".local", "share"
        )
    path = os.path.join(base, "circuit-simulator")
    os.makedirs(path, exist_ok=True)
    return path


if __name__ == "__main__":
    multiprocessing.freeze_support()

    if getattr(sys, "frozen", False):
        # Frozen executable: store DB in user data dir, not the temp extraction dir
        data_dir = _get_data_dir()
        os.environ.setdefault("DB_PATH", os.path.join(data_dir, "circuit.db"))

    import uvicorn
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
