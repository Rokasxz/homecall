"""Talks to uia_worker.ps1: a PowerShell helper started once and kept running.  (Owner: Hands)

Asking Windows "what's under the mouse?" used to start PowerShell every time (1-2 s). Now the
helper stays open and answers in a fraction of a second. Windows only; elsewhere every
question answers {} and the tools fall back to what they did before.
"""
import json
import queue
import subprocess
import sys
import threading
from pathlib import Path

IS_WIN = sys.platform == "win32"
WORKER = Path(__file__).resolve().parent / "uia_worker.ps1"

_lock = threading.Lock()
_proc: subprocess.Popen | None = None
_answers: "queue.Queue[str]" = queue.Queue()


def _start() -> subprocess.Popen | None:
    global _proc
    if _proc is not None and _proc.poll() is None:
        return _proc
    try:
        _proc = subprocess.Popen(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(WORKER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            text=True, encoding="utf-8", bufsize=1,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    except Exception:  # noqa: BLE001
        _proc = None
        return None

    def read(p: subprocess.Popen) -> None:
        for line in p.stdout:  # one answer per line
            _answers.put(line)

    threading.Thread(target=read, args=(_proc,), daemon=True).start()
    return _proc


def _stop() -> None:
    global _proc
    if _proc is not None:
        try:
            _proc.kill()
        except Exception:  # noqa: BLE001
            pass
    _proc = None


def ask(request: dict, timeout: float = 10) -> dict:
    """Send one request to the helper and return its answer, or {} if anything goes wrong."""
    if not IS_WIN:
        return {}
    with _lock:
        p = _start()
        if p is None:
            return {}
        while not _answers.empty():  # drop a late answer from an earlier timeout
            _answers.get_nowait()
        try:
            p.stdin.write(json.dumps(request) + "\n")
            p.stdin.flush()
            line = _answers.get(timeout=timeout)
            answer = json.loads(line)
            return answer if isinstance(answer, dict) and "error" not in answer else {}
        except Exception:  # noqa: BLE001  (timeout, crash...): start fresh next time
            _stop()
            return {}


def at(real_x: int, real_y: int) -> dict:
    """What Windows says is at this screen point: name, control, process, x, y. {} if unknown."""
    return ask({"op": "at", "x": int(real_x), "y": int(real_y)})


def find(hwnd: int, text: str) -> list[dict]:
    """Visible buttons/links/menu items... in this window whose name contains the text."""
    return ask({"op": "find", "hwnd": int(hwnd), "text": text}, timeout=20).get("hits") or []


def volume_get() -> tuple[float, bool] | None:
    """(master volume 0.0-1.0, muted?), or None if unknown."""
    answer = ask({"op": "volume_get"}, timeout=30)
    return (float(answer["level"]), bool(answer.get("muted"))) if "level" in answer else None


def volume_set(level: float, mute: bool | None = None) -> float | None:
    """Set the master volume (0.0-1.0). Unmutes, unless mute is given. Returns the new level, or None."""
    request = {"op": "volume_set", "level": max(0.0, min(1.0, float(level)))}
    if mute is not None:
        request["mute"] = bool(mute)
    new = ask(request, timeout=30).get("level")
    return float(new) if new is not None else None
