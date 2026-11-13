"""Tests for the Hands (pc/actions/basic.py).  Owner: Demo, tests & safety.

Run from the project root:   python -m pytest tests/ -v

Safety: every test runs inside a temporary fake home folder. The tools'
ALLOWED_ROOTS, HOME and OUTBOX are pointed there, apps are never really opened
and the keyboard is never really pressed. Your real files are never touched.
"""
import os
import sys
import types
from pathlib import Path

import pytest

import pc.actions as actions
from pc.actions import basic


# ------------------------------------------------------------------ helpers -----

class FakeSession:
    """Stands in for pc.session.Session: records what the tools send to the phone."""

    def __init__(self, answer: bool = True):
        self.answer = answer        # what the "user" taps on a Yes/No card
        self.emitted = []           # every message sent to the phone
        self.questions = []         # every Yes/No question asked

    def emit(self, msg: dict) -> None:
        self.emitted.append(msg)

    def status(self, text: str) -> None:
        self.emit({"type": "status", "text": text})

    def confirm(self, question: str, timeout: int = 60) -> bool:
        self.questions.append(question)
        return self.answer

    def of_type(self, kind: str) -> list:
        return [m for m in self.emitted if m.get("type") == kind]


@pytest.fixture
def home(tmp_path, monkeypatch):
    """A fake home folder with Desktop/Documents/Downloads/Pictures and a few files."""
    fake_home = tmp_path / "home"
    roots = [fake_home / n for n in ("Desktop", "Documents", "Downloads", "Pictures")]
    for r in roots:
        r.mkdir(parents=True)
    (fake_home / "Desktop" / "My_CV.pdf").write_bytes(b"%PDF-1.4 fake cv")
    (fake_home / "Desktop" / "old draft.txt").write_text("delete me")
    (fake_home / "Desktop" / ".hidden").write_text("secret")
    (fake_home / "Desktop" / "Projects").mkdir()
    (fake_home / "Documents" / "notes.md").write_text("# notes")
    # A file OUTSIDE the allowed folders: tools must never reach it.
    (fake_home / "private.txt").write_text("top secret")

    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setattr(basic, "HOME", fake_home)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", roots)
    monkeypatch.setattr(basic, "OUTBOX", outbox)
    return fake_home


@pytest.fixture
def session(monkeypatch):
    s = FakeSession(answer=True)
    monkeypatch.setattr(actions, "current_session", s)
    return s


@pytest.fixture
def launched(monkeypatch):
    """Record app/file launches instead of really opening anything."""
    calls = []

    class FakePopen:
        def __init__(self, *args, **kwargs):
            calls.append(args[0] if args else kwargs.get("args"))

    def fake_run(*args, **kwargs):
        calls.append(args[0] if args else kwargs.get("args"))
        return types.SimpleNamespace(returncode=0, stdout=b"" if not kwargs.get("text") else "", stderr="")

    monkeypatch.setattr(basic.subprocess, "Popen", FakePopen)
    monkeypatch.setattr(basic.subprocess, "run", fake_run)  # Hands' open_app on Mac uses run()
    monkeypatch.setattr(os, "startfile", lambda p: calls.append(p), raising=False)
    if hasattr(basic, "_windows_apps"):  # Hands' Windows Start-menu lookup
        monkeypatch.setattr(basic, "_windows_apps", lambda: {"Spotify": "SpotifyAB.Spotify!App"})
    return calls


@pytest.fixture
def keyboard(monkeypatch):
    """A fake pyautogui that records key presses instead of pressing them."""
    fake = types.SimpleNamespace(typed=[], hotkeys=[])
    fake.typewrite = lambda text, interval=0: fake.typed.append(text)
    fake.hotkey = lambda *keys: fake.hotkeys.append(keys)
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    return fake


# --------------------------------------------------------------- list_files -----

def test_list_files_shows_desktop(home):
    out = basic.list_files("Desktop")
    assert "My_CV.pdf" in out
    assert "old draft.txt" in out
    assert "[folder] Projects" in out


def test_list_files_hides_dotfiles(home):
    assert ".hidden" not in basic.list_files("Desktop")


def test_list_files_default_is_desktop(home):
    assert "My_CV.pdf" in basic.list_files()


def test_list_files_empty_folder(home):
    assert basic.list_files("Pictures") == "(empty)"


@pytest.mark.parametrize("folder", ["/", "/etc", "..", "Desktop/../..", "~"])
def test_list_files_refuses_outside_folders(home, folder):
    assert basic.list_files(folder).startswith("Error")


# ---------------------------------------------------------------- find_file -----

def test_find_file_finds_cv_case_insensitive(home):
    out = basic.find_file("cv")
    assert "My_CV.pdf" in out


def test_find_file_searches_all_roots(home):
    assert "notes.md" in basic.find_file("notes")


def test_find_file_no_match(home):
    assert basic.find_file("nothing-like-this").startswith("No file")


def test_find_file_never_returns_files_outside_roots(home):
    assert "private.txt" not in basic.find_file("private")


# ---------------------------------------------------------------- open_file -----

def test_open_file_opens_and_says_so(home, session, launched):
    out = basic.open_file(str(home / "Desktop" / "My_CV.pdf"))
    assert out == "Opened My_CV.pdf"
    assert len(launched) == 1
    assert any("My_CV.pdf" in m["text"] for m in session.of_type("status"))


def test_open_file_missing(home, session, launched):
    assert basic.open_file(str(home / "Desktop" / "nope.pdf")).startswith("Error")
    assert launched == []


def test_open_file_refuses_outside(home, session, launched):
    assert basic.open_file(str(home / "private.txt")).startswith("Error")
    assert launched == []


# ------------------------------------------------------- send_file_to_phone -----

def test_send_file_copies_to_outbox_and_emits_card(home, session):
    out = basic.send_file_to_phone(str(home / "Desktop" / "My_CV.pdf"))
    assert out == "Sent My_CV.pdf to the phone."

    cards = session.of_type("file")
    assert len(cards) == 1
    card = cards[0]
    assert card["name"] == "My_CV.pdf"
    assert card["url"].startswith("/files/")
    token = card["url"].removeprefix("/files/")
    assert len(token) >= 12  # long random token, not guessable

    copied = list(basic.OUTBOX.iterdir())
    assert [p.name for p in copied] == [f"{token}__My_CV.pdf"]
    assert copied[0].read_bytes() == b"%PDF-1.4 fake cv"
    # the original stays where it was
    assert (home / "Desktop" / "My_CV.pdf").exists()


def test_send_file_tokens_are_different_each_time(home, session):
    path = str(home / "Desktop" / "My_CV.pdf")
    basic.send_file_to_phone(path)
    basic.send_file_to_phone(path)
    urls = [c["url"] for c in session.of_type("file")]
    assert len(set(urls)) == 2


def test_send_file_refuses_outside(home, session):
    assert basic.send_file_to_phone(str(home / "private.txt")).startswith("Error")
    assert session.of_type("file") == []
    assert list(basic.OUTBOX.iterdir()) == []


def test_send_file_refuses_folder(home, session):
    assert basic.send_file_to_phone(str(home / "Desktop" / "Projects")).startswith("Error")


# --------------------------------------------------------------- delete_file -----

def test_delete_asks_first_and_yes_deletes(home, session):
    target = home / "Desktop" / "old draft.txt"
    out = basic.delete_file(str(target))
    assert len(session.questions) == 1
    assert "old draft.txt" in session.questions[0]
    assert out == "Deleted old draft.txt"
    assert not target.exists()


def test_delete_no_keeps_the_file(home, session):
    session.answer = False
    target = home / "Desktop" / "old draft.txt"
    out = basic.delete_file(str(target))
    assert len(session.questions) == 1
    assert out.startswith("Cancelled")
    assert target.exists()


def test_delete_without_a_phone_never_deletes(home, monkeypatch):
    monkeypatch.setattr(actions, "current_session", None)
    target = home / "Desktop" / "old draft.txt"
    assert basic.delete_file(str(target)).startswith("Cancelled")
    assert target.exists()


def test_delete_refuses_outside_without_asking(home, session):
    out = basic.delete_file(str(home / "private.txt"))
    assert out.startswith("Error")
    assert session.questions == []
    assert (home / "private.txt").exists()


# ------------------------------------------------------------------ open_app -----

def test_open_app_launches_and_shows_status(session, launched):
    out = basic.open_app("Spotify")
    assert "Spotify" in out
    assert not out.startswith("Error"), out
    assert len(launched) == 1
    assert any("Spotify" in m["text"] for m in session.of_type("status"))


def test_open_app_returns_error_text_when_launch_fails(session, monkeypatch):
    def boom(*a, **k):
        raise OSError("no such app")
    monkeypatch.setattr(basic.subprocess, "Popen", boom)
    monkeypatch.setattr(basic.subprocess, "run", boom)
    monkeypatch.setattr(os, "startfile", boom, raising=False)
    if hasattr(basic, "_windows_apps"):
        monkeypatch.setattr(basic, "_windows_apps", lambda: {})
    assert basic.open_app("Nope").startswith("Error")


# ------------------------------------------------------ keyboard: type & keys -----

def test_type_text_types(keyboard):
    assert basic.type_text("hello") == "Typed 5 characters."
    assert keyboard.typed == ["hello"]


def test_press_keys_splits_shortcut(keyboard):
    assert basic.press_keys("Ctrl+S") == "Pressed Ctrl+S"
    assert keyboard.hotkeys == [("ctrl", "s")]


def test_keyboard_errors_become_text(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("no display")
    fake = types.SimpleNamespace(typewrite=boom, hotkey=boom)
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    assert basic.type_text("x").startswith("Error")
    assert basic.press_keys("enter").startswith("Error")


# ------------------------------------------------------------------- pc_info -----

def test_pc_info_mentions_os_and_home(home):
    out = basic.pc_info()
    assert str(home) in out
    assert out.split()[0] in ("Darwin", "Windows", "Linux")


# ------------------------------------------------------------- safety pass -----

def test_symlink_out_of_allowed_folder_is_refused(home, session):
    link = home / "Desktop" / "sneaky.txt"
    try:
        link.symlink_to(home / "private.txt")
    except (OSError, NotImplementedError):
        pytest.skip("this OS/user can't create symlinks")
    assert basic.send_file_to_phone(str(link)).startswith("Error")
    assert basic.delete_file(str(link)).startswith("Error")
    assert (home / "private.txt").exists()


def test_path_traversal_is_refused(home, session):
    sneaky = str(home / "Desktop" / ".." / "private.txt")
    assert basic.send_file_to_phone(sneaky).startswith("Error")
    assert basic.delete_file(sneaky).startswith("Error")


def test_every_tool_is_covered():
    """If Hands adds a tool, this reminds US (tests owner) to write a test for it.
    It only WARNS: a missing test is our job, so it must never turn the Hands PR red."""
    tested = {"list_files", "find_file", "open_file", "send_file_to_phone",
              "delete_file", "open_app", "type_text", "press_keys", "pc_info",
              "read_file_text"}
    tested |= {"media_key", "lock_pc", "sleep_pc", "click_at",  # test_media/power/pointer.py
               "open_url", "close_app", "scroll", "send_folder_to_phone"}  # test_extras.py
    missing = {f.__name__ for f in actions.TOOLS} - tested  # every file's tools, not just basic.py
    if missing:
        import warnings
        warnings.warn(f"New tools without tests (tests owner: add them): {sorted(missing)}")


WEIRD = ["", " ", "../../../../etc/passwd", "C:\\Windows\\System32", "a" * 5000,
         "~root", "Desktop/\n/etc",
         "\x00"]  # null character: was a Hands bug, fixed in PR 9


@pytest.mark.parametrize("bad", WEIRD)
def test_file_tools_never_raise_on_weird_input(home, session, launched, bad):
    """Contract: tools never raise, they return text."""
    for tool in (basic.list_files, basic.find_file, basic.open_file,
                 basic.send_file_to_phone, basic.delete_file):
        try:
            out = tool(bad)
        except Exception as e:  # noqa: BLE001
            pytest.fail(f"{tool.__name__}({bad[:30]!r}) raised {type(e).__name__}: {e}")
        assert isinstance(out, str)


# ----------------------------------------------------------- read_file_text -----
# Added by Hands in PR 9. Skipped until that is merged into main.

needs_read = pytest.mark.skipif(not hasattr(basic, "read_file_text"),
                                reason="read_file_text not in main yet (Hands PR 9)")


@needs_read
def test_read_file_text_reads_markdown(home, session):
    out = basic.read_file_text(str(home / "Documents" / "notes.md"))
    assert "# notes" in out
    assert any("notes.md" in m["text"] for m in session.of_type("status"))


@needs_read
def test_read_file_text_cuts_long_files(home, session):
    big = home / "Documents" / "big.txt"
    big.write_text("Q" * 10_000)
    out = basic.read_file_text(str(big))
    assert out.count("Q") == 3000
    assert "first 3000" in out


@needs_read
def test_read_file_text_reads_docx(home, session):
    import zipfile
    doc = home / "Documents" / "letter.docx"
    xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
           '<w:body><w:p><w:r><w:t>Labas, ąčęėįšųūž!</w:t></w:r></w:p></w:body></w:document>')
    with zipfile.ZipFile(doc, "w") as z:
        z.writestr("word/document.xml", xml)
    assert "Labas, ąčęėįšųūž!" in basic.read_file_text(str(doc))


@needs_read
def test_read_file_text_refuses_outside_and_unknown_types(home, session):
    assert basic.read_file_text(str(home / "private.txt")).startswith("Error")
    (home / "Desktop" / "photo.heic").write_bytes(b"\x00\x01")
    assert basic.read_file_text(str(home / "Desktop" / "photo.heic")).startswith("Error")


@needs_read
def test_read_file_text_broken_docx_is_error_text(home, session):
    bad = home / "Documents" / "broken.docx"
    bad.write_text("not a zip")
    assert basic.read_file_text(str(bad)).startswith("Error")
