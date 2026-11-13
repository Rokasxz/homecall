"""Starter tools. Real but minimal; the Hands owner extends and improves them."""
import difflib
import itertools
import json
import os
import platform
import secrets
import shutil
import subprocess
import sys
import time
import unicodedata
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pc.actions as actions  # for actions.current_session

HOME = Path.home()
IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def _windows_folder(guid: str) -> Path | None:
    """Ask Windows where a special folder really is (OneDrive often moves Desktop/Documents)."""
    try:
        import ctypes
        import uuid
        folder_id = ctypes.create_string_buffer(uuid.UUID(guid).bytes_le, 16)
        out = ctypes.c_wchar_p()
        if ctypes.windll.shell32.SHGetKnownFolderPath(folder_id, 0, None, ctypes.byref(out)) != 0:
            return None
        path = out.value
        ctypes.windll.ole32.CoTaskMemFree(out)
        return Path(path) if path else None
    except Exception:  # noqa: BLE001
        return None


def _special_folders() -> dict[str, Path]:
    folders = {name: HOME / name for name in ("Desktop", "Documents", "Downloads", "Pictures")}
    if IS_WIN:
        guids = {"Desktop": "B4BFCC3A-DB2C-424C-B029-7FE99A87C641",
                 "Documents": "FDD39AD0-238F-46AF-ADB4-6C85480369C7",
                 "Downloads": "374DE290-123F-4565-9164-39C4925E467B",
                 "Pictures": "33E28130-4E1E-4676-835A-98395C3BC3BB"}
        for name, guid in guids.items():
            real = _windows_folder(guid)
            if real:
                folders[name] = real
    return folders


# The friendly names the AI can use ("Desktop") and where they really are on this PC.
SPECIAL_FOLDERS = _special_folders()
# The AI may only touch files inside these folders. Add more if you need them.
ALLOWED_ROOTS = list(SPECIAL_FOLDERS.values())
OUTBOX = Path(__file__).resolve().parent.parent / "outbox"  # files sent to the phone land here
OUTBOX.mkdir(exist_ok=True)


def _resolve(path_or_name: str) -> Path | None:
    """Turn 'Downloads', 'Desktop/cv.pdf', '~/Documents/a.pdf' or a full path into a safe Path, or None."""
    try:
        p = Path(os.path.expanduser(path_or_name.strip().strip('"')))
        if not p.is_absolute() and p.parts:
            first, rest = p.parts[0].lower(), p.parts[1:]
            named = {k.lower(): v for k, v in SPECIAL_FOLDERS.items()}
            named.update({r.name.lower(): r for r in ALLOWED_ROOTS})  # the allowed folders win
            p = named[first].joinpath(*rest) if first in named else HOME / p
        p = p.resolve()
    except (ValueError, OSError):  # e.g. a null character or a broken path
        return None
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
    lines = [("[folder] " if x.is_dir() else "") + x.name for x in items
             if not x.name.startswith((".", "~$")) and x.name.lower() != "desktop.ini"]
    return "\n".join(lines) or "(empty)"


# What people say for a file -> other words that may be in its name (English + Lithuanian).
_CV = ["cv", "curriculum vitae", "curriculum", "resume", "gyvenimo aprasymas"]
_PHOTO = ["photo", "picture", "image", "img", "nuotrauka", "foto"]
SYNONYMS = {
    "cv": _CV, "resume": _CV, "curriculum vitae": _CV,
    "photo": _PHOTO, "picture": _PHOTO, "image": _PHOTO,
    "invoice": ["invoice", "saskaita", "faktura"],
    "report": ["report", "ataskaita"],
    "draft": ["draft", "juodrastis"],
    "notes": ["notes", "note", "uzrasai"],
    "presentation": ["presentation", "slides", "pristatymas", "skaidres"],
    "contract": ["contract", "agreement", "sutartis"],
    "letter": ["letter", "laiskas"],
}
SKIP_DIRS = {"node_modules", "__pycache__", ".venv", "venv", "site-packages"}
MAX_HITS = 20


def _plain(text: str) -> str:
    """Lowercase without accents: 'Ataskaitą' -> 'ataskaita', so 'ataskaita' finds it."""
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _match_score(filename: str, phrases: list[str]) -> int:
    """0 = no match. 4 = the whole name, 3 = the start, 2 = inside, 1 = all words, scattered."""
    stem, full = _plain(Path(filename).stem), _plain(filename)
    best = 0
    for phrase in phrases:
        if not all(word in full for word in phrase.split()):
            continue
        if stem == phrase:
            score = 4
        elif stem.startswith(phrase):
            score = 3
        elif phrase in full:
            score = 2
        else:
            score = 1
        best = max(best, score)
    return best


def find_file(name: str) -> str:
    """Search Desktop, Documents, Downloads and Pictures for a file by name; best match and newest first. Knows synonyms: "cv" also finds "Curriculum Vitae" and "resume".

    Args:
        name: Part of the file name, e.g. "cv", "report 2024" or "photo.jpg". Not case sensitive.
    """
    wanted = _plain(" ".join(name.split()))
    if not wanted:
        return "Error: tell me part of the file name."
    phrases = list(dict.fromkeys([wanted] + SYNONYMS.get(wanted, [])))
    found: list[tuple[int, float, str]] = []
    for root in ALLOWED_ROOTS:
        if not root.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".") and d not in SKIP_DIRS][:50]
            if dirpath.count(os.sep) - str(root).count(os.sep) > 3:
                dirnames[:] = []  # don't crawl forever
            for f in filenames:
                if f.startswith("~$"):  # Office lock files
                    continue
                score = _match_score(f, phrases)
                if score:
                    p = Path(dirpath) / f
                    try:
                        modified = p.stat().st_mtime
                    except OSError:
                        modified = 0.0
                    found.append((score, modified, str(p)))
            if len(found) >= 500:
                break
    if not found:
        return f"No file with '{name}' (or a similar word) in its name."
    found.sort(key=lambda hit: (-hit[0], -hit[1]))  # best match first, then newest
    more = f" (showing the first {MAX_HITS})" if len(found) > MAX_HITS else ""
    return f"Found {len(found)}, best match and newest first{more}:\n" + "\n".join(p for _, _, p in found[:MAX_HITS])


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


TEXT_TYPES = {".txt", ".md", ".csv", ".log", ".json", ".xml", ".html", ".htm", ".ini", ".yaml", ".yml", ".py", ".js"}
MAX_CHARS = 3000


def _read_plain(p: Path) -> str:
    data = p.read_bytes()[:200_000]
    for encoding in ("utf-8-sig", "cp1257"):  # cp1257 = older Windows files with Lithuanian letters
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _read_docx(p: Path) -> str:
    w = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    with zipfile.ZipFile(p) as z:
        root = ElementTree.fromstring(z.read("word/document.xml"))
    paragraphs = []
    for para in root.iter(f"{w}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{w}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{w}tab":
                parts.append("\t")
            elif node.tag in (f"{w}br", f"{w}cr"):
                parts.append("\n")
        paragraphs.append("".join(parts))
    return "\n".join(paragraphs)


def _read_pdf(p: Path) -> str:
    import pypdf  # optional: only works if the lead adds pypdf to requirements.txt
    reader = pypdf.PdfReader(str(p))
    text = []
    for page in reader.pages[:10]:
        text.append(page.extract_text() or "")
        if sum(len(t) for t in text) > MAX_CHARS:
            break
    return "\n".join(text)


def read_file_text(path: str) -> str:
    """Read the text inside a document (.txt, .md, .csv, .docx, ...) and return the first 3000 characters.

    Args:
        path: Full path of the file, e.g. from find_file.
    """
    p = _resolve(path)
    if p is None or not p.is_file():
        return f"Error: '{path}' is not a file I can read."
    if _session():
        _session().status(f"Reading {p.name}")
    ext = p.suffix.lower()
    try:
        if ext in TEXT_TYPES:
            text = _read_plain(p)
        elif ext == ".docx":
            text = _read_docx(p)
        elif ext == ".pdf":
            try:
                text = _read_pdf(p)
            except ImportError:
                return f"Error: I can't read PDF files yet. I can open {p.name} on the screen or send it to the phone."
        else:
            return f"Error: I can't read {ext or 'this kind of'} files. I can read .txt, .md, .csv and .docx."
    except Exception as e:  # noqa: BLE001
        return f"Error reading {p.name}: {e}"
    text = text.strip()
    if not text:
        return f"{p.name} has no readable text (it may be a scanned image)."
    if len(text) > MAX_CHARS:
        return f"{p.name}, first {MAX_CHARS} of {len(text)} characters:\n{text[:MAX_CHARS]}"
    return f"{p.name}:\n{text}"


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

_start_menu_apps: dict[str, str] | None = None  # app name -> Windows AppID, read once


def _windows_apps() -> dict[str, str]:
    """Every app in the Windows Start menu (normal and Microsoft Store apps), name -> AppID."""
    global _start_menu_apps
    if not _start_menu_apps:  # empty = not read yet, or the last try failed: try again
        _start_menu_apps = {}
        try:
            out = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"],
                capture_output=True, timeout=20, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            apps = json.loads(out.stdout.decode("utf-8", errors="replace") or "[]")
            for app in apps if isinstance(apps, list) else [apps]:
                if app.get("Name") and app.get("AppID"):
                    _start_menu_apps[app["Name"]] = app["AppID"]
        except Exception:  # noqa: BLE001
            pass
    return _start_menu_apps


def _match_app(name: str, apps: dict[str, str]) -> str | None:
    """Pick the Start menu entry that best matches what the user said ("chrome" -> "Google Chrome")."""
    wanted = name.lower().strip()
    names = [n for n in apps if "uninstall" not in n.lower()]
    for test in (lambda n: n.lower() == wanted,
                 lambda n: n.lower().startswith(wanted),
                 lambda n: wanted in n.lower().split(),
                 lambda n: wanted in n.lower()):
        found = sorted((n for n in names if test(n)), key=len)
        if found:
            return found[0]
    return None


def open_app(name: str) -> str:
    """Open an application by name, e.g. "Spotify", "Chrome", "Notepad", "Calculator".

    Args:
        name: The app's name as a user would say it.
    """
    if _session():
        _session().status(f"Opening {name}")
    try:
        if IS_WIN:
            apps = _windows_apps()
            found = _match_app(name, apps)
            if found:
                subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{apps[found]}"])
                return f"Opened {found}."
            exe = shutil.which(name) or shutil.which(name.replace(" ", "") + ".exe")
            if exe:  # programs without a Start menu entry, e.g. "calc", "mspaint"
                subprocess.Popen([exe])
                return f"Opened {Path(exe).stem}."
            close = difflib.get_close_matches(name, list(apps), n=3, cutoff=0.5)
            hint = f" Did you mean: {', '.join(close)}?" if close else ""
            return f"Error: no app called '{name}' on this PC.{hint}"
        if IS_MAC:
            result = subprocess.run(["open", "-a", name], capture_output=True, text=True, timeout=15)
            if result.returncode != 0:
                return f"Error: no app called '{name}' on this Mac."
            return f"Opened {name}."
        subprocess.Popen([name.lower()])
        return f"Asked the system to open {name}. Check the screen."
    except Exception as e:  # noqa: BLE001
        return f"Error opening {name}: {e}"


# ------------------------------------------------------- keyboard & mouse -------

def _type_windows(text: str) -> None:
    """Type any characters (also ą, č, ė, š, ž, emoji) by sending them to Windows as Unicode key presses."""
    import ctypes
    from ctypes import wintypes

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class MOUSEINPUT(ctypes.Structure):  # only here so INPUT has the size Windows expects
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG), ("mouseData", wintypes.DWORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_size_t)]

    class INPUT(ctypes.Structure):
        class _U(ctypes.Union):
            _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]
        _anonymous_ = ("u",)
        _fields_ = [("type", wintypes.DWORD), ("u", _U)]

    KEYUP, UNICODE, VK_RETURN, VK_TAB = 0x0002, 0x0004, 0x0D, 0x09
    send = ctypes.windll.user32.SendInput

    def press(vk: int = 0, scan: int = 0, flags: int = 0) -> None:
        down, up = INPUT(type=1), INPUT(type=1)
        down.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
        up.ki = KEYBDINPUT(vk, scan, flags | KEYUP, 0, 0)
        if send(2, (INPUT * 2)(down, up), ctypes.sizeof(INPUT)) != 2:
            raise OSError("Windows blocked the key presses (is an admin window in front?)")
        time.sleep(0.004)

    for ch in text.replace("\r\n", "\n"):
        if ch == "\n":
            press(vk=VK_RETURN)
        elif ch == "\t":
            press(vk=VK_TAB)
        else:
            units = ch.encode("utf-16-le")
            for i in range(0, len(units), 2):  # emoji are two UTF-16 units
                press(scan=int.from_bytes(units[i:i + 2], "little"), flags=UNICODE)


def type_text(text: str) -> str:
    """Type text on the keyboard into whatever is focused on the PC.

    Args:
        text: The text to type.
    """
    if len(text) > 5000:
        return "Error: that's too much text to type at once (max 5000 characters)."
    try:
        import pyautogui
        skipped = 0
        # Plain letters go through pyautogui; ą, č, ė, š, ž... through Windows' Unicode typing.
        for plain, chunk in itertools.groupby(text, key=str.isascii):
            chunk = "".join(chunk)
            if plain:
                pyautogui.typewrite(chunk, interval=0.02)
            elif IS_WIN:
                _type_windows(chunk)
            else:
                skipped += len(chunk)
        note = f" ({skipped} special characters could not be typed)" if skipped else ""
        return f"Typed {len(text) - skipped} characters.{note}"
    except Exception as e:  # noqa: BLE001
        return f"Error typing: {e}"


KEY_ALIASES = {"control": "ctrl", "escape": "esc", "return": "enter", "del": "delete",
               "pgup": "pageup", "pgdn": "pagedown", "spacebar": " ", "space": "space"}
SUPER_KEYS = {"cmd", "command", "win", "windows", "super", "meta", "start"}


def _key_name(key: str) -> str:
    key = KEY_ALIASES.get(key, key)
    if key in SUPER_KEYS:
        return "command" if IS_MAC else "win"
    if key == "option":
        return "option" if IS_MAC else "alt"
    return key


def press_keys(keys: str) -> str:
    """Press a key or shortcut, e.g. "enter", "ctrl+s", "alt+tab", "win+d". "cmd" works as the Windows key and vice versa.

    Args:
        keys: Key names joined with +.
    """
    try:
        import pyautogui
        names = [_key_name(k.strip()) for k in keys.lower().split("+") if k.strip()]
        valid = getattr(pyautogui, "KEYBOARD_KEYS", None)
        unknown = [k for k in names if valid is not None and k not in valid]
        if not names or unknown:  # check BEFORE pressing, so nothing is left half-pressed
            return f"Error: unknown key name(s): {', '.join(unknown) or keys}. Use names like ctrl, alt, shift, win, enter, tab, f5, a."
        pyautogui.hotkey(*names)
        return f"Pressed {keys}"
    except Exception as e:  # noqa: BLE001
        return f"Error pressing {keys}: {e}"


def pc_info() -> str:
    """Tell which operating system and user this PC has. Use it when unsure what commands work."""
    folders = ", ".join(f"{k} = {v}" for k, v in SPECIAL_FOLDERS.items())
    return f"{platform.system()} {platform.release()}, user folder {HOME}. Folders: {folders}"


# The Brain turns every function in this list into a tool the AI can call.
TOOLS = [list_files, find_file, open_file, read_file_text, send_file_to_phone, delete_file,
         open_app, type_text, press_keys, pc_info]
