"""Tests for lock_pc / sleep_pc (pc/actions/power.py, Hands PR 12/13).  Owner: Demo, tests & safety.

Skipped until power.py is in main. Nothing really locks or sleeps: launches are faked.
"""
import types

import pytest

power = pytest.importorskip("pc.actions.power", reason="lock_pc/sleep_pc not in main yet (Hands PR 12/13)")
import pc.actions as actions  # noqa: E402


class FakeSession:
    def __init__(self, answer):
        self.answer, self.questions, self.emitted = answer, [], []

    def confirm(self, q, timeout=60):
        self.questions.append(q)
        return self.answer

    def status(self, text):
        self.emitted.append({"type": "status", "text": text})

    def emit(self, m):
        self.emitted.append(m)


@pytest.fixture
def launched(monkeypatch):
    calls = []
    monkeypatch.setattr(power.subprocess, "Popen", lambda *a, **k: calls.append(a))
    monkeypatch.setattr(power, "IS_WIN", False)  # never call the real Windows lock API
    return calls


@pytest.mark.parametrize("tool", ["lock_pc", "sleep_pc"])
def test_no_means_nothing_happens(monkeypatch, launched, tool):
    s = FakeSession(answer=False)
    monkeypatch.setattr(actions, "current_session", s)
    out = getattr(power, tool)()
    assert len(s.questions) == 1
    assert out.startswith("Cancelled")
    assert launched == []


@pytest.mark.parametrize("tool", ["lock_pc", "sleep_pc"])
def test_no_phone_means_nothing_happens(monkeypatch, launched, tool):
    monkeypatch.setattr(actions, "current_session", None)
    assert getattr(power, tool)().startswith("Cancelled")
    assert launched == []


@pytest.mark.parametrize("tool", ["lock_pc", "sleep_pc"])
def test_yes_runs_it(monkeypatch, launched, tool):
    s = FakeSession(answer=True)
    monkeypatch.setattr(actions, "current_session", s)
    out = getattr(power, tool)()
    assert not out.startswith(("Error", "Cancelled")), out
    assert len(launched) == 1


def test_sleep_warns_the_call_will_end(monkeypatch, launched):
    s = FakeSession(answer=False)
    monkeypatch.setattr(actions, "current_session", s)
    power.sleep_pc()
    assert "end" in s.questions[0].lower()


def test_power_tools_are_tools_the_brain_sees():
    assert power.lock_pc in actions.TOOLS and power.sleep_pc in actions.TOOLS
