"""Clicking on the screen.  (Owner: Hands)

The AI sees a screenshot of the MAIN screen, shrunk to at most 1280 px wide
(pc/screen.py, capture_png). It says where to click in THAT picture, and
click_at scales the point up to the real screen, e.g. on a 2880x1800 screen
the picture is 1280x800, so (100, 100) in the picture is (225, 225) on screen.
"""
import inspect
import os
import re
from pathlib import Path

import pc.actions as actions  # for actions.current_session
from pc.actions import uia
from pc.actions.basic import IS_WIN, PROGRAM_EXTS, SPECIAL_FOLDERS, _is_program, _plain

DEFAULT_SHOT_WIDTH = 1280

# Clicking a button with one of these can't be undone: ask on the phone first.
# Written without accents and matched against the button text without accents, so "Ištrinti" matches
# "istrin". A word matches at the START of a word: "send" also catches "Sending", "istrin" "Ištrinkite".
RISKY_WORDS = [
    # English
    "send", "delete", "remove", "bin", "trash", "erase", "discard", "buy", "pay", "purchase", "order",
    "checkout", "transfer", "allow", "accept", "agree", "approve", "grant", "install", "uninstall", "run",
    "confirm", "submit", "post", "publish", "share", "reply", "forward", "upload", "replace", "overwrite",
    "sign", "format", "reset", "shut down", "restart", "log out", "open anyway",
    # Lithuanian (Windows in Lithuanian): siųsti, ištrinti, pašalinti, pirkti, mokėti, leisti/paleisti,
    # patvirtinti, įdiegti, šiukšlinė, atsijungti, išjungti, užsakyti, pateikti, bendrinti, įkelti,
    # skelbti, atsakyti, persiųsti, perrašyti, pakeisti, sutinku, priimti
    "siust", "siunc", "issiust", "persiust", "istrin", "trint", "pasalin", "salint", "pirk", "moket",
    "mokej", "sumok", "leist", "leisk", "paleist", "patvirtin", "idieg", "diegt", "siuksl", "atsijung",
    "isjung", "uzsaky", "pateik", "bendrin", "ikelt", "skelbt", "paskelb", "atsakyt", "perrasy",
    "pakeist", "sutinku", "priimt",
]
_RISKY = re.compile(r"\b(" + "|".join(re.escape(w) for w in RISKY_WORDS) + r")")

# A double-click on one of these RUNS something (open_file would ask first, so a double-click must too).
_PROGRAM_EXT_RE = "|".join(re.escape(ext.lstrip(".")) for ext in sorted(PROGRAM_EXTS))
_PROGRAM = re.compile(r"\.(" + _PROGRAM_EXT_RE + r")\b"
                      r"|\b(setup|installer|install|program|application|script|programa|diegim)")


def is_risky(what: str) -> bool:
    """True if the thing to click sounds like it can't be undone (Send, Delete, Buy, Allow, Ištrinti...)."""
    return bool(_RISKY.search(_plain(what)))


def looks_like_program(what: str) -> bool:
    """True if double-clicking it would start a program (setup.exe, Evil.app, an installer...)."""
    return bool(_PROGRAM.search(_plain(what)))


def _session():
    return actions.current_session


def _ask(question: str) -> bool:
    """Yes/No on the phone. No phone (or one that can't ask) counts as No."""
    confirm = getattr(_session(), "confirm", None)
    return bool(confirm and confirm(question))


# ------------------------------------------------- what is really under the mouse (Windows) ------

_ICON_CONTROLS = {"ControlType.ListItem", "ControlType.Text", "ControlType.Image", "ControlType.DataItem"}


def _real_mouse() -> bool:
    """False when tests swapped in a fake mouse: then nothing real is clicked, so the real screen doesn't matter."""
    import sys
    return IS_WIN and getattr(sys.modules.get("pyautogui"), "__file__", None) is not None


def _thing_under(real_x: int, real_y: int) -> dict:
    """What Windows says is at this screen point: {"name", "control", "process", ...}. {} if unknown/not Windows."""
    if not _real_mouse():
        return {}
    return uia.at(real_x, real_y)


def _desktop_folders() -> list[Path]:
    """Where Desktop icons live: the user's Desktop and the shared (Public) Desktop."""
    folders = [SPECIAL_FOLDERS.get("Desktop")]
    public = os.environ.get("PUBLIC")
    if public:
        folders.append(Path(public) / "Desktop")
    return [f for f in folders if f and f.is_dir()]


def _real_item(shown_name: str) -> Path | None:
    """The file or folder behind an icon label: 'Evil' -> Desktop/Evil.exe (Windows hides extensions)."""
    wanted = shown_name.strip().lower()
    for folder in _desktop_folders():
        try:
            entries = list(folder.iterdir())
        except OSError:
            continue
        for entry in entries:
            if entry.name.lower() == wanted or (entry.is_file() and entry.stem.lower() == wanted):
                return entry
    return None


def _icon_worry(real_x: int, real_y: int, under: dict | None = None) -> str:
    """Why a double-click here needs a Yes/No first, or '' if it's fine.

    Only icons in File Explorer or on the Desktop are checked; double-clicks inside apps are left alone.
    """
    if under is None:
        under = _thing_under(real_x, real_y)
    name = (under.get("name") or "").strip()
    if (under.get("process") or "").lower() != "explorer" or under.get("control") not in _ICON_CONTROLS or not name:
        return ""
    item = _real_item(name)
    if item is None:
        return f"I can't tell what '{name}' is, and a double-click opens it."
    if item.is_file() and _is_program(item):
        return f"It's {item.name}, a program: a double-click starts it."
    return ""


def _shot_width() -> int:
    """The width the AI's screenshot is shrunk to, read from pc/screen.py so we stay in sync."""
    try:
        from pc import screen
        return int(inspect.signature(screen.capture_png).parameters["max_width"].default)
    except Exception:  # noqa: BLE001
        return DEFAULT_SHOT_WIDTH


def _main_screen() -> tuple[int, int, int, int]:
    """left, top, width, height of the main screen in real pixels (the same screen pc/screen.py captures)."""
    try:
        import mss
        maker = getattr(mss, "MSS", None) or mss.mss
        with maker() as sct:
            m = sct.monitors[1]
            return m["left"], m["top"], m["width"], m["height"]
    except Exception:  # noqa: BLE001
        import pyautogui
        w, h = pyautogui.size()
        return 0, 0, int(w), int(h)


def picture_size(screen_w: int, screen_h: int) -> tuple[int, int]:
    """Size of the screenshot the AI sees for a screen of this size (same maths as pc/screen.py)."""
    max_w = _shot_width()
    if screen_w > max_w:
        return max_w, int(screen_h * max_w / screen_w)
    return screen_w, screen_h


def to_screen(x: int, y: int) -> tuple[int, int] | None:
    """Turn a point in the AI's screenshot into a point on the real screen, or None if it's outside."""
    left, top, w, h = _main_screen()
    pic_w, pic_h = picture_size(w, h)
    if not (0 <= x < pic_w and 0 <= y < pic_h):
        return None
    return left + round(x * w / pic_w), top + round(y * h / pic_h)


def click_at(x: int, y: int, what: str, double: bool = False) -> str:
    """Click with the mouse at a point in the screenshot you were given (look at it first, aim at the middle of the button or link). Buttons like Send, Delete, Buy or Allow ask the user on the phone first. To open a file, use open_file instead of double-clicking it.

    Args:
        x: Pixels from the LEFT edge of the screenshot (not of the real screen).
        y: Pixels from the TOP edge of the screenshot.
        what: What you are clicking, as written on the screen, e.g. "Play button" or "Send button".
        double: True for a double-click (e.g. to open a file on the desktop). Default False.
    """
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        return "Error: x and y must be whole numbers (pixels in the screenshot)."
    what = " ".join(str(what or "").split())[:80]
    if not what:
        return "Error: say what you are clicking (what), e.g. 'Play button'."
    left, top, w, h = _main_screen()
    pic_w, pic_h = picture_size(w, h)
    point = to_screen(x, y)
    if point is None:
        return f"Error: ({x}, {y}) is outside the screenshot, which is {pic_w} x {pic_h} pixels."
    real_x, real_y = point
    problem = _guard(real_x, real_y, what, double, _thing_under(real_x, real_y))
    if problem:
        return problem
    clicked = _click(real_x, real_y, what, double)
    if clicked:
        return clicked
    return (f"{'Double-clicked' if double else 'Clicked'} {what} at ({x}, {y}) in the screenshot "
            f"(= {real_x}, {real_y} on the {w}x{h} screen). Look at the next screenshot to see what happened.")


def _guard(real_x: int, real_y: int, what: str, double: bool, under: dict) -> str:
    """Ask Yes/No when this click could do something that can't be undone. Returns 'Cancelled: ...' or ''."""
    real_name = " ".join(str(under.get("name") or "").split())[:80]
    if double and looks_like_program(what):
        if not _ask(f"Double-click '{what}' on the PC? This starts a program."):
            return f"Cancelled: '{what}' looks like a program and the user did not confirm starting it."
    elif double and (worry := _icon_worry(real_x, real_y, under)):
        # The AI's description sounded harmless, but the icon under the mouse is a program
        # (Windows hides ".exe", so "Evil" may really be Evil.exe) or a file we can't identify.
        if not _ask(f"Double-click '{what}' on the PC? {worry}"):
            return f"Cancelled: {worry} The user did not confirm."
    elif is_risky(what):
        if not _ask(f"Click '{what}' on the PC?"):
            return f"Cancelled: the user did not confirm clicking '{what}'."
    elif real_name and is_risky(real_name):
        # The AI said something harmless, but Windows says the button under the mouse is e.g. "Delete".
        if not _ask(f"Click '{real_name}' on the PC? (asked to click '{what}', but the button there is '{real_name}')"):
            return f"Cancelled: the button there is really '{real_name}', and the user did not confirm."
    return ""


def _click(real_x: int, real_y: int, what: str, double: bool) -> str:
    """Show the status and click. Returns an error text, or '' when it clicked."""
    if _session():
        _session().status(f"{'Double-clicking' if double else 'Clicking'} {what}")
    try:
        import pyautogui
        pyautogui.click(real_x, real_y, clicks=2 if double else 1, interval=0.1)
    except Exception as e:  # noqa: BLE001  (e.g. pyautogui's fail-safe when aiming at a screen corner)
        return f"Error clicking: {e}"
    return ""


def _foreground_window() -> int:
    import ctypes
    return int(ctypes.windll.user32.GetForegroundWindow() or 0)


def rank_matches(text: str, hits: list[dict]) -> list[dict]:
    """Best first: enabled, then exact name, then real buttons/links before plain labels, then starts-with, shorter."""
    wanted = _plain(" ".join(text.split()))

    def score(hit: dict) -> tuple:
        name = _plain(" ".join(str(hit.get("name") or "").split()))
        exact, starts = name == wanted, name.startswith(wanted)
        return (not hit.get("enabled", True), not exact, not hit.get("preferred", True), not starts, len(name))
    return sorted((h for h in hits if wanted in _plain(str(h.get("name") or ""))), key=score)


def click_text(text: str, double: bool = False, which: int = 1) -> str:
    """Click a button, link, tab or menu item in the window in front by the words written on it, e.g. "Play" or "Next". More reliable than click_at when the thing has a name. Risky buttons (Send, Delete...) ask on the phone first.

    Args:
        text: The words on the button or link, e.g. "Play" or "Sign in". Not case sensitive.
        double: True for a double-click. Default False.
        which: If several things have that name, which one: 1 = the best match (default), 2 = the next...
    """
    text = " ".join(str(text or "").split())[:80]
    if not text:
        return "Error: tell me the words on the button (text)."
    if not IS_WIN:
        return "Error: click_text works on Windows only; use click_at with the position in the screenshot."
    try:
        which = int(which)
    except (TypeError, ValueError):
        return "Error: which must be a whole number (1 = the best match)."
    hits = rank_matches(text, uia.find(_foreground_window(), text))
    if not hits:
        return f"Error: I can't see a button or link called '{text}' in the window in front. Try click_at with its position."
    if not 1 <= which <= len(hits):
        return f"Error: there are only {len(hits)} things called '{text}'."
    hit = hits[which - 1]
    real_name = " ".join(str(hit.get("name") or "").split())[:80]
    if not hit.get("enabled", True):
        return f"Error: '{real_name}' is greyed out (disabled) right now."
    real_x, real_y = int(hit["x"]), int(hit["y"])
    problem = _guard(real_x, real_y, real_name, double, hit)  # checks the REAL name from Windows
    if problem:
        return problem
    clicked = _click(real_x, real_y, real_name, double)
    if clicked:
        return clicked
    others = f" ({len(hits)} things matched; use which=2 for the next one)" if len(hits) > 1 else ""
    return f"{'Double-clicked' if double else 'Clicked'} '{real_name}'.{others} Look at the next screenshot to see what happened."


TOOLS = [click_at, click_text]
