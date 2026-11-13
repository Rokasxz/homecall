"""The Mac permissions HomeCall needs, asked for ALL AT ONCE at the start.  (Owner: Server)

macOS gives permissions to the app that started HomeCall (Terminal when you
double-click HomeCall.command) and asks the first time something is used. If
that happens in the middle of a call, the screenshot, click or file list fails.
So start.py asks for everything first, while you are at the PC:

  screen   Screen Recording     see the screen
  control  Accessibility        move the mouse, click, type, press keys
  files    Files and Folders    open Desktop, Documents, Downloads
  apps     Automation           Finder (move to Trash) and System Events (which app is in front)

Windows and Linux need none of these: check() says all OK there.
Each check runs in a FRESH Python process: a running program keeps macOS's old answer.

    python -m pc.permissions          show what is allowed
    python -m pc.permissions --ask    ask for everything that is missing
"""
import json
import os
import subprocess
import sys
from pathlib import Path

IS_MAC = sys.platform == "darwin"
_PANE = "x-apple.systempreferences:com.apple.preference.security?"
ITEMS = [  # key, what the user sees, System Settings page
    ("screen", "See the screen (Screen Recording)", _PANE + "Privacy_ScreenCapture"),
    ("control", "Control mouse and keyboard (Accessibility)", _PANE + "Privacy_Accessibility"),
    ("files", "Open Desktop, Documents, Downloads (Files and Folders)", _PANE + "Privacy_FilesAndFolders"),
    ("apps", "Use Finder and System Events (Automation)", _PANE + "Privacy_Automation"),
]
FOLDERS = ("Desktop", "Documents", "Downloads")
APPLESCRIPTS = {  # harmless commands: the first run of each makes macOS ask "allow controlling ...?"
    "Finder": 'tell application "Finder" to get name',
    "System Events": 'tell application "System Events" to get name of first application process whose frontmost is true',
}


# ------------------------------------------------------- probes (fresh process) ---

def _screen(ask: bool) -> bool:
    import ctypes
    try:
        cg = ctypes.CDLL("/System/Library/Frameworks/CoreGraphics.framework/CoreGraphics")
        cg.CGPreflightScreenCaptureAccess.restype = ctypes.c_bool
        if cg.CGPreflightScreenCaptureAccess():
            return True
        if ask:  # shows macOS's own window once and adds the app to the list
            cg.CGRequestScreenCaptureAccess.restype = ctypes.c_bool
            return bool(cg.CGRequestScreenCaptureAccess())
        return False
    except (OSError, AttributeError):
        return True  # macOS older than 10.15: no such permission


def _control(ask: bool) -> bool:
    import ctypes
    ax = ctypes.CDLL("/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices")
    ax.AXIsProcessTrusted.restype = ctypes.c_bool
    if ax.AXIsProcessTrusted() or not ask:
        return bool(ax.AXIsProcessTrusted())
    try:  # same check, but macOS shows its window and adds the app to the list
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        key = ctypes.c_void_p.in_dll(ax, "kAXTrustedCheckOptionPrompt")
        yes = ctypes.c_void_p.in_dll(cf, "kCFBooleanTrue")
        cf.CFDictionaryCreate.restype = ctypes.c_void_p
        cf.CFDictionaryCreate.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p),
                                          ctypes.POINTER(ctypes.c_void_p), ctypes.c_long,
                                          ctypes.c_void_p, ctypes.c_void_p]
        keys, vals = (ctypes.c_void_p * 1)(key.value), (ctypes.c_void_p * 1)(yes.value)
        options = cf.CFDictionaryCreate(
            None, keys, vals, 1,
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryKeyCallBacks")),
            ctypes.addressof(ctypes.c_char.in_dll(cf, "kCFTypeDictionaryValueCallBacks")))
        ax.AXIsProcessTrustedWithOptions.restype = ctypes.c_bool
        ax.AXIsProcessTrustedWithOptions.argtypes = [ctypes.c_void_p]
        return bool(ax.AXIsProcessTrustedWithOptions(options))
    except (OSError, ValueError, AttributeError):
        return False


def _files() -> bool:
    """Reading each folder once makes macOS ask (the first time) and tells us the answer."""
    ok = True
    for name in FOLDERS:
        folder = Path.home() / name
        if folder.is_dir():
            try:
                os.listdir(folder)
            except PermissionError:
                ok = False
    return ok


def _apps(ask: bool) -> bool:
    """Automation can't be checked without asking: run the commands only when asking is OK."""
    if not ask:
        return True  # unknown: assume fine (start.py asked at the start)
    ok = True
    for script in APPLESCRIPTS.values():
        try:
            r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=90)
            if "-1743" in r.stderr or "Not authorized" in r.stderr:  # the user said no
                ok = False
        except (OSError, subprocess.TimeoutExpired):
            ok = False
    return ok


def _probe(ask: bool, apps: bool) -> dict:
    return {"screen": _screen(ask), "control": _control(ask), "files": _files(), "apps": _apps(apps)}


# ------------------------------------------------------------------ public ---

def check(ask: bool = False, apps: bool | None = None) -> list[dict]:
    """[{key, name, ok, settings}] for every permission. ask=True shows macOS's windows for the missing ones.

    apps=True also tries the Automation commands (they can only be checked by trying them;
    after a "Don't Allow" they fail at once without a window). Default: same as ask.
    """
    if not IS_MAC:
        return [{"key": k, "name": n, "ok": True, "settings": ""} for k, n, _ in ITEMS]
    root = Path(__file__).resolve().parent.parent
    cmd = [sys.executable, "-m", "pc.permissions", "--json"] + (["--ask"] if ask else []) \
        + (["--apps"] if (ask if apps is None else apps) else [])
    try:
        r = subprocess.run(cmd, cwd=root, capture_output=True, text=True, timeout=300 if ask else 30)
        got = json.loads(r.stdout.strip().splitlines()[-1])
    except (OSError, subprocess.TimeoutExpired, ValueError, IndexError):
        got = {}
    return [{"key": k, "name": n, "ok": bool(got.get(k, False)), "settings": url} for k, n, url in ITEMS]


def open_settings(key: str) -> None:
    """Open the System Settings page where this permission is switched on."""
    url = dict((k, u) for k, _, u in ITEMS).get(key)
    if IS_MAC and url:
        subprocess.run(["open", url], check=False)


def starter_app() -> str:
    """Name of the app that started HomeCall (it gets the permissions), e.g. "Terminal"."""
    pid = os.getpid()
    for _ in range(30):
        try:
            out = subprocess.run(["ps", "-o", "ppid=,comm=", "-p", str(pid)],
                                 capture_output=True, text=True, timeout=5).stdout.strip()
        except (OSError, subprocess.TimeoutExpired):
            break
        if not out:
            break
        ppid, _, comm = out.partition(" ")
        if ".app/" in comm:
            return comm.split(".app/")[0].rsplit("/", 1)[-1]
        if ppid.strip() in ("0", "1", ""):
            break
        pid = int(ppid)
    return "Terminal"


if __name__ == "__main__":
    ask = "--ask" in sys.argv
    if "--json" in sys.argv:
        print(json.dumps(_probe(ask, ask or "--apps" in sys.argv) if IS_MAC else {k: True for k, _, _ in ITEMS}))
    else:
        for item in check(ask):
            print(("OK      " if item["ok"] else "MISSING ") + item["name"])
