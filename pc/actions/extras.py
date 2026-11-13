"""More things the AI can do: open a website, close an app, scroll, send a whole folder.  (Owner: Hands)"""
import secrets
import subprocess
import sys
import time
import webbrowser
import zipfile
from pathlib import Path
from urllib.parse import quote_plus, urlparse

import pc.actions as actions  # for actions.current_session
from pc.actions import basic, pointer

IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def _session():
    return actions.current_session


def _status(text: str) -> None:
    if _session():
        _session().status(text)


def _ask(question: str) -> bool:
    """Yes/No on the phone. No phone (or one that can't ask) counts as No."""
    confirm = getattr(_session(), "confirm", None)
    return bool(confirm and confirm(question))


# ----------------------------------------------------------------- websites ---------

def _clean_url(url: str) -> str | None:
    """Return a safe http(s) address, or None. 'youtube.com' -> 'https://youtube.com'."""
    url = (url or "").strip().strip('"').strip("'")
    if not url or len(url) > 2000 or any(ch.isspace() for ch in url) or "\\" in url:
        return None  # spaces or a Windows path (C:\...) are not web addresses
    if "://" not in url:
        if "." not in url.split("/")[0]:
            return None
        url = "https://" + url
    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.hostname or "." not in parts.hostname:
        return None  # no file:, javascript:, ms-settings: ... only real websites (example.com)
    if parts.username or parts.password:
        return None  # https://user:pass@... tricks
    return url


def open_url(url: str) -> str:
    """Open a website in the PC's web browser, e.g. "youtube.com" or a full link. To play something on YouTube use https://www.youtube.com/results?search_query=<words>.

    Args:
        url: The web address (http or https only), e.g. "https://www.youtube.com/results?search_query=lofi".
    """
    clean = _clean_url(url)
    if clean is None:
        return f"Error: '{str(url)[:100]}' is not a website address I can open (only http:// or https:// links)."
    host = urlparse(clean).hostname
    _status(f"Opening {host}")
    try:
        if not webbrowser.open(clean, new=2):
            return f"Error: no web browser opened {host}."
    except Exception as e:  # noqa: BLE001
        return f"Error opening {host}: {e}"
    return f"Opened {host} in the browser. Check the screen."


def youtube_search_url(words: str) -> str:
    """The YouTube search link for some words (used in tests and by the docstring above)."""
    return "https://www.youtube.com/results?search_query=" + quote_plus(words)


# ------------------------------------------------------------------ close app -------

# Never close these: the desktop itself, or the programs HomeCall itself runs in.
PROTECTED = {"explorer", "python", "pythonw", "py", "cloudflared", "claude", "powershell", "pwsh",
             "windowsterminal", "cmd", "conhost", "openconsole", "dwm", "winlogon", "csrss",
             "searchhost", "startmenuexperiencehost", "shellexperiencehost", "textinputhost", "lockapp"}


def _windows() -> list[dict]:
    """Every visible top-level window: {"hwnd", "title", "exe"} (Windows only)."""
    if not IS_WIN:
        return []
    import ctypes
    from ctypes import wintypes
    user32, kernel32 = ctypes.windll.user32, ctypes.windll.kernel32
    found: list[dict] = []

    def exe_of(hwnd) -> str:
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = kernel32.OpenProcess(0x1000, False, pid.value)  # PROCESS_QUERY_LIMITED_INFORMATION
        if not handle:
            return ""
        buf, size = ctypes.create_unicode_buffer(512), wintypes.DWORD(512)
        kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
        kernel32.CloseHandle(handle)
        return Path(buf.value).stem.lower()

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def each(hwnd, _):
        if user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):  # 4 = GW_OWNER: skip dialogs/popups
            length = user32.GetWindowTextLengthW(hwnd)
            if length:
                buf = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buf, length + 1)
                found.append({"hwnd": hwnd, "title": buf.value, "exe": exe_of(hwnd)})
        return True

    user32.EnumWindows(each, 0)
    return found


def _app_label(win: dict) -> str:
    """What to call a window's app: Calculator lives in 'applicationframehost', so use its title then."""
    if win["exe"] in ("applicationframehost", ""):
        return win["title"]
    return win["exe"]


def match_windows(name: str, windows: list[dict]) -> list[dict]:
    """The windows of the app the user means: same program name, else the title starts with / contains it."""
    wanted = basic._plain(name).replace(".exe", "").strip()
    if not wanted:
        return []
    usable = [w for w in windows if w["exe"] not in PROTECTED]
    for test in (lambda w: w["exe"] == wanted.replace(" ", ""),
                 lambda w: basic._plain(w["title"]) == wanted,
                 lambda w: basic._plain(w["title"]).endswith(" " + wanted) or basic._plain(w["title"]).startswith(wanted),
                 lambda w: wanted in basic._plain(w["title"])):
        hits = [w for w in usable if test(w)]
        if hits:
            exes = {w["exe"] for w in hits}
            if len(exes) == 1 and "applicationframehost" not in exes:
                return [w for w in usable if w["exe"] in exes]  # every window of that one program
            return hits  # Store apps (Calculator...) share one host program: only the matching windows
    return []


def close_app(name: str) -> str:
    """Close an app's windows, like clicking its X (the app may still ask to save). Asks the user on the phone first, because unsaved work could be lost.

    Args:
        name: The app as the user says it, e.g. "Spotify", "Calculator", "Chrome".
    """
    name = " ".join(str(name or "").split())
    if not name:
        return "Error: tell me which app to close."
    if IS_MAC:
        if any(ch in name for ch in '"\\'):
            return "Error: that's not an app name."
        if not _ask(f"Close {name}? Unsaved work could be lost."):
            return "Cancelled: the user did not confirm."
        _status(f"Closing {name}")
        try:
            ok = subprocess.run(["osascript", "-e", f'tell application "{name}" to quit'],
                                capture_output=True, text=True, timeout=10).returncode == 0
        except Exception:  # noqa: BLE001
            ok = False
        return f"Asked {name} to quit." if ok else f"Error: couldn't close {name}."
    if not IS_WIN:
        return "Error: close_app works on Windows and Mac only."
    hits = match_windows(name, _windows())
    if not hits:
        return f"Error: no open window of '{name}' that I'm allowed to close."
    label = _app_label(hits[0])
    count = f"{len(hits)} {label} windows" if len(hits) > 1 else label
    if not _ask(f"Close {count}? Unsaved work could be lost."):
        return "Cancelled: the user did not confirm."
    _status(f"Closing {label}")
    import ctypes
    for w in hits:
        ctypes.windll.user32.PostMessageW(w["hwnd"], 0x0010, 0, 0)  # WM_CLOSE = clicking the X
    time.sleep(1.5)
    still = {w["hwnd"] for w in _windows()} & {w["hwnd"] for w in hits}
    if still:
        return f"Asked {label} to close, but {len(still)} window(s) are still open (it may be asking to save). Look at the screen."
    return f"Closed {count}."


# ---------------------------------------------------------------------- scroll ------

WHEEL_NOTCH = 120  # Windows counts one mouse-wheel notch as 120


def scroll(direction: str, amount: int = 5, x: int = -1, y: int = -1) -> str:
    """Scroll the page or list under the mouse, like the mouse wheel. Use it to see more of a long page.

    Args:
        direction: up, down, left or right.
        amount: How far, in mouse-wheel notches (about 3 lines each); 1 to 30. Default 5.
        x: Optional: where to scroll, in the screenshot (pixels from the left). -1 = where the mouse already is.
        y: Optional: where to scroll, in the screenshot (pixels from the top). -1 = where the mouse already is.
    """
    direction = str(direction or "").strip().lower()
    if direction not in ("up", "down", "left", "right"):
        return "Error: direction must be up, down, left or right."
    try:
        amount, x, y = int(amount), int(x), int(y)
    except (TypeError, ValueError):
        return "Error: amount, x and y must be whole numbers."
    if not 1 <= amount <= 30:
        return "Error: amount must be from 1 to 30."
    point = None
    if (x, y) != (-1, -1):
        point = pointer.to_screen(x, y)
        if point is None:
            return f"Error: ({x}, {y}) is outside the screenshot."
    _status(f"Scrolling {direction}")
    try:
        import pyautogui
        if point:
            pyautogui.moveTo(*point)
        notches = amount * (WHEEL_NOTCH if IS_WIN else 1)
        if direction in ("up", "down"):
            pyautogui.scroll(notches if direction == "up" else -notches)
        else:
            pyautogui.hscroll(notches if direction == "right" else -notches)
    except Exception as e:  # noqa: BLE001
        return f"Error scrolling: {e}"
    return f"Scrolled {direction} {amount}. Look at the next screenshot."


# ------------------------------------------------------------- send a folder ---------

MAX_FOLDER_BYTES = 200 * 1024 * 1024
MAX_FOLDER_FILES = 5000


def send_folder_to_phone(path: str) -> str:
    """Zip a whole folder and send it to the phone as one .zip download. For a single file use send_file_to_phone.

    Args:
        path: The folder, e.g. "Desktop/ISM" or a full path from list_files/find_file.
    """
    p = basic._resolve(path)
    if p is None or not p.is_dir():
        return f"Error: '{path}' is not a folder I can send."
    if p in [r.resolve() for r in basic.ALLOWED_ROOTS]:
        return "Error: that's a whole Desktop/Documents/Downloads/Pictures folder; pick a folder inside it."
    total, files = 0, []
    for f in p.rglob("*"):
        if f.is_file() and not any(part.startswith(".") for part in f.relative_to(p).parts):
            files.append(f)
            total += f.stat().st_size
            if total > MAX_FOLDER_BYTES:
                return "Error: that folder is bigger than 200 MB."
            if len(files) > MAX_FOLDER_FILES:
                return f"Error: that folder has more than {MAX_FOLDER_FILES} files."
    if not files:
        return f"Error: the folder {p.name} is empty."
    _status(f"Zipping {p.name}")
    token = secrets.token_urlsafe(12)
    target = basic.OUTBOX / f"{token}__{p.name}.zip"
    try:
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
            for f in files:  # exactly the files counted above: no hidden ones
                z.write(f, f.relative_to(p).as_posix())
    except Exception as e:  # noqa: BLE001
        target.unlink(missing_ok=True)
        return f"Error zipping {p.name}: {e}"
    if _session():
        _session().emit({"type": "file", "name": f"{p.name}.zip", "url": f"/files/{token}"})
    return f"Sent {p.name}.zip ({len(files)} files) to the phone."


TOOLS = [open_url, close_app, scroll, send_folder_to_phone]
