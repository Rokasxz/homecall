"""Tests for search_in_files, find_recent_files (search.py) and get/set_clipboard (clipboard.py), #45.

Temporary fake home folder; the clipboard is faked, so nothing real is read or written.
"""
import pytest

search = pytest.importorskip("pc.actions.search", reason="search.py not in main yet (#45)")
clipboard = pytest.importorskip("pc.actions.clipboard", reason="clipboard.py not in main yet (#45)")
import pc.actions as actions  # noqa: E402
from pc.actions import basic  # noqa: E402


class FakeSession:
    def __init__(self, answer=True):
        self.answer, self.questions, self.emitted = answer, [], []

    def confirm(self, q, timeout=60):
        self.questions.append(q)
        return self.answer

    def status(self, t):
        self.emitted.append(t)

    def emit(self, m):
        self.emitted.append(m)


@pytest.fixture
def session(monkeypatch):
    s = FakeSession()
    monkeypatch.setattr(actions, "current_session", s)
    return s


@pytest.fixture
def home(tmp_path, monkeypatch):
    h = tmp_path / "home"
    roots = {n: h / n for n in ("Desktop", "Documents", "Downloads", "Pictures")}
    for r in roots.values():
        r.mkdir(parents=True)
    (roots["Documents"] / "trip.txt").write_text("Book the cabin by Friday. Budget 300 EUR.")
    (roots["Desktop"] / "todo.md").write_text("- call grandma")
    (h / "secret.txt").write_text("bank password hunter2")  # OUTSIDE the 4 folders
    monkeypatch.setattr(basic, "HOME", h)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", list(roots.values()))
    monkeypatch.setattr(basic, "SPECIAL_FOLDERS", roots, raising=False)
    return h


def test_search_finds_text_inside_documents(home, session):
    out = search.search_in_files("cabin")
    assert "trip.txt" in out


def test_search_never_reads_outside_the_4_folders(home, session):
    assert "hunter2" not in search.search_in_files("password")


@pytest.mark.xfail(strict=False, reason="Hands: search follows a symlink inside the 4 folders to a file outside")
def test_search_never_follows_a_symlink_out(home, session):
    try:
        (home / "Desktop" / "notes.txt").symlink_to(home / "secret.txt")
    except OSError:
        pytest.skip("can't make symlinks here")
    assert "hunter2" not in search.search_in_files("password")


def test_recent_files_lists_new_files_only_inside(home, session):
    out = search.find_recent_files(7)
    assert "trip.txt" in out and "secret.txt" not in out


def test_reading_the_clipboard_asks_first_and_no_reads_nothing(session, monkeypatch):
    session.answer = False
    read = []
    monkeypatch.setattr(clipboard, "read_clipboard_text", lambda: read.append(1) or "hunter2")
    out = clipboard.get_clipboard()
    assert out.startswith("Cancelled") and read == [] and session.questions


def test_reading_the_clipboard_yes(session, monkeypatch):
    monkeypatch.setattr(clipboard, "read_clipboard_text", lambda: "hello")
    assert "hello" in clipboard.get_clipboard()


def test_reading_the_clipboard_without_a_phone_reads_nothing(monkeypatch):
    monkeypatch.setattr(actions, "current_session", None)
    monkeypatch.setattr(clipboard, "read_clipboard_text", lambda: "hunter2")
    assert "hunter2" not in clipboard.get_clipboard()


@pytest.mark.parametrize("bad", ["", "x" * 10_001])
def test_set_clipboard_bad_input(session, monkeypatch, bad):
    wrote = []
    monkeypatch.setattr(clipboard, "write_clipboard_text", lambda t: wrote.append(t) or True)
    assert clipboard.set_clipboard(bad).startswith("Error") and wrote == []


def test_set_clipboard_writes(session, monkeypatch):
    wrote = []
    monkeypatch.setattr(clipboard, "write_clipboard_text", lambda t: wrote.append(t) or True)
    assert not clipboard.set_clipboard("Gedimino pr. 1").startswith("Error")
    assert wrote == ["Gedimino pr. 1"]
