"""The PC itself: battery and disk, a sharp screenshot for the phone, clearing the screen.  (Owner: Hands)"""
import secrets
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pc.actions as actions  # for actions.current_session
from pc.actions import basic

IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def _session():
    return actions.current_session


def _status(text: str) -> None:
    if _session():
        _session().status(text)


# ------------------------------------------------------------------ pc_status -------

def _battery() -> str:
    """'Battery 76%, charging' / 'No battery (desktop PC), on mains power' / ''."""
    try:
        if IS_WIN:
            import ctypes

            class SYSTEM_POWER_STATUS(ctypes.Structure):
                _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                            ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                            ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
            s = SYSTEM_POWER_STATUS()
            if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(s)):
                return ""
            plugged = {0: "not charging (on battery)", 1: "plugged in"}.get(s.ACLineStatus, "")
            if s.BatteryFlag & 128 or s.BatteryLifePercent == 255:
                return "No battery (desktop PC)" + (", on mains power" if s.ACLineStatus == 1 else "")
            if s.ACLineStatus == 1 and s.BatteryFlag & 8:
                plugged = "charging"
            left = ""
            if s.ACLineStatus == 0 and s.BatteryLifeTime not in (0xFFFFFFFF, 0):
                left = f", about {s.BatteryLifeTime // 3600} h {s.BatteryLifeTime % 3600 // 60} min left"
            return f"Battery {s.BatteryLifePercent}%, {plugged}{left}"
        if IS_MAC:
            out = subprocess.run(["pmset", "-g", "batt"], capture_output=True, text=True, timeout=5).stdout
            line = next((x for x in out.splitlines() if "%" in x), "")
            return "Battery " + line.split("\t")[-1].strip() if line else ""
    except Exception:  # noqa: BLE001
        return ""
    return ""


def _uptime_seconds() -> float | None:
    try:
        if IS_WIN:
            import ctypes
            ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
            return ctypes.windll.kernel32.GetTickCount64() / 1000
        with open("/proc/uptime", encoding="ascii") as f:
            return float(f.read().split()[0])
    except Exception:  # noqa: BLE001
        return None


def _duration(seconds: float) -> str:
    days, rest = divmod(int(seconds), 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    if days:
        return f"{days} day(s) {hours} h"
    return f"{hours} h {minutes} min" if hours else f"{minutes} min"


def pc_status() -> str:
    """Tell how the PC is doing: battery and charging, free disk space, and how long it has been on since the last restart."""
    _status("Checking the PC")
    parts = []
    battery = _battery()
    if battery:
        parts.append(battery)
    seen = set()
    for folder in [Path.home()] + list(basic.SPECIAL_FOLDERS.values()):
        try:
            drive = folder.anchor or "/"
            if drive in seen or not folder.exists():
                continue
            seen.add(drive)
            u = shutil.disk_usage(folder)
            parts.append(f"Disk {drive.rstrip(chr(92)).rstrip('/') or '/'} {u.free / 1e9:.0f} GB free of {u.total / 1e9:.0f} GB")
        except OSError:
            continue
    up = _uptime_seconds()
    if up is not None:
        parts.append(f"On for {_duration(up)} since the last restart")
    parts.append("Time on the PC: " + time.strftime("%H:%M, %Y-%m-%d"))
    return ". ".join(parts) + "."


# --------------------------------------------------------- screenshot to phone ------

def send_screenshot_to_phone() -> str:
    """Send a sharp, full-size picture of the PC's screen to the phone as a download (the live view is small; use this to read details)."""
    _status("Taking a screenshot")
    try:
        from pc import screen
        data = screen.capture_jpeg(max_width=100_000, quality=85)  # full size, sharp enough to read text
        if getattr(screen, "LAST_ERROR", None):
            return f"Error: the screen can't be captured right now ({screen.LAST_ERROR})."
    except Exception as e:  # noqa: BLE001
        return f"Error taking the screenshot: {e}"
    name = time.strftime("screenshot %Y-%m-%d %H-%M-%S.jpg")
    token = secrets.token_urlsafe(12)
    (basic.OUTBOX / f"{token}__{name}").write_bytes(data)
    if _session():
        _session().emit({"type": "file", "name": name, "url": f"/files/{token}"})
    return f"Sent a screenshot ({len(data) // 1000} KB) to the phone."


# ---------------------------------------------------------------- show desktop -------

def show_desktop(undo: bool = False) -> str:
    """Minimize all windows so the desktop and its icons are visible (or bring them all back with undo=True).

    Args:
        undo: True to bring back the windows that were minimized. Default False.
    """
    _status("Bringing the windows back" if undo else "Showing the desktop")
    try:
        if IS_WIN:
            method = "UndoMinimizeALL" if undo else "MinimizeAll"
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                            f"(New-Object -ComObject Shell.Application).{method}()"],
                           capture_output=True, timeout=15, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        elif IS_MAC:
            script = ('tell application "System Events" to set visible of every process whose visible is true '
                      'and name is not "Finder" to false') if not undo else \
                     'tell application "System Events" to set visible of every process to true'
            subprocess.run(["osascript", "-e", script], capture_output=True, timeout=15)
        else:
            return "Error: show_desktop works on Windows and Mac only."
    except Exception as e:  # noqa: BLE001
        return f"Error: {e}"
    return "Brought the windows back." if undo else "Minimized all windows: the desktop is visible. (undo=True brings them back.)"


TOOLS = [pc_status, send_screenshot_to_phone, show_desktop]
