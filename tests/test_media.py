"""Tests for media_key (pc/actions/media.py, Hands PR 10).  Owner: Demo, tests & safety.

Skipped until media.py is in main. The keyboard is faked: nothing is really pressed.
"""
import sys
import types

import pytest

media = pytest.importorskip("pc.actions.media", reason="media_key not in main yet (Hands PR 10)")
import pc.actions as actions  # noqa: E402


class FakeSession:
    def __init__(self):
        self.emitted = []

    def emit(self, msg):
        self.emitted.append(msg)

    def status(self, text):
        self.emit({"type": "status", "text": text})


@pytest.fixture
def keys(monkeypatch):
    fake = types.SimpleNamespace(pressed=[])
    fake.press = lambda key, presses=1, interval=0: fake.pressed.append((key, presses))
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setattr(media, "IS_MAC", False)
    monkeypatch.setattr(actions, "current_session", FakeSession())
    return fake


@pytest.mark.parametrize("said, key", [("pause", "playpause"), ("Next track", "nexttrack"),
                                        ("volume-up", "volumeup"), ("mute", "volumemute")])
def test_media_key_presses_the_right_key(keys, said, key):
    out = media.media_key(said)
    assert not out.startswith("Error"), out
    assert keys.pressed == [(key, 1)]


def test_volume_can_repeat_but_play_cannot(keys):
    media.media_key("volume up", 5)
    media.media_key("play", 5)
    assert keys.pressed == [("volumeup", 5), ("playpause", 1)]


@pytest.mark.parametrize("bad", [("dance", 1), ("next", 0), ("next", 99), ("next", "lots")])
def test_bad_input_is_error_text_and_presses_nothing(keys, bad):
    assert media.media_key(*bad).startswith("Error")
    assert keys.pressed == []


def test_mac_never_crashes_and_never_touches_real_apps(keys, monkeypatch):
    """On a Mac, media_key either says 'not supported' (old) or talks to Spotify/Music via
    AppleScript (Hands PR 18). AppleScript is faked so the test never plays real music."""
    monkeypatch.setattr(media, "IS_MAC", True)
    scripts = []
    if hasattr(media, "_osascript"):
        monkeypatch.setattr(media, "_osascript", lambda script: (scripts.append(script) or (False, "")))
    out = media.media_key("play")
    assert isinstance(out, str)
    assert keys.pressed == []  # no real key press on a Mac


@pytest.mark.skipif(not hasattr(media, "_osascript"), reason="Mac media support not in main yet (Hands PR 18)")
def test_mac_plays_in_spotify_when_it_is_open(keys, monkeypatch):
    monkeypatch.setattr(media, "IS_MAC", True)
    scripts = []

    def fake(script):
        scripts.append(script)
        return True, "true" if script == 'application "Spotify" is running' else ""
    monkeypatch.setattr(media, "_osascript", fake)
    out = media.media_key("next")
    assert "Spotify" in out and not out.startswith("Error"), out
    assert any("next track" in s for s in scripts)


@pytest.mark.skipif(not hasattr(media, "_osascript"), reason="Mac media support not in main yet (Hands PR 18)")
def test_mac_nothing_open_is_error_text(keys, monkeypatch):
    monkeypatch.setattr(media, "IS_MAC", True)
    monkeypatch.setattr(media, "_osascript", lambda script: (True, "false"))
    assert media.media_key("play").startswith("Error")


def test_media_key_is_a_tool_the_brain_sees():
    assert media.media_key in actions.TOOLS
