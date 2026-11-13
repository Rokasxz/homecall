"""The PC's clipboard (what you copied with Ctrl+C).  (Owner: Hands)

Reading asks Yes/No on the phone first: people often copy passwords, and whatever the
tool returns is sent to the AI.
"""
import shutil
import subprocess
import sys

import pc.actions as actions  # for actions.current_session

IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"
MAX_CHARS = 3000
CF_UNICODETEXT = 13


def _session():
    return actions.current_session


def _ask(question: str) -> bool:
    confirm = getattr(_session(), "confirm", None)
    return bool(confirm and confirm(question))


def _win_api():
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    user32.OpenClipboard.argtypes = [wintypes.HWND]
    user32.GetClipboardData.restype = wintypes.HANDLE
    user32.SetClipboardData.argtypes = [wintypes.UINT, wintypes.HANDLE]
    user32.SetClipboardData.restype = wintypes.HANDLE
    kernel32.GlobalAlloc.argtypes = [wintypes.UINT, ctypes.c_size_t]
    kernel32.GlobalAlloc.restype = wintypes.HGLOBAL
    kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
    kernel32.GlobalLock.restype = ctypes.c_void_p
    kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]
    return ctypes, user32, kernel32


def _open_clipboard(user32) -> bool:
    import time
    for _ in range(10):  # another program may have it open for a moment
        if user32.OpenClipboard(None):
            return True
        time.sleep(0.05)
    return False


def read_clipboard_text() -> str | None:
    """The text on the clipboard ('' if it holds no text), or None if it can't be read."""
    if IS_WIN:
        ctypes, user32, kernel32 = _win_api()
        if not _open_clipboard(user32):
            return None
        try:
            handle = user32.GetClipboardData(CF_UNICODETEXT)
            if not handle:
                return ""
            ptr = kernel32.GlobalLock(handle)
            try:
                return ctypes.wstring_at(ptr) if ptr else ""
            finally:
                kernel32.GlobalUnlock(handle)
        finally:
            user32.CloseClipboard()
    command = ["pbpaste"] if IS_MAC else (["xclip", "-selection", "clipboard", "-o"] if shutil.which("xclip") else None)
    if not command:
        return None
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return None


def write_clipboard_text(text: str) -> bool:
    """Put text on the clipboard. True if it worked."""
    if IS_WIN:
        ctypes, user32, kernel32 = _win_api()
        data = text.encode("utf-16-le") + b"\0\0"
        mem = kernel32.GlobalAlloc(0x0002, len(data))  # GMEM_MOVEABLE
        if not mem:
            return False
        ptr = kernel32.GlobalLock(mem)
        ctypes.memmove(ptr, data, len(data))
        kernel32.GlobalUnlock(mem)
        if not _open_clipboard(user32):
            kernel32.GlobalFree(mem)
            return False
        try:
            user32.EmptyClipboard()
            return bool(user32.SetClipboardData(CF_UNICODETEXT, mem))  # Windows owns the memory now
        finally:
            user32.CloseClipboard()
    command = ["pbcopy"] if IS_MAC else (["xclip", "-selection", "clipboard"] if shutil.which("xclip") else None)
    if not command:
        return False
    try:
        return subprocess.run(command, input=text, text=True, timeout=5).returncode == 0
    except Exception:  # noqa: BLE001
        return False


def get_clipboard() -> str:
    """Read the text the user copied on the PC (Ctrl+C), e.g. "send me what I copied". Asks the user on the phone first, because it could be a password."""
    if not _ask("Read what you copied on the PC? (It could be a password.)"):
        return "Cancelled: the user did not confirm reading the clipboard."
    if _session():
        _session().status("Reading the clipboard")
    try:
        text = read_clipboard_text()
    except Exception as e:  # noqa: BLE001
        return f"Error reading the clipboard: {e}"
    if text is None:
        return "Error: I can't read the clipboard on this PC."
    if not text.strip():
        return "The clipboard has no text (it may hold a picture or a file, or nothing)."
    if len(text) > MAX_CHARS:
        return f"The clipboard holds {len(text)} characters; the first {MAX_CHARS}:\n{text[:MAX_CHARS]}"
    return f"The clipboard holds:\n{text}"


def set_clipboard(text: str) -> str:
    """Put text on the PC's clipboard, so the user can paste it there with Ctrl+V (e.g. an address said on the phone).

    Args:
        text: The text to put on the clipboard (max 10000 characters).
    """
    text = str(text or "")
    if not text:
        return "Error: tell me the text to put on the clipboard."
    if len(text) > 10_000:
        return "Error: that's too much text for the clipboard (max 10000 characters)."
    if _session():
        _session().status("Copying to the clipboard")
    try:
        ok = write_clipboard_text(text)
    except Exception as e:  # noqa: BLE001
        return f"Error writing the clipboard: {e}"
    return f"Put {len(text)} characters on the clipboard: paste with Ctrl+V." if ok else "Error: I can't write the clipboard on this PC."


TOOLS = [get_clipboard, set_clipboard]
