"""Safety pass: things an attacker (or a confused AI) might try.  Owner: Demo, tests & safety.

Run from the project root:   python -m pytest tests/ -v

Tests marked xfail are KNOWN GAPS, written up for their owner in TASKS.md and
demo/SAFETY-PASS.md. They are NOT strict: when an owner fixes one, the owner's
Pull Request stays green and the test shows as "XPASS" (= fixed). Then remove
the xfail mark here. (Strict marks turned the owners' CI red for doing the right
thing, so we don't use them.)
"""
import json
import sys
import types

import pytest
from fastapi.testclient import TestClient

import pc.actions as actions
from pc import server
from pc.actions import basic


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server.screen, "capture_jpeg", lambda *a, **k: b"\xff\xd8x")
    monkeypatch.setattr(server.screen, "capture_png", lambda *a, **k: b"png")
    monkeypatch.setattr(server, "FRAME_EVERY", 0.05)
    monkeypatch.setattr(server, "OUTBOX", tmp_path)
    with TestClient(server.app) as c:
        yield c


def first_json(ws, limit=200):
    for _ in range(limit):
        m = ws.receive()
        if m.get("type") == "websocket.close":
            return {"type": "closed"}
        if m.get("text") is not None:
            return json.loads(m["text"])
    raise AssertionError("no JSON message")


def wrong_code():
    return "000000" if server.PAIR_CODE != "000000" else "111111"


# ------------------------------------------------------------ server (lead) -----

@pytest.mark.xfail(strict=False, reason="Server: no lockout after wrong codes yet (TASKS.md)")
def test_lockout_after_5_wrong_codes(client):
    for _ in range(5):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "code": wrong_code()})
            first_json(ws)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "code": server.PAIR_CODE})
        assert first_json(ws)["type"] != "welcome", "right code still works after 5 wrong ones"


@pytest.mark.xfail(strict=False, reason="Server: a second phone can join a running call (TASKS.md)")
def test_only_one_phone_at_a_time(client):
    with client.websocket_connect("/ws") as a:
        a.send_json({"type": "hello", "code": server.PAIR_CODE})
        assert first_json(a)["type"] == "welcome"
        with client.websocket_connect("/ws") as b:
            b.send_json({"type": "hello", "code": server.PAIR_CODE})
            assert first_json(b)["type"] != "welcome"


def test_garbage_first_message_does_not_kill_the_server(client):
    for junk in ["hi", "[1, 2]", "{"]:
        try:
            with client.websocket_connect("/ws") as ws:
                ws.send_text(junk)
                ws.receive()
        except Exception:  # noqa: BLE001 - the socket may just drop; that's fine
            pass
    assert client.get("/health").text == "ok"


@pytest.mark.parametrize("token", ["", "*", "?", "[a-z]*", "a__b"])
def test_download_wildcards_dont_leak(client, tmp_path, token):
    (tmp_path / "SECRETTOKEN123__private.txt").write_text("secret")
    r = client.get(f"/files/{token}")
    assert b"secret" not in r.content


# ------------------------------------------------------------- voice (Voice) -----

@pytest.mark.xfail(strict=False, reason="Voice/Server: /voice endpoints don't check the pairing code (TASKS.md)")
def test_voice_endpoints_need_the_pairing_code(client):
    r = client.get("/voice/speak", params={"text": "hi"})
    assert r.status_code in (401, 403)


# ------------------------------------------------------------- hands (Hands) -----

@pytest.fixture
def desktop(tmp_path, monkeypatch):
    d = tmp_path / "Desktop"
    d.mkdir()
    monkeypatch.setattr(basic, "HOME", tmp_path)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", [d])
    launched = []
    monkeypatch.setattr(basic.subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(actions, "current_session", None)
    return d, launched


# Was a known gap; fixed in Hands PR 13. Now a guard: must stay green.
@pytest.mark.parametrize("name", ["run-me.command", "run-me.sh", "Evil.app", "setup.exe", "x.bat"])
def test_open_file_does_not_run_programs_without_asking(desktop, name):
    d, launched = desktop
    target = d / name
    if name.endswith(".app"):
        target.mkdir()
    else:
        target.write_text("echo pwned")
    basic.open_file(str(target))
    assert launched == [], "a program was launched with no Yes/No on the phone"


# Was a known gap; fixed in Hands PR 13. Now a guard: must stay green.
@pytest.mark.parametrize("path", ["~/Downloads/Evil.app", "/tmp/evil.sh", "C:\\Users\\me\\Downloads\\evil.exe"])
def test_open_app_refuses_program_paths(monkeypatch, path):
    """open_app is for app NAMES. A full path would bypass the 4-folder rule and run anything."""
    launched = []
    monkeypatch.setattr(basic.subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(basic.subprocess, "run",
                        lambda *a, **k: launched.append(a) or type("R", (), {"returncode": 0})())
    monkeypatch.setattr(basic.shutil, "which", lambda name, *a, **k: name)  # "the file exists"
    monkeypatch.setattr(actions, "current_session", None)
    if hasattr(basic, "_windows_apps"):
        monkeypatch.setattr(basic, "_windows_apps", lambda: {})
    out = basic.open_app(path)
    assert launched == [] and out.startswith("Error"), f"launched {launched}: {out}"


@pytest.mark.skipif(not hasattr(basic, "read_file_text"), reason="read_file_text not in main yet")
def test_read_file_text_refuses_symlink_out(tmp_path, monkeypatch):
    d = tmp_path / "Desktop"
    d.mkdir()
    (tmp_path / "secret.txt").write_text("top secret")
    try:
        (d / "link.txt").symlink_to(tmp_path / "secret.txt")
    except OSError:
        pytest.skip("can't make symlinks here")
    monkeypatch.setattr(basic, "HOME", tmp_path)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", [d])
    monkeypatch.setattr(actions, "current_session", None)
    out = basic.read_file_text(str(d / "link.txt"))
    assert "top secret" not in out


# ------------------------------------------------- terminal guard (Hands PR 13) -----

needs_guard = pytest.mark.skipif(not hasattr(basic, "_ok_to_run_in_terminal"),
                                 reason="terminal guard not in main yet (Hands PR 13)")


class _AskSession:
    def __init__(self, answer=False):
        self.answer, self.questions, self.emitted = answer, [], []

    def confirm(self, q, timeout=60):
        self.questions.append(q)
        return self.answer

    def status(self, t):
        self.emitted.append(t)

    def emit(self, m):
        self.emitted.append(m)


@pytest.fixture
def terminal_in_front(monkeypatch):
    fake = types.SimpleNamespace(pressed=[], typed=[], KEYBOARD_KEYS=None)
    fake.hotkey = lambda *k: fake.pressed.append(k)
    fake.typewrite = lambda t, interval=0: fake.typed.append(t)
    fake.write = fake.typewrite
    fake.press = lambda *a, **k: fake.pressed.append(a)
    monkeypatch.setitem(sys.modules, "pyautogui", fake)
    monkeypatch.setattr(basic, "_terminal_in_front", lambda: True)
    monkeypatch.setattr(basic, "IS_WIN", False)  # use the pyautogui path, not Windows SendInput
    s = _AskSession(answer=False)
    monkeypatch.setattr(actions, "current_session", s)
    return fake, s


@needs_guard
@pytest.mark.parametrize("key", ["enter", "Enter"])
def test_enter_in_a_terminal_asks_first(terminal_in_front, key):
    fake, s = terminal_in_front
    assert basic.press_keys(key).startswith("Cancelled")
    assert s.questions and fake.pressed == []


@needs_guard
def test_return_key_in_a_terminal_asks_first(terminal_in_front):
    fake, s = terminal_in_front
    basic.press_keys("return")
    assert s.questions and fake.pressed == [], "'return' ran a command with no Yes/No"


@needs_guard
def test_typing_a_command_with_newline_in_a_terminal_asks_first(terminal_in_front):
    fake, s = terminal_in_front
    assert basic.type_text("rm -rf ~/Documents\n").startswith("Cancelled")
    assert fake.typed == []

