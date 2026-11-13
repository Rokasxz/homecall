"""Starter tools. Real but minimal; the Hands owner extends and improves them."""
import os
import platform
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

import pc.actions as actions  # for actions.current_session

HOME = Path.home()
# The AI may only touch files inside these folders. Add more if you need them.
ALLOWED_ROOTS = [HOME / "Desktop", HOME / "Documents", HOME / "Downloads", HOME / "Pictures"]
OUTBOX = Path(__file__).resolve().parent.parent / "outbox"  # files sent to the phone land here
OUTBOX.mkdir(exist_ok=True)
IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def _resolve(path_or_name: str) -> Path | None:
    """Turn 'Downloads', '~/Documents/a.pdf' or a full path into a safe Path, or None."""
    p = Path(os.path.expanduser(path_or_name))
    if not p.is_absolute():
        p = HOME / p
    p = p.resolve()
    roots = [r.resolve() for r in ALLOWED_ROOTS]  # resolve: /var -> /private/var on Mac, OneDrive on Windows
    if any(p == r or r in p.parents for r in roots):
        return p
    return None


def _session():
    return actions.current_session


# ---------------------------------------------------------------- files ---------

def list_files(folder: str = "Desktop") -> str:
    """List the files and folders inside a folder on the PC.

    Args:
        folder: Desktop, Documents, Downloads, Pictures, or a full path inside them.
    """
    p = _resolve(folder)
    if p is None or not p.is_dir():
        return f"Error: '{folder}' is not an allowed folder. Allowed: Desktop, Documents, Downloads, Pictures."
    items = sorted(p.iterdir(), key=lambda x: x.name.lower())[:60]
    lines = [("[folder] " if x.is_dir() else "") + x.name for x in items if not x.name.startswith(".")]
    return "\n".join(lines) or "(empty)"


def find_file(name: str) -> str:
    """Search Desktop, Documents, Downloads and Pictures for files whose name contains the text.

    Args:
        name: Part of the file name, e.g. "cv" or "report.pdf". Not case sensitive.
    """
    needle, hits = name.lower(), []
    for root in ALLOWED_ROOTS:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")][:50]  # don't crawl forever
            if dirpath.count(os.sep) - str(root).count(os.sep) > 3:
                dirnames[:] = []
            for f in filenames:
                if needle in f.lower():
                    hits.append(str(Path(dirpath) / f))
                    if len(hits) >= 20:
                        return "\n".join(hits)
    return "\n".join(hits) or f"No file with '{name}' in its name."


def open_file(path: str) -> str:
    """Open a file or folder on the PC with its default app (PDF viewer, Word, Explorer...).

    Args:
        path: Full path of the file or folder, e.g. from find_file.
    """
    p = _resolve(path)
    if p is None or not p.exists():
        return f"Error: '{path}' not found or not allowed."
    if _session():
        _session().status(f"Opening {p.name}")
    try:
        if IS_WIN:
            os.startfile(str(p))  # type: ignore[attr-defined]
        elif IS_MAC:
            subprocess.Popen(["open", str(p)])
        else:
            subprocess.Popen(["xdg-open", str(p)])
        return f"Opened {p.name}"
    except Exception as e:  # noqa: BLE001
        return f"Error opening {p.name}: {e}"


def send_file_to_phone(path: str) -> str:
    """Send a file from the PC to the phone, so the user can download it there.

    Args:
        path: Full path of the file, e.g. from find_file.
    """
    p = _resolve(path)
    if p is None or not p.is_file():
        return f"Error: '{path}' is not a file I can send."
    if p.stat().st_size > 200 * 1024 * 1024:
        return "Error: file is bigger than 200 MB."
    token = secrets.token_urlsafe(12)
    shutil.copy2(p, OUTBOX / f"{token}__{p.name}")
    if _session():
        _session().emit({"type": "file", "name": p.name, "url": f"/files/{token}"})
    return f"Sent {p.name} to the phone."


def delete_file(path: str) -> str:
    """Delete a file. Always asks the user to confirm on the phone first.

    Args:
        path: Full path of the file to delete.
    """
    p = _resolve(path)
    if p is None or not p.is_file():
        return f"Error: '{path}' is not a file I can delete."
    if not _session() or not _session().confirm(f"Delete {p.name}? This cannot be undone."):
        return "Cancelled: the user did not confirm."
    p.unlink()
    return f"Deleted {p.name}"


# ----------------------------------------------------------------- apps ---------

def open_app(name: str) -> str:
    """Open an application by name, e.g. "Spotify", "Chrome", "Notepad", "Calculator".

    Args:
        name: The app's name as a user would say it.
    """
    if _session():
        _session().status(f"Opening {name}")
    try:
        if IS_WIN:
            subprocess.Popen(f'start "" "{name}"', shell=True)
        elif IS_MAC:
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name.lower()])
        return f"Asked the system to open {name}. Check the screen."
    except Exception as e:  # noqa: BLE001
        return f"Error opening {name}: {e}"


# ------------------------------------------------------- keyboard & mouse -------

def type_text(text: str) -> str:
    """Type text on the keyboard into whatever is focused on the PC.

    Args:
        text: The text to type.
    """
    try:
        import pyautogui
        pyautogui.typewrite(text, interval=0.02)
        return f"Typed {len(text)} characters."
    except Exception as e:  # noqa: BLE001
        return f"Error typing: {e}"


def press_keys(keys: str) -> str:
    """Press a key or shortcut, e.g. "enter", "ctrl+s", "cmd+space", "alt+f4".

    Args:
        keys: Key names joined with +.
    """
    try:
        import pyautogui
        pyautogui.hotkey(*keys.lower().split("+"))
        return f"Pressed {keys}"
    except Exception as e:  # noqa: BLE001
        return f"Error pressing {keys}: {e}"


def pc_info() -> str:
    """Tell which operating system and user this PC has. Use it when unsure what commands work."""
    return f"{platform.system()} {platform.release()}, user folder {HOME}"


# The Brain turns every function in this list into a tool the AI can call.
TOOLS = [list_files, find_file, open_file, send_file_to_phone, delete_file,
         open_app, type_text, press_keys, pc_info]
