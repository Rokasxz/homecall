"""Tests for click_at (pc/actions/pointer.py, Hands PR 20).  Owner: Demo, tests & safety.

Skipped until pointer.py is in main. The mouse is faked: nothing is really clicked.
"""
import sys
import types

import pytest

pointer = pytest.importorskip("pc.actions.pointer", reason="click_at not in main yet (Hands PR 20)")
import inspect  # noqa: E402

import pc.actions as actions  # noqa: E402


def click(*args, **kwargs):
    """Call click_at; works whether or not it has the suggested 'what' argument."""
    if "what" in inspect.signature(pointer.click_at).parameters:
        kwargs.setdefault("what", "OK button")
    return pointer.click_at(*args, **kwargs)


class FakeSession:
    def __init__(self):
        self.emitted = []

    def status(self, text):
        self.emitted.append(text)

    def emit(self, m):
        self.emitted.append(m)


@pytest.fixture
def mouse(monkeypatch):
    """A 2880x1800 Mac-style screen; the AI's screenshot is 1280 wide (1280x800)."""
    fake = types.SimpleNamespace(clicks=[])
    fake.click = lambda x, y, clicks=1, interval=0: fake.clicks.append((x, y, clicks))
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setattr(pointer, "_main_screen", lambda: (0, 0, 2880, 1800))
    monkeypatch.setattr(pointer, "_shot_width", lambda: 1280)
    s = FakeSession()
    monkeypatch.setattr(actions, "current_session", s)
    return fake, s


def test_point_in_screenshot_is_scaled_to_the_real_screen(mouse):
    fake, s = mouse
    out = click(100, 100)
    assert not out.startswith("Error"), out
    assert fake.clicks == [(225, 225, 1)]
    assert s.emitted, "no status shown on the phone"


def test_double_click(mouse):
    fake, _ = mouse
    click(640, 400, double=True)
    assert fake.clicks == [(1440, 900, 2)]


@pytest.mark.parametrize("x, y", [(-1, 10), (10, -1), (1280, 10), (10, 800), (99999, 99999)])
def test_outside_the_screenshot_is_error_and_no_click(mouse, x, y):
    fake, _ = mouse
    assert click(x, y).startswith("Error")
    assert fake.clicks == []


@pytest.mark.parametrize("x, y", [("abc", 1), (None, 1), (1.5, "2.5")])
def test_bad_numbers_never_raise(mouse, x, y):
    out = click(x, y)
    assert isinstance(out, str)


def test_mouse_failure_is_error_text(mouse, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("PyAutoGUI fail-safe triggered")
    monkeypatch.setitem(sys.modules, "pyautogui", types.SimpleNamespace(click=boom))
    assert click(10, 10).startswith("Error")


def test_screen_with_offset_monitor(mouse, monkeypatch):
    """Main screen not at (0,0), e.g. a second monitor on the left."""
    fake, _ = mouse
    monkeypatch.setattr(pointer, "_main_screen", lambda: (-1920, 0, 1920, 1080))
    click(0, 0)
    assert fake.clicks == [(-1920, 0, 1)]


def test_click_at_is_a_tool_the_brain_sees():
    assert pointer.click_at in actions.TOOLS


# ------------------------------------------- Yes/No before risky clicks (Hands PR 24) -----

needs_guard = pytest.mark.skipif(not hasattr(pointer, "is_risky"),
                                 reason="risky-click guard not in main yet (Hands PR 24)")


class AskingSession(FakeSession):
    def __init__(self, answer):
        super().__init__()
        self.answer, self.questions = answer, []

    def confirm(self, q, timeout=60):
        self.questions.append(q)
        return self.answer


@pytest.fixture
def asking(mouse, monkeypatch):
    fake, _ = mouse
    s = AskingSession(answer=False)
    monkeypatch.setattr(actions, "current_session", s)
    return fake, s


@needs_guard
@pytest.mark.parametrize("what", ["Send button", "Delete", "Move to Bin", "Buy now", "Allow",
                                  "Install", "Sign out", "Pay with card"])
def test_risky_click_asks_and_no_means_no_click(asking, what):
    fake, s = asking
    out = pointer.click_at(100, 100, what=what)
    assert s.questions, f"'{what}' was clicked with no Yes/No"
    assert out.startswith("Cancelled") and fake.clicks == []


@needs_guard
def test_risky_click_yes_clicks(asking):
    fake, s = asking
    s.answer = True
    pointer.click_at(100, 100, what="Send button")
    assert fake.clicks == [(225, 225, 1)]


@needs_guard
@pytest.mark.parametrize("what", ["Play button", "Search box", "Next track", "Spotify icon"])
def test_harmless_click_does_not_ask(asking, what):
    fake, s = asking
    pointer.click_at(100, 100, what=what)
    assert s.questions == [] and len(fake.clicks) == 1


@needs_guard
def test_risky_click_without_a_phone_never_clicks(mouse, monkeypatch):
    fake, _ = mouse
    monkeypatch.setattr(actions, "current_session", None)
    assert pointer.click_at(100, 100, what="Delete").startswith("Cancelled")
    assert fake.clicks == []


@needs_guard
@pytest.mark.parametrize("what", ["", "   ", None])
def test_click_must_say_what(asking, what):
    fake, _ = asking
    assert pointer.click_at(100, 100, what=what).startswith("Error")
    assert fake.clicks == []


# Known gaps (posted on Hands PR 24). Not strict: a fix shows as XPASS, never turns CI red.

@needs_guard
@pytest.mark.xfail(strict=False, reason="Hands: double-clicking a script/app opens (runs) it with no Yes/No")
@pytest.mark.parametrize("what", ["run-me.command", "setup.exe icon", "Evil.app"])
def test_double_click_on_a_program_asks(asking, what):
    fake, s = asking
    pointer.click_at(100, 100, what=what, double=True)
    assert s.questions and fake.clicks == []


@needs_guard
@pytest.mark.xfail(strict=False, reason="Hands: Lithuanian button words aren't risky words yet")
@pytest.mark.parametrize("what", ["Siųsti", "Ištrinti", "Pirkti", "Leisti", "Patvirtinti"])
def test_lithuanian_risky_buttons_ask(asking, what):
    fake, s = asking
    pointer.click_at(100, 100, what=what)
    assert s.questions and fake.clicks == []


@needs_guard
@pytest.mark.xfail(strict=False, reason="Hands: these risky words are missing from RISKY_WORDS")
@pytest.mark.parametrize("what", ["Replace", "Overwrite", "Share", "Reply", "Forward", "Upload", "Open Anyway"])
def test_more_risky_words_ask(asking, what):
    fake, s = asking
    pointer.click_at(100, 100, what=what)
    assert s.questions and fake.clicks == []


@needs_guard
@pytest.mark.xfail(strict=False, reason="Hands: Mac hides extensions, so a program shows as just 'Evil'; double-click doesn't ask")
@pytest.mark.parametrize("what", ["Evil icon on the Desktop", "Free Movie Player"])
def test_double_click_on_a_program_without_visible_extension_asks(asking, what):
    """macOS hides .app/.command by default, so the AI only sees the name. A double-click opens it."""
    fake, s = asking
    pointer.click_at(100, 100, what=what, double=True)
    assert s.questions and fake.clicks == []
