"""Try every Hands tool on this PC and print what happens.  (Owner: Hands)

    python -m pc.actions.try_tools          safe tests: a temporary folder only, your real files are never touched
    python -m pc.actions.try_tools --gui    also opens a test file and Calculator on the screen
    python -m pc.actions.try_tools --keys   also types into a small window of its own and checks every letter
                                            (hands off the keyboard and mouse for ~5 seconds!)
    python -m pc.actions.try_tools --click  also clicks a button in a small window of its own and checks it was pressed
    python -m pc.actions.try_tools --icon   also double-clicks a harmless test program in its own Explorer window
                                            (Windows) and checks it asked first and did NOT run
    python -m pc.actions.try_tools --more   also scrolls its own window, opens+closes a fresh Calculator,
                                            and opens example.com in the browser (then closes that tab)
    python -m pc.actions.try_tools --round2 also click_text / switch_to_app in a test window of its own, sends a
                                            test file to the Recycle Bin, and changes the volume while muted
                                            (then puts it back exactly)
    python -m pc.actions.try_tools --files  also a real clipboard round trip (what you had copied is put back)

Nothing real is deleted: the only thing removed at the end is the temporary
test folder this script made itself, and its own copies in pc/outbox.
"""
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
import types
import zipfile
from pathlib import Path

import pc.actions as actions
from pc.actions import basic, clipboard, extras, media, pointer, power, search

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


def make_pptx(path: Path, slides: list[list[str]]) -> None:
    """A tiny but real PowerPoint file: one slide per list, one paragraph per string."""
    a = "http://schemas.openxmlformats.org/drawingml/2006/main"
    p = "http://schemas.openxmlformats.org/presentationml/2006/main"
    with zipfile.ZipFile(path, "w") as z:
        for i, lines in enumerate(slides, 1):
            paras = "".join(f"<a:p><a:r><a:t>{line}</a:t></a:r></a:p>" for line in lines)
            z.writestr(f"ppt/slides/slide{i}.xml",
                       f'<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:a="{a}" xmlns:p="{p}"><p:cSld><p:spTree>'
                       f"<p:sp><p:txBody>{paras}</p:txBody></p:sp></p:spTree></p:cSld></p:sld>")


def make_xlsx(path: Path, rows: list[list[str]]) -> None:
    """A tiny but real Excel file: text cells go through the shared-strings table, numbers stay numbers."""
    s = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    shared: list[str] = []
    xml_rows = []
    for r, row in enumerate(rows, 1):
        cells = []
        for value in row:
            if value.replace(".", "", 1).isdigit():
                cells.append(f"<c><v>{value}</v></c>")
            else:
                shared.append(value)
                cells.append(f'<c t="s"><v>{len(shared) - 1}</v></c>')
        xml_rows.append(f'<row r="{r}">{"".join(cells)}</row>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/sharedStrings.xml", f'<?xml version="1.0" encoding="UTF-8"?><sst xmlns="{s}">'
                   + "".join(f"<si><t>{t}</t></si>" for t in shared) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="{s}">'
                   f"<sheetData>{''.join(xml_rows)}</sheetData></worksheet>")


def make_pdf(path: Path, line: str) -> None:
    """A tiny but real one-page PDF with one line of (ASCII) text."""
    stream = f"BT /F1 12 Tf 10 50 Td ({line}) Tj ET".encode("latin-1")
    objects = [b"<</Type/Catalog/Pages 2 0 R>>", b"<</Type/Pages/Kids[3 0 R]/Count 1>>",
               b"<</Type/Page/Parent 2 0 R/MediaBox[0 0 400 100]/Contents 4 0 R/Resources<</Font<</F1 5 0 R>>>>>>",
               b"<</Length %d>>stream\n" % len(stream) + stream + b"\nendstream",
               b"<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>"]
    out, offsets = b"%PDF-1.4\n", []
    for i, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj" % i + body + b"endobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer<</Size %d/Root 1 0 R>>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, xref)
    path.write_bytes(out)


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

        print("\nsend_folder_to_phone (temporary folder only)")
        proj = tmp / "Projects"
        (proj / "deep" / "notes2.txt").write_text("more notes", encoding="utf-8")
        (proj / ".secret").write_text("hidden", encoding="utf-8")
        phone = FakeSession(answer=False)
        actions.current_session = phone
        r = extras.send_folder_to_phone(str(proj))
        cards = [e for e in phone.sent if e.get("type") == "file"]
        token = cards[0]["url"].rsplit("/", 1)[-1] if cards else ""
        zips = list(basic.OUTBOX.glob(f"{token}__*")) if token else []
        names = zipfile.ZipFile(zips[0]).namelist() if zips else []
        check("zips the folder and sends one 'file' card named Projects.zip", r,
              bool(cards) and cards[0]["name"] == "Projects.zip" and len(zips) == 1)
        check("the zip has the files (also 2 folders deep) but not hidden ones", ", ".join(names),
              any(n.endswith("plan.txt") for n in names) and any(n.endswith("notes2.txt") for n in names)
              and not any(".secret" in n for n in names))
        for z in zips:
            z.unlink()  # our own test copy
        r = extras.send_folder_to_phone(str(tmp))
        check("refuses a whole Desktop/Documents-level folder", r, r.startswith("Error"))
        (tmp / "Empty").mkdir()
        r = extras.send_folder_to_phone(str(tmp / "Empty"))
        check("an empty folder gives an error", r, r.startswith("Error") and "empty" in r)
        r = extras.send_folder_to_phone("C:\\Windows" if sys.platform == "win32" else "/etc")
        check("refuses a folder outside the allowed ones", r, r.startswith("Error"))
        actions.current_session = None

        print("\nPowerPoint, Excel and PDF")
        docs = tmp / "Docs"
        docs.mkdir()
        make_pptx(docs / "Pitch.pptx", [["HomeCall", "Call your PC"], ["Demo", "Find my CV"]])
        make_xlsx(docs / "Budget.xlsx", [["Item", "Price"], ["Pica", "12.5"], ["Sutartis su ąžuolu", "3"]])
        make_pdf(docs / "Cabin.pdf", "The cabin wifi password is on the fridge")
        r = basic.read_file_text(str(docs / "Pitch.pptx"))
        check("reads a PowerPoint, slide by slide", r, "Slide 1: HomeCall / Call your PC" in r and "Slide 2: Demo / Find my CV" in r)
        r = basic.read_file_text(str(docs / "Budget.xlsx"))
        check("reads an Excel sheet, row by row", r, "Item\tPrice" in r and "Pica\t12.5" in r and "ąžuolu" in r)
        r = basic.read_file_text(str(docs / "Cabin.pdf"))
        check("reads a PDF", r, "cabin wifi password" in r)

        print("\nfind_recent_files")
        now = time.time()
        for name, age_days in (("today notes.txt", 0), ("last week report.txt", 6), ("old essay.txt", 40)):
            (docs / name).write_text(name, encoding="utf-8")
            os.utime(docs / name, (now - age_days * 86400 - 60, now - age_days * 86400 - 60))
        r = search.find_recent_files(7)
        check("lists files from the last 7 days, newest first", r,
              r.index("today notes.txt") < r.index("last week report.txt") and "old essay.txt" not in r)
        r = search.find_recent_files(60, "essay")
        check("name filter + more days finds the old essay", r, "old essay.txt" in r and "today notes" not in r)
        r = search.find_recent_files(0)
        check("days=0 gives an error", r, r.startswith("Error"))

        print("\nsearch_in_files")
        (docs / "Lease.txt").write_text("Nuomos sutartį pasirašėme gegužę.", encoding="utf-8")
        for words, expect in (("cabin wifi", "Cabin.pdf"), ("find my cv", "Pitch.pptx"), ("pica", "Budget.xlsx"),
                              ("sutarti", "Lease.txt"), ("Python and ąžuolai", "Cover letter.docx")):
            r = search.search_in_files(words)
            check(f"finds '{words}' inside {expect}", r.split("\n", 2)[0] + " | " + (r.split("\n")[2].strip() if r.count("\n") > 1 else ""),
                  expect in r)
        r = search.search_in_files("zebra crossing")
        check("says when no document mentions it", r, r.startswith("No document"))
        r = search.search_in_files("ab")
        check("fewer than 3 letters gives an error", r, r.startswith("Error"))

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
        r = pointer.click_at(1500, 10, "OK button")
        check("a point outside the picture gives an error", r, r.startswith("Error") and "1280 x 800" in r)
        r = pointer.click_at("left", 5, "OK button")
        check("x that isn't a number gives an error", r, r.startswith("Error"))
        r = pointer.click_at(10, 10, "  ")
        check("click_at without saying what gives an error", r, r.startswith("Error"))
        for risky in ("Send button", "Move to Bin", "Buy now", "Allow", "Delete"):
            check(f"'{risky}' counts as risky", risky, pointer.is_risky(risky))
        for safe in ("Play button", "OK button", "Brunch menu", "Design tab", "Search box"):
            check(f"'{safe}' is not risky", safe, not pointer.is_risky(safe))
        lt_risky = ["Siųsti", "Ištrinti", "Pašalinti", "Pirkti", "Mokėti", "Leisti", "Patvirtinti", "Įdiegti",
                    "Perkelti į šiukšlinę", "Atsijungti", "Siusti"]
        missing = [w for w in lt_risky if not pointer.is_risky(w)]
        check("Lithuanian risky buttons ask (also typed without accents)", ", ".join(missing) or "all risky", not missing)
        lt_safe = ["Groti", "Ieškoti", "Gerai", "Atšaukti", "Atidaryti", "Uždaryti", "Kitas"]
        wrong = [w for w in lt_safe if pointer.is_risky(w)]
        check("harmless Lithuanian buttons don't ask (Groti, Ieškoti, Gerai...)", ", ".join(wrong) or "none ask", not wrong)
        en_more = ["Replace", "Overwrite", "Share", "Reply", "Forward", "Upload", "Approve", "Grant", "Open Anyway"]
        missing = [w for w in en_more if not pointer.is_risky(w)]
        check("more English risky words ask", ", ".join(missing) or "all risky", not missing)
        for prog in ("setup.exe icon", "Evil.app", "run-me.command", "Zoom installer", "diegimo programa"):
            check(f"double-clicking '{prog}' counts as starting a program", prog, pointer.looks_like_program(prog))
        for doc in ("notes.md", "CV_Alex_Demo.pdf", "OK button", "Projects folder"):
            check(f"double-clicking '{doc}' is not a program", doc, not pointer.looks_like_program(doc))
        actions.current_session = FakeSession(answer=False)
        r = pointer.click_at(10, 10, "setup.exe icon", double=True)
        check("double-click on a program asks first; 'No' cancels", r, r.startswith("Cancelled"))
        actions.current_session = None

        print("\nclick_at: the real file behind a Desktop icon (faked screen, nothing is clicked)")
        desk = tmp / "FakeDesktop"
        desk.mkdir()
        (desk / "Evil.exe").write_bytes(b"MZ fake")
        (desk / "notes.md").write_text("notes", encoding="utf-8")
        (desk / "Projects").mkdir()
        real_under, real_folders = pointer._thing_under, pointer._desktop_folders
        pointer._desktop_folders = lambda: [desk]
        clicks: list = []
        real_gui = sys.modules.get("pyautogui")
        sys.modules["pyautogui"] = types.SimpleNamespace(click=lambda *a, **k: clicks.append(a))
        try:
            def icon(name: str):
                return lambda x, y: {"name": name, "control": "ControlType.ListItem", "process": "explorer"}
            pointer._thing_under = icon("Evil")
            check("'Evil' icon is found as Evil.exe, a program", pointer._icon_worry(1, 1), "Evil.exe" in pointer._icon_worry(1, 1))
            actions.current_session = FakeSession(answer=False)
            r = pointer.click_at(10, 10, "Evil icon", double=True)
            check("double-click on the 'Evil' icon asks; 'No' = no click", r, r.startswith("Cancelled") and not clicks)
            pointer._thing_under = icon("notes")
            check("'notes' icon (notes.md) needs no question", repr(pointer._icon_worry(1, 1)), pointer._icon_worry(1, 1) == "")
            pointer._thing_under = icon("Projects")
            check("'Projects' folder icon needs no question", repr(pointer._icon_worry(1, 1)), pointer._icon_worry(1, 1) == "")
            pointer._thing_under = icon("Mystery thing")
            check("an icon we can't find asks (to be safe)", pointer._icon_worry(1, 1), "can't tell" in pointer._icon_worry(1, 1))
            pointer._thing_under = lambda x, y: {"name": "Play", "control": "ControlType.Button", "process": "spotify"}
            check("double-clicks inside apps are left alone", repr(pointer._icon_worry(1, 1)), pointer._icon_worry(1, 1) == "")
        finally:
            pointer._thing_under, pointer._desktop_folders = real_under, real_folders
            actions.current_session = None
            if real_gui is not None:
                sys.modules["pyautogui"] = real_gui
            else:
                sys.modules.pop("pyautogui", None)
        actions.current_session = FakeSession(answer=False)
        r = pointer.click_at(10, 10, "Send button")
        check("a risky click asks first; 'No' cancels (nothing clicked)", r, r.startswith("Cancelled"))
        actions.current_session = None
        r = pointer.click_at(10, 10, "Delete")
        check("a risky click without a phone is refused", r, r.startswith("Cancelled"))
    finally:
        pointer._main_screen = real_screen
    pointer._main_screen = lambda: (0, 0, 1024, 768)  # a small screen isn't scaled at all
    try:
        check("1024x768 screen is not scaled", str(pointer.to_screen(500, 400)), pointer.to_screen(500, 400) == (500, 400))
    finally:
        pointer._main_screen = real_screen

    print("\nopen_url (the browser is faked, nothing opens)")
    for good, expect in (("youtube.com", "https://youtube.com"),
                         ("https://www.youtube.com/results?search_query=lofi", "https://www.youtube.com/results?search_query=lofi")):
        check(f"'{good}' is a website I can open", str(extras._clean_url(good)), extras._clean_url(good) == expect)
    for bad in ("file:///C:/Windows/System32", "javascript:alert(1)", "ms-settings:privacy", "https://user:pw@evil.com",
                "hello world", "notes", "C:\\Users\\me\\Downloads\\evil.exe", ""):
        check(f"refuses '{bad}'", str(extras._clean_url(bad)), extras._clean_url(bad) is None)
    check("YouTube search link", extras.youtube_search_url("lo-fi beats"),
          extras.youtube_search_url("lo-fi beats") == "https://www.youtube.com/results?search_query=lo-fi+beats")
    opened: list[str] = []
    real_open = extras.webbrowser.open
    extras.webbrowser.open = lambda url, new=0: opened.append(url) or True
    try:
        r = extras.open_url("youtube.com")
        check("open_url opens it in the browser", r, r.startswith("Opened youtube.com") and opened == ["https://youtube.com"])
        r = extras.open_url("file:///C:/Windows")
        check("open_url refuses a file: link and opens nothing", r, r.startswith("Error") and len(opened) == 1)
    finally:
        extras.webbrowser.open = real_open

    print("\nclose_app (windows are faked, nothing is closed)")
    fake_windows = [
        {"hwnd": 1, "title": "Calculator", "exe": "applicationframehost"},
        {"hwnd": 2, "title": "Settings", "exe": "applicationframehost"},
        {"hwnd": 3, "title": "Gmail - Google Chrome", "exe": "chrome"},
        {"hwnd": 4, "title": "YouTube - Google Chrome", "exe": "chrome"},
        {"hwnd": 5, "title": "Downloads - File Explorer", "exe": "explorer"},
        {"hwnd": 6, "title": "HomeCall", "exe": "python"},
        {"hwnd": 7, "title": "Spotify Premium", "exe": "spotify"},
    ]
    for said, expect in (("Calculator", [1]), ("chrome", [3, 4]), ("Google Chrome", [3, 4]), ("Spotify", [7]),
                         ("File Explorer", []), ("python", []), ("Word", [])):
        got = [w["hwnd"] for w in extras.match_windows(said, fake_windows)]
        check(f"close_app('{said}') would close {expect or 'nothing'}", str(got), got == expect)
    if sys.platform == "win32":
        real_windows = extras._windows
        extras._windows = lambda: fake_windows
        try:
            actions.current_session = FakeSession(answer=False)
            r = extras.close_app("Spotify")
            check("close_app asks first; 'No' cancels", r, r.startswith("Cancelled"))
            actions.current_session = None
            r = extras.close_app("Spotify")
            check("close_app without a phone refuses", r, r.startswith("Cancelled"))
            r = extras.close_app("Word")
            check("an app that isn't open gives an error", r, r.startswith("Error"))
        finally:
            extras._windows = real_windows

    print("\nclipboard (no real reading here; the real round trip is under --files)")
    actions.current_session = FakeSession(answer=False)
    real_read = clipboard.read_clipboard_text
    clipboard.read_clipboard_text = lambda: "SHOULD NOT BE READ"
    try:
        r = clipboard.get_clipboard()
        check("get_clipboard asks first; 'No' = nothing read", r, r.startswith("Cancelled") and "SHOULD NOT" not in r)
        actions.current_session = None
        r = clipboard.get_clipboard()
        check("get_clipboard without a phone refuses", r, r.startswith("Cancelled"))
    finally:
        clipboard.read_clipboard_text = real_read
    for bad in ("", "x" * 10_001):
        r = clipboard.set_clipboard(bad)
        check(f"set_clipboard with {len(bad)} characters gives an error", r, r.startswith("Error"))

    print("\nswitch_to_app / set_volume (faked, nothing changes)")
    got = [w["hwnd"] for w in extras.match_windows("File Explorer", fake_windows, protected=extras.SYSTEM_WINDOWS)]
    check("switch_to_app may pick File Explorer (close_app may not)", str(got), got == [5])
    for bad in (-5, 101, "loud"):
        r = extras.set_volume(bad)
        check(f"set_volume({bad!r}) gives an error", r, r.startswith("Error"))

    print("\nclick_text (Windows answers are faked, nothing is clicked)")
    fake_hits = [{"name": "Delete everything", "control": "ControlType.Button", "x": 10, "y": 10, "enabled": True},
                 {"name": "Play", "control": "ControlType.Button", "x": 20, "y": 20, "enabled": True},
                 {"name": "Play next", "control": "ControlType.Button", "x": 30, "y": 30, "enabled": True},
                 {"name": "Išsaugoti", "control": "ControlType.Button", "x": 40, "y": 40, "enabled": False}]
    names = [h["name"] for h in pointer.rank_matches("play", fake_hits)]
    check("'play' ranks the exact 'Play' before 'Play next'", str(names), names == ["Play", "Play next"])
    names = [h["name"] for h in pointer.rank_matches("issaugoti", fake_hits)]
    check("matching ignores Lithuanian accents (issaugoti -> Išsaugoti)", str(names), names == ["Išsaugoti"])
    if sys.platform == "win32":
        clicked: list = []
        real_find, real_fg, real_gui = pointer.uia.find, pointer._foreground_window, sys.modules.get("pyautogui")
        pointer.uia.find = lambda hwnd, text: fake_hits
        pointer._foreground_window = lambda: 1
        sys.modules["pyautogui"] = types.SimpleNamespace(click=lambda *a, **k: clicked.append(a))
        try:
            actions.current_session = FakeSession(answer=False)
            r = pointer.click_text("Play")
            check("click_text clicks the button called 'Play'", r, r.startswith("Clicked 'Play'") and clicked == [(20, 20)])
            r = pointer.click_text("Delete")
            check("click_text asks before 'Delete everything'; 'No' = no click", r, r.startswith("Cancelled") and len(clicked) == 1)
            r = pointer.click_text("Išsaugoti")
            check("a greyed-out button gives an error", r, r.startswith("Error") and "greyed out" in r)
            r = pointer.click_text("Play", which=5)
            check("which=5 with 2 matches gives an error", r, r.startswith("Error"))
            pointer.uia.find = lambda hwnd, text: []
            r = pointer.click_text("Nothing here")
            check("no such button gives an error that suggests click_at", r, r.startswith("Error") and "click_at" in r)
            r = pointer._guard(1, 1, "OK button", False, {"name": "Delete account"})
            check("click_at asks when Windows says the button is really 'Delete account'", r, r.startswith("Cancelled"))
        finally:
            pointer.uia.find, pointer._foreground_window = real_find, real_fg
            actions.current_session = None
            if real_gui is not None:
                sys.modules["pyautogui"] = real_gui
            else:
                sys.modules.pop("pyautogui", None)

    print("\nscroll (the mouse wheel is faked, nothing scrolls)")
    wheel: list = []
    real_gui = sys.modules.get("pyautogui")
    sys.modules["pyautogui"] = types.SimpleNamespace(scroll=lambda n: wheel.append(("v", n)),
                                                     hscroll=lambda n: wheel.append(("h", n)),
                                                     moveTo=lambda *a: wheel.append(("move",) + a))
    try:
        notch = extras.WHEEL_NOTCH if sys.platform == "win32" else 1
        r = extras.scroll("down")
        check("scroll down 5 = mouse wheel backwards", r, r.startswith("Scrolled") and wheel[-1] == ("v", -5 * notch))
        r = extras.scroll("right", 2)
        check("scroll right = sideways wheel", r, r.startswith("Scrolled") and wheel[-1] == ("h", 2 * notch))
        for bad_args in (("sideways",), ("down", 0), ("down", 99), ("down", 5, 5000, 10)):
            r = extras.scroll(*bad_args)
            check(f"scroll{bad_args} gives an error", r, r.startswith("Error"))
    finally:
        if real_gui is not None:
            sys.modules["pyautogui"] = real_gui
        else:
            sys.modules.pop("pyautogui", None)

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
    root.geometry("460x300+300+300")
    root.attributes("-topmost", True)
    play = tk.Button(root, text="Play (test)", font=("Segoe UI", 14), command=lambda: pressed.append("play"))
    play.pack(expand=True, fill="both", padx=60, pady=(40, 10))
    delete = tk.Button(root, text="Delete (test)", font=("Segoe UI", 14), command=lambda: pressed.append("delete"))
    delete.pack(expand=True, fill="both", padx=60, pady=(10, 40))

    def in_picture(widget) -> tuple[int, int]:
        """The middle of a widget, as it would appear in the AI's screenshot."""
        left, top, w, h = pointer._main_screen()
        pic_w, pic_h = pointer.picture_size(w, h)
        bx = widget.winfo_rootx() + widget.winfo_width() // 2
        by = widget.winfo_rooty() + widget.winfo_height() // 2
        return round((bx - left) * pic_w / w), round((by - top) * pic_h / h)

    def go() -> None:
        root.lift()
        root.update()
        actions.current_session = FakeSession(answer=False)  # the "phone" taps No
        try:
            r = pointer.click_at(*in_picture(play), "Play button")
            results.append(("click_at clicks a normal button without asking", r, r.startswith("Clicked")))
            r = pointer.click_at(*in_picture(delete), "Delete button")
            results.append(("click_at asks before 'Delete'; 'No' cancels", r, r.startswith("Cancelled")))
            r = pointer.click_at(*in_picture(delete), "Ištrinti")
            results.append(("click_at asks before Lithuanian 'Ištrinti'; 'No' cancels", r, r.startswith("Cancelled")))
            r = pointer.click_at(*in_picture(delete), "setup.exe", double=True)
            results.append(("a double-click on 'setup.exe' asks; 'No' cancels", r, r.startswith("Cancelled")))
        finally:
            actions.current_session = None
        root.after(500, done)

    def done() -> None:
        results.append(("Play really got clicked", ", ".join(pressed) or "nothing", "play" in pressed))
        results.append(("Delete was NOT clicked", ", ".join(pressed) or "nothing", "delete" not in pressed))
        root.destroy()

    root.after(1200, go)
    root.mainloop()
    for label, result, ok in results:
        check(label, result, ok)


_FIND_ITEM = r"""
Add-Type -AssemblyName UIAutomationClient, UIAutomationTypes, WindowsBase
$A = [System.Windows.Automation.AutomationElement]
$S = [System.Windows.Automation.TreeScope]
$win = $A::RootElement.FindAll($S::Children, [System.Windows.Automation.Condition]::TrueCondition) |
       Where-Object { $_.Current.Name -like '*%s*' } | Select-Object -First 1
if (-not $win) { '{}'; exit }
$item = $win.FindFirst($S::Descendants, (New-Object System.Windows.Automation.PropertyCondition($A::NameProperty, '%s')))
if (-not $item) { '{}'; exit }
$r = $item.Current.BoundingRectangle
[pscustomobject]@{ x = [int]($r.X + $r.Width / 2); y = [int]($r.Y + $r.Height / 2) } | ConvertTo-Json -Compress
"""
_CLOSE_WINDOW = r"""
(New-Object -ComObject Shell.Application).Windows() | Where-Object { $_.LocationURL -like '*%s*' } | ForEach-Object { $_.Quit() }
"""


def _ps(script: str) -> str:
    out = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                         capture_output=True, text=True, timeout=20)
    return out.stdout.strip()


def icon_tests() -> None:
    """Double-click a program icon in a fresh Explorer window of our own; with 'No' it must not run."""
    print("\n--icon: double-clicking a test program in the test's OWN Explorer window (hands off the mouse ~10 s)")
    if sys.platform != "win32":
        print("      skipped: this test is written for Windows")
        return
    folder = Path(tempfile.mkdtemp(prefix="HomeCallIconTest_"))
    prog = folder / "HomeCall test program.bat"
    marker = folder / "ran.txt"
    prog.write_text('@echo ran> "%~dp0ran.txt"\r\n', encoding="ascii")  # its only effect: write ran.txt here
    try:
        subprocess.Popen(["explorer.exe", str(folder)])
        found = {}
        for _ in range(20):  # wait up to 10 s for the window and the icon
            time.sleep(0.5)
            found = json.loads(_ps(_FIND_ITEM % (folder.name, prog.stem)) or "{}")
            if found:
                break
        if not found:
            check("the test icon shows up in its Explorer window", "not found; NOT clicking anything", False)
            return
        under = pointer._thing_under(found["x"], found["y"])
        if under.get("process", "").lower() != "explorer" or under.get("name") != prog.stem:
            check("the test icon is the thing under the mouse", f"under it: {under}; NOT clicking anything", False)
            return
        check("Windows sees the icon as 'HomeCall test program' (no .bat shown)", str(under), True)
        left, top, w, h = pointer._main_screen()
        pic_w, pic_h = pointer.picture_size(w, h)
        x, y = round((found["x"] - left) * pic_w / w), round((found["y"] - top) * pic_h / h)
        actions.current_session = FakeSession(answer=False)  # the "phone" taps No
        try:
            r = pointer.click_at(x, y, "test icon", double=True)  # a harmless-sounding description on purpose
        finally:
            actions.current_session = None
        check("double-click on the test program asks; 'No' cancels", r, r.startswith("Cancelled"))
        time.sleep(1.5)
        check("the test program did NOT run", "ran.txt exists!" if marker.exists() else "no ran.txt", not marker.exists())
    finally:
        _ps(_CLOSE_WINDOW % folder.name)
        time.sleep(0.5)
        shutil.rmtree(folder, ignore_errors=True)


def more_tests() -> None:
    """Real scroll / close_app / open_url on this PC, only on things the test opens itself."""
    print("\n--more: scroll, close_app and open_url for real (hands off the mouse ~20 seconds)")
    if sys.platform != "win32":
        print("      skipped: this test is written for Windows")
        return
    import tkinter as tk
    import pyautogui  # noqa: F401  (real pixels, like the app)
    results: list[tuple[str, str, bool]] = []

    # 1. scroll: our own window with a long text
    root = tk.Tk()
    root.title("HomeCall scroll test")
    root.geometry("600x400+300+300")
    root.attributes("-topmost", True)
    text = tk.Text(root, font=("Segoe UI", 12))
    text.insert("1.0", "\n".join(f"line {i}" for i in range(1, 301)))
    text.pack(expand=True, fill="both")

    def go() -> None:
        root.lift()
        root.update()
        left, top, w, h = pointer._main_screen()
        pic_w, pic_h = pointer.picture_size(w, h)
        cx = text.winfo_rootx() + text.winfo_width() // 2
        cy = text.winfo_rooty() + text.winfo_height() // 2
        x, y = round((cx - left) * pic_w / w), round((cy - top) * pic_h / h)
        r = extras.scroll("down", 5, x, y)
        root.after(400, lambda: after_down(r, x, y))

    def after_down(r: str, x: int, y: int) -> None:
        moved = text.yview()[0]
        results.append(("scroll down really moved the text", f"{r} (top now at {moved:.0%})", moved > 0))
        extras.scroll("up", 30, x, y)
        root.after(400, after_up)

    def after_up() -> None:
        results.append(("scroll up went back to the top", f"top at {text.yview()[0]:.0%}", text.yview()[0] == 0))
        root.destroy()

    root.after(1000, go)
    root.mainloop()
    for label, result, ok in results:
        check(label, result, ok)

    # 2. close_app: a fresh Calculator, never one you already had open
    def calculators() -> list[dict]:
        return [w for w in extras._windows() if w["title"] in ("Calculator", "Skaičiuotuvas")]
    if calculators():
        print("      close_app real test skipped: a Calculator is already open, and I don't close yours")
    else:
        basic.open_app("Calculator")
        for _ in range(20):
            time.sleep(0.5)
            if calculators():
                break
        if not calculators():
            check("Calculator opened for the close_app test", "it didn't open", False)
        else:
            actions.current_session = FakeSession(answer=True)  # the "phone" taps Yes
            try:
                r = extras.close_app(calculators()[0]["title"])
            finally:
                actions.current_session = None
            check("close_app closes the test Calculator after a Yes", r, r.startswith("Closed") and not calculators())

    # 3. open_url: example.com, then close only that tab
    r = extras.open_url("https://example.com")
    seen = False
    for _ in range(20):
        time.sleep(0.5)
        if any(w["title"].startswith("Example Domain") for w in extras._windows()):
            seen = True
            break
    check("open_url opens example.com in the browser", r, r.startswith("Opened") and seen)
    if seen and basic._foreground_exe() in ("chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe"):
        import ctypes
        buf = ctypes.create_unicode_buffer(512)
        ctypes.windll.user32.GetWindowTextW(ctypes.windll.user32.GetForegroundWindow(), buf, 512)
        if buf.value.startswith("Example Domain"):
            basic.press_keys("ctrl+w")  # close only the example.com tab
            print("      (closed the example.com tab again)")


_TEST_FORM = r"""
param([string]$log)
Add-Type -AssemblyName System.Windows.Forms
$f = New-Object Windows.Forms.Form
$f.Text = 'HomeCall UIA test'; $f.Width = 760; $f.Height = 360; $f.StartPosition = 'Manual'; $f.Left = 400; $f.Top = 300
$play = New-Object Windows.Forms.Button; $play.Text = 'Play test'; $play.Left = 40; $play.Top = 60; $play.Width = 300; $play.Height = 140
$play.Add_Click({ Add-Content -Path $log -Value 'play' })
$del = New-Object Windows.Forms.Button; $del.Text = 'Delete test'; $del.Left = 400; $del.Top = 60; $del.Width = 300; $del.Height = 140
$del.Add_Click({ Add-Content -Path $log -Value 'delete' })
$f.Controls.Add($play); $f.Controls.Add($del)
$t = New-Object Windows.Forms.Timer; $t.Interval = 120000; $t.Add_Tick({ $f.Close() }); $t.Start()
[void]$f.ShowDialog()
"""


def round2_tests() -> None:
    """Real click_text, real-name check, switch_to_app, Recycle Bin, volume and speed, on things the test makes."""
    print("\n--round2: click_text, switch_to_app, Recycle Bin, volume (hands off the mouse ~30 seconds)")
    if sys.platform != "win32":
        print("      skipped: this test is written for Windows")
        return
    import ctypes
    import pyautogui  # noqa: F401  (real pixels, like the app)
    from pc.actions import uia
    user32 = ctypes.windll.user32
    work = Path(tempfile.mkdtemp(prefix="HomeCallRound2_"))
    log = work / "clicks.txt"
    form_ps1 = work / "form.ps1"
    form_ps1.write_text(_TEST_FORM, encoding="utf-8")

    # speed of the background Windows helper
    t0 = time.time()
    uia.at(10, 10)
    first = time.time() - t0
    t0 = time.time()
    uia.at(10, 10)
    second = time.time() - t0
    check("asking Windows what's under the mouse is fast after the first time",
          f"first {first:.2f}s, then {second:.3f}s", second < 0.5)

    form = subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(form_ps1), str(log)])
    try:
        win = None
        for _ in range(30):
            time.sleep(0.5)
            win = next((w for w in extras._windows() if w["title"] == "HomeCall UIA test"), None)
            if win:
                break
        if not win:
            check("the test window opened", "it didn't; NOT clicking anything", False)
            return

        def clicks() -> list[str]:
            return log.read_text(encoding="utf-8").split() if log.exists() else []

        # switch_to_app: put another window of ours in front first
        import tkinter as tk
        cover = tk.Tk()
        cover.title("HomeCall cover window")
        cover.geometry("900x500+380+280")
        cover.update()
        cover.focus_force()
        cover.update()
        time.sleep(0.5)
        r = extras.switch_to_app("HomeCall UIA test")
        check("switch_to_app brings the test window to the front", r,
              r.startswith("Switched") and user32.GetForegroundWindow() == win["hwnd"])
        cover.destroy()
        time.sleep(0.5)
        if user32.GetForegroundWindow() != win["hwnd"]:
            extras.switch_to_app("HomeCall UIA test")

        actions.current_session = FakeSession(answer=False)  # the "phone" taps No
        try:
            r = pointer.click_text("Play test")
            time.sleep(0.6)
            check("click_text clicks 'Play test' by its name", r, r.startswith("Clicked") and clicks() == ["play"])
            r = pointer.click_text("Delete test")
            time.sleep(0.6)
            check("click_text asks before 'Delete test'; 'No' = not clicked", r,
                  r.startswith("Cancelled") and "delete" not in clicks())
            hits = uia.find(win["hwnd"], "Delete test")
            if hits:
                left, top, w, h = pointer._main_screen()
                pic_w, pic_h = pointer.picture_size(w, h)
                x, y = round((hits[0]["x"] - left) * pic_w / w), round((hits[0]["y"] - top) * pic_h / h)
                r = pointer.click_at(x, y, "OK button")  # the AI names it wrongly on purpose
                time.sleep(0.6)
                check("click_at on 'Delete test' called 'OK button' still asks; 'No' = not clicked", r,
                      r.startswith("Cancelled") and "delete" not in clicks())
            else:
                check("found the Delete test button", "not found", False)
        finally:
            actions.current_session = None
    finally:
        try:
            if win:
                user32.PostMessageW(win["hwnd"], 0x0010, 0, 0)  # close our test window
            form.wait(timeout=10)
        except Exception:  # noqa: BLE001
            form.kill()

    # Recycle Bin: our own test file
    victim = work / "HomeCall recycle test.txt"
    victim.write_text("A test file from HomeCall's try_tools. Safe to delete.", encoding="utf-8")
    saved_roots = basic.ALLOWED_ROOTS
    basic.ALLOWED_ROOTS = [work]
    actions.current_session = FakeSession(answer=True)  # the "phone" taps Yes
    try:
        r = basic.delete_file(str(victim))
    finally:
        basic.ALLOWED_ROOTS = saved_roots
        actions.current_session = None
    in_bin = _ps("(New-Object -ComObject Shell.Application).NameSpace(10).Items() | "
                 "Where-Object { $_.Name -like 'HomeCall recycle test*' } | Measure-Object | Select-Object -ExpandProperty Count")
    check("delete_file moves the file to the Recycle Bin (not gone for good)", f"{r}; in Recycle Bin: {in_bin}",
          r.startswith("Deleted") and not victim.exists() and in_bin not in ("", "0"))

    # Volume: change it while staying MUTED (so nothing is heard), then put it back exactly
    before = uia.volume_get()
    if before is None:
        check("can read the volume", "no answer", False)
    else:
        level, muted = before
        test_level = 0.3 if abs(level - 0.3) > 0.05 else 0.5
        uia.volume_set(test_level, mute=True)
        now = uia.volume_get()
        uia.volume_set(level, mute=muted)
        back = uia.volume_get()
        check("the volume can be set to an exact level", f"set {test_level:.0%}, read {now[0]:.0%}" if now else "no answer",
              bool(now) and abs(now[0] - test_level) < 0.02)
        check("the volume and mute are back as they were", f"was {level:.0%} muted={muted}, now {back}",
              bool(back) and abs(back[0] - level) < 0.02 and back[1] == muted)
    shutil.rmtree(work, ignore_errors=True)


def files_tests() -> None:
    """The real clipboard: put a test text on it, read it back, then put back what was there."""
    print("\n--files: the real clipboard (what you had copied is put back afterwards)")
    before = clipboard.read_clipboard_text()
    if before is None:
        print("      skipped: can't read the clipboard on this PC")
        return
    if before == "" and sys.platform == "win32":
        import ctypes
        if ctypes.windll.user32.CountClipboardFormats() > 0:
            print("      skipped: your clipboard holds a picture or files, and I won't overwrite those")
            return
    test_text = "HomeCall clipboard test: ąčęėįšųūž 123"
    try:
        r = clipboard.set_clipboard(test_text)
        check("set_clipboard puts text on the clipboard", r, r.startswith("Put"))
        actions.current_session = FakeSession(answer=True)  # the "phone" taps Yes
        try:
            r = clipboard.get_clipboard()
        finally:
            actions.current_session = None
        check("get_clipboard reads it back after a Yes (Lithuanian letters too)", r, test_text in r)
    finally:
        if before:
            clipboard.write_clipboard_text(before)
        elif sys.platform == "win32":
            import ctypes
            if ctypes.windll.user32.OpenClipboard(None):
                ctypes.windll.user32.EmptyClipboard()
                ctypes.windll.user32.CloseClipboard()
    check("what you had copied is back on the clipboard", "restored" if clipboard.read_clipboard_text() == before else "DIFFERENT",
          clipboard.read_clipboard_text() == before)


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
        if "--icon" in sys.argv:
            icon_tests()
        if "--more" in sys.argv:
            more_tests()
        if "--round2" in sys.argv:
            round2_tests()
        if "--files" in sys.argv:
            files_tests()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)  # only the temporary folder made above
    failed = [label for ok, label in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)} passed, {len(failed)} failed.")
    for label in failed:
        print(f"  FAILED: {label}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
