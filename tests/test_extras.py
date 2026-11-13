"""Tests for open_url, close_app, scroll, send_folder_to_phone (pc/actions/extras.py, #38).  Owner: tests.

Nothing real happens: browser, AppleScript, mouse and the Windows window list are faked;
files live in a temporary fake home folder.
"""
import sys
import types
import zipfile

import pytest

extras = pytest.importorskip("pc.actions.extras", reason="extras.py not in main yet (#38)")
import pc.actions as actions  # noqa: E402
from pc.actions import basic  # noqa: E402


class FakeSession:
    def __init__(self, answer=True):
        self.answer, self.questions, self.emitted = answer, [], []

    def confirm(self, q, timeout=60):
        self.questions.append(q)
        return self.answer

    def status(self, text):
        self.emitted.append({"type": "status", "text": text})

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
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setattr(basic, "HOME", h)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", list(roots.values()))
    monkeypatch.setattr(basic, "SPECIAL_FOLDERS", roots, raising=False)
    monkeypatch.setattr(basic, "OUTBOX", outbox)
    return h


# ------------------------------------------------------------------- open_url -----

@pytest.fixture
def browser(monkeypatch):
    opened = []
    monkeypatch.setattr(extras.webbrowser, "open", lambda url, new=0: opened.append(url) or True)
    return opened


@pytest.mark.parametrize("given, expected", [("youtube.com", "https://youtube.com"),
                                             ("https://example.com/a?b=1", "https://example.com/a?b=1")])
def test_open_url_opens_websites(session, browser, given, expected):
    assert not extras.open_url(given).startswith("Error")
    assert browser == [expected]


@pytest.mark.parametrize("bad", ["file:///etc/passwd", "javascript:alert(1)", "ms-settings:privacy",
                                 "C:\\Windows\\System32\\cmd.exe", "smb://evil/share", "https://user:pw@evil.com",
                                 "localhost", "", "x" * 3000, "open terminal"])
def test_open_url_refuses_non_websites(session, browser, bad):
    assert extras.open_url(bad).startswith("Error")
    assert browser == []


# ------------------------------------------------------------------ close_app -----

def test_close_app_asks_first_and_no_means_nothing(session, monkeypatch):
    session.answer = False
    ran = []
    monkeypatch.setattr(extras, "IS_MAC", True)
    monkeypatch.setattr(extras, "IS_WIN", False)
    monkeypatch.setattr(extras.subprocess, "run", lambda *a, **k: ran.append(a))
    assert extras.close_app("Spotify").startswith("Cancelled")
    assert session.questions and ran == []


def test_close_app_on_mac_yes_quits(session, monkeypatch):
    ran = []
    monkeypatch.setattr(extras, "IS_MAC", True)
    monkeypatch.setattr(extras, "IS_WIN", False)
    monkeypatch.setattr(extras.subprocess, "run",
                        lambda cmd, **k: ran.append(cmd) or types.SimpleNamespace(returncode=0))
    assert not extras.close_app("Spotify").startswith(("Error", "Cancelled"))
    assert ran and 'tell application "Spotify" to quit' in ran[0][-1]


@pytest.mark.parametrize("bad", ['Spotify" to quit\ndo shell script "rm -rf ~', "a\\b", ""])
def test_close_app_on_mac_refuses_script_tricks(session, monkeypatch, bad):
    ran = []
    monkeypatch.setattr(extras, "IS_MAC", True)
    monkeypatch.setattr(extras.subprocess, "run", lambda *a, **k: ran.append(a))
    assert extras.close_app(bad).startswith("Error")
    assert ran == []


def test_close_app_never_matches_protected_windows():
    wins = [{"hwnd": 1, "title": "Command Prompt - python -m pc.server", "exe": "cmd"},
            {"hwnd": 2, "title": "HomeCall tunnel", "exe": "cloudflared"},
            {"hwnd": 3, "title": "Spotify Premium", "exe": "spotify"}]
    assert extras.match_windows("python", wins) == []
    assert extras.match_windows("cmd", wins) == []
    assert [w["hwnd"] for w in extras.match_windows("spotify", wins)] == [3]


# --------------------------------------------------------------------- scroll -----

@pytest.fixture
def wheel(monkeypatch):
    fake = types.SimpleNamespace(calls=[])
    fake.scroll = lambda n: fake.calls.append(("v", n))
    fake.hscroll = lambda n: fake.calls.append(("h", n))
    fake.moveTo = lambda x, y: fake.calls.append(("move", x, y))
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    return fake


def test_scroll_down_and_up(session, wheel):
    assert not extras.scroll("down", 3).startswith("Error")
    assert not extras.scroll("up", 2).startswith("Error")
    vs = [c for c in wheel.calls if c[0] == "v"]
    assert vs[0][1] < 0 < vs[1][1]


@pytest.mark.parametrize("args", [("sideways",), ("down", 0), ("down", 99), ("down", "lots")])
def test_scroll_bad_input_is_error_and_no_scroll(session, wheel, args):
    assert extras.scroll(*args).startswith("Error")
    assert wheel.calls == []


# ------------------------------------------------------- send_folder_to_phone -----

def _zip_names(outbox):
    zips = list(outbox.glob("*.zip"))
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as z:
        return z.namelist(), {n: z.read(n) for n in z.namelist()}


def test_send_folder_zips_it_and_shows_a_card(home, session):
    proj = home / "Desktop" / "Project"
    (proj / "sub").mkdir(parents=True)
    (proj / "a.txt").write_text("A")
    (proj / "sub" / "b.txt").write_text("B")
    (proj / ".secret").write_text("hidden")
    out = extras.send_folder_to_phone(str(proj))
    assert not out.startswith("Error"), out
    names, _ = _zip_names(basic.OUTBOX)
    assert sorted(names) == ["a.txt", "sub/b.txt"]  # hidden files left out
    cards = [m for m in session.emitted if m.get("type") == "file"]
    assert cards and cards[0]["name"] == "Project.zip" and cards[0]["url"].startswith("/files/")


@pytest.mark.parametrize("where", ["Desktop", "/", "/etc", "Desktop/../.."])
def test_send_folder_refuses_whole_roots_and_outside(home, session, where):
    assert extras.send_folder_to_phone(where).startswith("Error")
    assert list(basic.OUTBOX.iterdir()) == []


@pytest.mark.xfail(strict=False, reason="Hands: a symlink INSIDE the folder is followed, leaking a file from outside the 4 folders")
def test_send_folder_never_includes_files_from_outside_via_symlink(home, session):
    secret = home / "private-key.txt"
    secret.write_text("TOP SECRET")
    proj = home / "Desktop" / "Project"
    proj.mkdir()
    (proj / "notes.txt").write_text("ok")
    try:
        (proj / "looks-normal.txt").symlink_to(secret)
    except OSError:
        pytest.skip("can't make symlinks here")
    extras.send_folder_to_phone(str(proj))
    zips = list(basic.OUTBOX.glob("*.zip"))
    if zips:
        _, contents = _zip_names(basic.OUTBOX)
        assert b"TOP SECRET" not in b"".join(contents.values()), "a file outside the 4 folders was sent"
