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
