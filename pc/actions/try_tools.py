"""Try every Hands tool on this PC and print what happens.  (Owner: Hands)

    python -m pc.actions.try_tools          safe tests: a temporary folder only, your real files are never touched
    python -m pc.actions.try_tools --gui    also opens a test file and Calculator on the screen
    python -m pc.actions.try_tools --keys   also types into a small window of its own and checks every letter
                                            (hands off the keyboard and mouse for ~5 seconds!)
    python -m pc.actions.try_tools --click  also clicks a button in a small window of its own and checks it was pressed

Nothing real is deleted: the only thing removed at the end is the temporary
test folder this script made itself, and its own copies in pc/outbox.
"""
import platform
import shutil
import sys
import tempfile
import time
import zipfile
from pathlib import Path

import pc.actions as actions
from pc.actions import basic, media, pointer, power

RESULTS: list[tuple[bool, str]] = []


class FakeSession:
    """Pretends to be the phone: prints what the tools send and answers Yes/No questions."""

    def __init__(self, answer: bool):
        self.answer, self.sent = answer, []

    def emit(self, event: dict) -> None:
        self.sent.append(event)
        print(f"      phone <- {event}")

    def status(self, text: str) -> None:
        self.emit({"type": "status", "text": text})

    def confirm(self, question: str, timeout: float = 60) -> bool:
        print(f"      phone asks: {question!r} -> taps {'Yes' if self.answer else 'No'}")
        return self.answer


def check(label: str, result: str, ok: bool) -> None:
    RESULTS.append((ok, label))
    shown = result if len(result) < 300 else result[:300] + " ..."
    print(f"  {'PASS' if ok else 'FAIL'}  {label}")
    print("      -> " + shown.replace("\n", "\n         "))


def make_docx(path: Path, paragraphs: list[str]) -> None:
    """A tiny but real Word file (a .docx is a zip with XML inside)."""
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    xml = ('<?xml version="1.0" encoding="UTF-8"?><w:document xmlns:w='
           '"http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           f"<w:body>{body}</w:body></w:document>")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)


def safe_tests(tmp: Path) -> None:
    print("\nReal folders the AI may use on this PC:")
    for name, path in basic.SPECIAL_FOLDERS.items():
        print(f"      {name:<10} {path}  {'(exists)' if path.exists() else '(MISSING)'}")

    r = basic.pc_info()
    check("pc_info names the OS", r, platform.system() in r)

    # From here on the tools only see the temporary folder.
    saved_roots = basic.ALLOWED_ROOTS
    basic.ALLOWED_ROOTS = [tmp]
    try:
        cv = tmp / "Mantas CV.txt"
        cv.write_text("Mantas, Kaunas. Skills: Python, šachmatai, žvejyba.", encoding="utf-8")
        (tmp / "old draft.txt").write_text("delete me later", encoding="utf-8")
        (tmp / "senas.txt").write_bytes("Ačiū, labas".encode("cp1257"))  # an old-style Windows file
        (tmp / "big.md").write_text("x" * 10_000, encoding="utf-8")
        (tmp / "photo.png").write_bytes(b"\x89PNG fake")
        make_docx(tmp / "Cover letter.docx", ["Dear team,", "I love Python and ąžuolai."])
        (tmp / "Projects" / "deep").mkdir(parents=True)
        (tmp / "Projects" / "deep" / "plan.txt").write_text("the plan", encoding="utf-8")
        (tmp / "~$lockfile.docx").write_text("office lock file", encoding="utf-8")

        print("\nlist_files")
        r = basic.list_files(str(tmp))
        check("lists files and folders", r, "Mantas CV.txt" in r and "[folder] Projects" in r)
        check("hides Office lock files (~$...)", r, "~$" not in r)
        r = basic.list_files(tmp.name)
        check("accepts the folder's short name", r, "Mantas CV.txt" in r)
        r = basic.list_files("C:\\Windows" if sys.platform == "win32" else "/etc")
        check("refuses a folder outside the allowed ones", r, r.startswith("Error"))

        print("\nfind_file")
        import os
        now = time.time()
        (tmp / "Curriculum Vitae 2019.pdf").write_bytes(b"%PDF fake")
        os.utime(tmp / "Curriculum Vitae 2019.pdf", (now - 9e6, now - 9e6))  # years old
        (tmp / "Resume.docx").write_bytes(b"PK fake")
        (tmp / "Ataskaitą.docx").write_bytes(b"PK fake")
        (tmp / "notes old.txt").write_text("old", encoding="utf-8")
        os.utime(tmp / "notes old.txt", (now - 1e6, now - 1e6))
        (tmp / "notes new.txt").write_text("new", encoding="utf-8")
        r = basic.find_file("cv")
        check("finds 'cv'", r, "Mantas CV.txt" in r)
        check("'cv' also finds 'Curriculum Vitae' and 'Resume'", r,
              "Curriculum Vitae 2019.pdf" in r and "Resume.docx" in r)
        r = basic.find_file("resume")
        check("'resume' finds the CV files too", r, "Mantas CV.txt" in r and "Curriculum Vitae 2019.pdf" in r)
        r = basic.find_file("notes")
        check("newest file first", r, r.index("notes new.txt") < r.index("notes old.txt"))
        r = basic.find_file("ataskaita")
        check("finds 'Ataskaitą' without typing the accent", r, "Ataskaitą.docx" in r)
        r = basic.find_file("mantas cv")
        check("two words find 'Mantas CV.txt'", r, "Mantas CV.txt" in r)
        r = basic.find_file("PLAN")
        check("finds a file 2 folders deep, any letter case", r, "plan.txt" in r)
        r = basic.find_file("zzz-nothing")
        check("says when nothing is found", r, r.startswith("No file"))
        r = basic.find_file("   ")
        check("empty search gives an error", r, r.startswith("Error"))

        print("\nread_file_text")
        r = basic.read_file_text(str(cv))
        check("reads a .txt with Lithuanian letters", r, "šachmatai, žvejyba" in r)
        r = basic.read_file_text(str(tmp / "senas.txt"))
        check("reads an old Windows (cp1257) file", r, "Ačiū" in r)
        r = basic.read_file_text(str(tmp / "Cover letter.docx"))
        check("reads a Word .docx", r, "Dear team," in r and "ąžuolai" in r)
        r = basic.read_file_text(str(tmp / "big.md"))
        check("cuts long files at 3000 characters", r, "first 3000 of 10000" in r and len(r) < 3100)
        r = basic.read_file_text(str(tmp / "photo.png"))
        check("politely refuses a picture", r, r.startswith("Error"))
        r = basic.read_file_text("C:\\Windows\\win.ini" if sys.platform == "win32" else "/etc/hosts")
        check("refuses a file outside the allowed folders", r, r.startswith("Error"))

        print("\nsend_file_to_phone")
        phone = FakeSession(answer=False)
        actions.current_session = phone
        r = basic.send_file_to_phone(str(cv))
        sent = [e for e in phone.sent if e.get("type") == "file"]
        token = sent[0]["url"].rsplit("/", 1)[-1] if sent else ""
        copies = list(basic.OUTBOX.glob(f"{token}__*")) if token else []
        check("sends a 'file' message and puts a copy in pc/outbox", r, bool(sent) and bool(copies))
        for c in copies:
            c.unlink()  # our own test copy
        r = basic.send_file_to_phone(str(tmp / "Projects"))
        check("refuses to send a folder", r, r.startswith("Error"))

        print("\ndelete_file (always answers No, nothing is deleted)")
        draft = tmp / "old draft.txt"
        r = basic.delete_file(str(draft))
        check("asks first; 'No' keeps the file", r, r.startswith("Cancelled") and draft.exists())
        actions.current_session = None
        r = basic.delete_file(str(draft))
        check("without a phone it refuses", r, r.startswith("Cancelled") and draft.exists())
        r = basic.delete_file("C:\\Windows\\win.ini" if sys.platform == "win32" else "/etc/hosts")
        check("refuses a file outside the allowed folders", r, r.startswith("Error"))

        print("\nopen_file with programs (phone answers No, so nothing runs)")
        for prog in ("setup.exe", "run-me.bat", "script.sh"):
            (tmp / prog).write_text("echo pwned", encoding="utf-8")
        phone = FakeSession(answer=False)
        actions.current_session = phone
        r = basic.open_file(str(tmp / "setup.exe"))
        check("asks before running a .exe; 'No' cancels", r, r.startswith("Cancelled"))
        actions.current_session = None
        r = basic.open_file(str(tmp / "run-me.bat"))
        check("without a phone it refuses to run a .bat", r, r.startswith("Cancelled"))
        r = basic.open_file(str(tmp / "script.sh"))
        check("same for a .sh script", r, r.startswith("Cancelled"))

        print("\nread_file_text with a huge .docx")
        make_docx(tmp / "huge.docx", ["x" * (6 * 1024 * 1024)])
        r = basic.read_file_text(str(tmp / "huge.docx"))
        check("refuses a .docx whose text part is over 5 MB", r, r.startswith("Error") and "too big" in r)
    finally:
        basic.ALLOWED_ROOTS = saved_roots
        actions.current_session = None

    print("\npress_keys (only wrong names, so nothing is pressed)")
    r = basic.press_keys("ctrl+nosuchkey")
    check("rejects an unknown key before pressing anything", r, r.startswith("Error") and "nosuchkey" in r)
    check("'cmd' means the Windows key on Windows", basic._key_name("cmd"),
          basic._key_name("cmd") == ("win" if sys.platform == "win32" else "command" if sys.platform == "darwin" else "win"))

    print("\nopen_app (only looks the apps up, opens nothing)")
    if sys.platform == "win32":
        apps = basic._windows_apps()
        check("reads the Start menu app list", f"{len(apps)} apps", len(apps) > 5)
        for said in ("Calculator", "Notepad"):
            found = basic._match_app(said, apps)
            check(f"'{said}' is found", str(found), found is not None)
        found = basic._match_app("Spotify", apps)
        print(f"      (Spotify -> {found or 'not installed'})")
    r = basic.open_app("NoSuchAppXyz123")
    check("an unknown app gives an error, not a fake 'done'", r, r.startswith("Error"))
    for bad in ("C:\\Users\\me\\Downloads\\evil.exe", "~/Downloads/Evil.app", "/tmp/evil.sh", "..\\evil"):
        r = basic.open_app(bad)
        check(f"refuses a path as an app name: {bad}", r, r.startswith("Error") and "NAME" in r)

    print("\ntyping into a terminal (pretend a terminal is in front; nothing is pressed)")
    real_foreground = basic._foreground_exe
    basic._foreground_exe = lambda: "powershell.exe"
    try:
        actions.current_session = None
        r = basic.press_keys("enter")
        check("Enter in a terminal without a phone is refused", r, r.startswith("Cancelled"))
        r = basic.type_text("dir\n")
        check("typing a line + Enter in a terminal without a phone is refused", r, r.startswith("Cancelled"))
        phone = FakeSession(answer=False)
        actions.current_session = phone
        r = basic.press_keys("enter")
        check("Enter in a terminal asks on the phone; 'No' cancels", r, r.startswith("Cancelled"))
    finally:
        basic._foreground_exe = real_foreground
        actions.current_session = None

    print("\nmedia_key (only wrong input here; a real press is under --gui)")
    r = media.media_key("dance")
    check("unknown action gives an error", r, r.startswith("Error"))
    r = media.media_key("volume up", 0)
    check("times out of range gives an error", r, r.startswith("Error"))
    r = media.media_key("volume up", "lots")
    check("times that isn't a number gives an error", r, r.startswith("Error"))

    print("\nMac paths (pretend to be a Mac; AppleScript is faked, nothing really happens)")
    scripts: list[str] = []

    def fake_osascript(script: str) -> tuple[bool, str]:
        scripts.append(script)
        if script == 'application "Spotify" is running':
            return True, "true"
        return True, ""

    real_mac, real_osa = media.IS_MAC, media._osascript
    media.IS_MAC, media._osascript = True, fake_osascript
    try:
        r = media.media_key("next")
        check("Mac: 'next' goes to Spotify", r, r == "Pressed next track in Spotify." and
              scripts[-1] == 'tell application "Spotify" to next track')
        r = media.media_key("volume down", 2)
        check("Mac: volume down 2 = -12%", r, r.startswith("Pressed") and "+ -12)" in scripts[-1])
        media._osascript = lambda s: (True, "false")  # nothing is running
        r = media.media_key("play")
        check("Mac: nothing open gives a helpful error", r, r.startswith("Error") and "Open Spotify" in r)
    finally:
        media.IS_MAC, media._osascript = real_mac, real_osa
    real_mac_b = basic.IS_MAC
    basic.IS_MAC = True
    try:
        r = basic._foreground_exe()  # osascript doesn't exist here: must return "" and not crash
        check("Mac terminal check never crashes without osascript", repr(r), isinstance(r, str))
    finally:
        basic.IS_MAC = real_mac_b
    check("Mac script files count as programs", "x.terminal, y.scpt",
          basic._is_program(Path("x.terminal")) and basic._is_program(Path("y.scpt")))
    check("Mac Terminal counts as a terminal", "terminal, iterm2",
          "terminal" in basic.TERMINALS and "iterm2" in basic.TERMINALS)

    print("\nclick_at maths (nothing is clicked here; the real click is under --click)")
    real_screen = pointer._main_screen
    pointer._main_screen = lambda: (0, 0, 2880, 1800)  # pretend: a 2880x1800 laptop screen
    try:
        check("2880x1800 screen -> the AI sees 1280x800", str(pointer.picture_size(2880, 1800)),
              pointer.picture_size(2880, 1800) == (1280, 800))
        check("(100, 100) in the picture -> (225, 225) on screen", str(pointer.to_screen(100, 100)),
              pointer.to_screen(100, 100) == (225, 225))
        r = pointer.click_at(1500, 10)
        check("a point outside the picture gives an error", r, r.startswith("Error") and "1280 x 800" in r)
        r = pointer.click_at("left", 5)
        check("x that isn't a number gives an error", r, r.startswith("Error"))
    finally:
        pointer._main_screen = real_screen
    pointer._main_screen = lambda: (0, 0, 1024, 768)  # a small screen isn't scaled at all
    try:
        check("1024x768 screen is not scaled", str(pointer.to_screen(500, 400)), pointer.to_screen(500, 400) == (500, 400))
    finally:
        pointer._main_screen = real_screen

    print("\nlock_pc / sleep_pc (phone always answers No, so nothing happens)")
    phone = FakeSession(answer=False)
    actions.current_session = phone
    r = power.lock_pc()
    check("lock_pc asks first; 'No' cancels", r, r.startswith("Cancelled") and len(phone.sent) == 0)
    r = power.sleep_pc()
    check("sleep_pc asks first; 'No' cancels", r, r.startswith("Cancelled") and len(phone.sent) == 0)
    actions.current_session = None
    r = power.lock_pc()
    check("lock_pc without a phone refuses", r, r.startswith("Cancelled"))
    r = power.sleep_pc()
    check("sleep_pc without a phone refuses", r, r.startswith("Cancelled"))


def gui_tests(tmp: Path) -> None:
    print("\n--gui: things you should SEE on the screen")
    note = tmp / "HomeCall test note.txt"
    note.write_text("If you can read this, open_file works.", encoding="utf-8")
    saved_roots = basic.ALLOWED_ROOTS
    basic.ALLOWED_ROOTS = [tmp]
    try:
        r = basic.open_file(str(note))
        check("open_file opens the test note", r, r.startswith("Opened"))
    finally:
        basic.ALLOWED_ROOTS = saved_roots
    time.sleep(1.5)
    r = basic.open_app("Calculator")
    check("open_app opens Calculator", r, r.startswith("Opened"))
    time.sleep(1.5)
    r = media.media_key("volume up")
    check("media_key volume up (watch for the volume slider)", r, r.startswith("Pressed"))
    time.sleep(0.5)
    r = media.media_key("volume down")
    check("media_key volume down (back where it was)", r, r.startswith("Pressed"))


TYPED = "Labas iš HomeCall! ąčęėįšųūž ĄČĘĖĮŠŲŪŽ ABC xyz 123"


def keys_tests() -> None:
    """Type into a plain window this script makes itself, then check every letter.

    Not Notepad: Windows 11 Notepad has autocorrect, which silently changes
    what was typed (we saw 'HomeCall' become 'homeCall').
    """
    print("\n--keys: typing into the test's OWN window (hands off the keyboard and mouse for ~5 seconds)")
    try:
        import tkinter as tk
    except ImportError:
        print("      skipped: tkinter is not installed with this Python")
        return
    results: list[tuple[str, str, bool]] = []
    root = tk.Tk()
    root.title("HomeCall typing test")
    root.geometry("780x140+200+200")
    box = tk.Text(root, font=("Segoe UI", 14))
    box.pack(fill="both", expand=True)
    root.attributes("-topmost", True)
    root.lift()
    root.focus_force()
    box.focus_set()

    def go() -> None:
        if root.focus_get() is not box:
            results.append(("the test window is in front", "another window took the focus; typed NOTHING", False))
            root.destroy()
            return
        r = basic.type_text(TYPED)
        results.append(("type_text reports success", r, r.startswith("Typed")))
        r = basic.press_keys("shift+home")
        results.append(("press_keys reports success", r, r.startswith("Pressed")))
        root.after(600, done)

    def done() -> None:
        got = box.get("1.0", "end").rstrip("\n")
        results.append(("every letter arrived exactly right", f"typed: {TYPED!r}\n   got: {got!r}", got == TYPED))
        selected = bool(box.tag_ranges("sel"))
        results.append(("shift+home really selected the line", "selected" if selected else "nothing selected", selected))
        root.destroy()

    root.after(1200, go)
    root.mainloop()
    for label, result, ok in results:
        check(label, result, ok)


def click_tests() -> None:
    """Open a window of our own with a button, click it through click_at, check it was pressed."""
    print("\n--click: clicking a button in the test's OWN window (hands off the mouse for ~5 seconds)")
    try:
        import tkinter as tk
    except ImportError:
        print("      skipped: tkinter is not installed with this Python")
        return
    import pyautogui  # noqa: F401  (makes this program use real pixels, like the app does)
    pressed: list[str] = []
    results: list[tuple[str, str, bool]] = []
    root = tk.Tk()
    root.title("HomeCall click test")
    root.geometry("420x220+300+300")
    root.attributes("-topmost", True)
    button = tk.Button(root, text="HomeCall click test: click me", font=("Segoe UI", 14),
                       command=lambda: pressed.append("yes"))
    button.pack(expand=True, fill="both", padx=60, pady=60)

    def go() -> None:
        root.lift()
        root.update()
        left, top, w, h = pointer._main_screen()
        pic_w, pic_h = pointer.picture_size(w, h)
        # the middle of the button, as it would appear in the AI's screenshot
        bx = button.winfo_rootx() + button.winfo_width() // 2
        by = button.winfo_rooty() + button.winfo_height() // 2
        x, y = round((bx - left) * pic_w / w), round((by - top) * pic_h / h)
        r = pointer.click_at(x, y)
        results.append(("click_at reports success", r, r.startswith("Clicked")))
        root.after(500, done)

    def done() -> None:
        results.append(("the button really got clicked", "pressed" if pressed else "NOT pressed", bool(pressed)))
        root.destroy()

    root.after(1200, go)
    root.mainloop()
    for label, result, ok in results:
        check(label, result, ok)


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="HomeCallTest_"))
    print(f"HomeCall tools test on {platform.system()} {platform.release()} (temporary folder: {tmp})")
    try:
        safe_tests(tmp)
        if "--gui" in sys.argv:
            gui_tests(tmp)
        if "--keys" in sys.argv:
            keys_tests()
        if "--click" in sys.argv:
            click_tests()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # only the temporary folder made above
    failed = [label for ok, label in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed.")
    for label in failed:
        print(f"  FAILED: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
