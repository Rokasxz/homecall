"""Safety pass: things an attacker (or a confused AI) might try.  Owner: Demo, tests & safety.

Run from the project root:   python -m pytest tests/ -v

Tests marked xfail are KNOWN GAPS, written up for their owner in TASKS.md and
demo/SAFETY-PASS.md. When the owner fixes one, its test turns into "XPASS"
(a failure, because strict=True): then remove the xfail mark here.
"""
import json

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

@pytest.mark.xfail(strict=True, reason="Server: no lockout after wrong codes yet (TASKS.md)")
def test_lockout_after_5_wrong_codes(client):
    for _ in range(5):
        with client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "hello", "code": wrong_code()})
            first_json(ws)
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "hello", "code": server.PAIR_CODE})
        assert first_json(ws)["type"] != "welcome", "right code still works after 5 wrong ones"


@pytest.mark.xfail(strict=True, reason="Server: a second phone can join a running call (TASKS.md)")
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

@pytest.mark.xfail(strict=True, reason="Voice/Server: /voice endpoints don't check the pairing code (TASKS.md)")
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


@pytest.mark.xfail(strict=True, reason="Hands: open_file runs scripts/apps without asking (TASKS.md)")
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
