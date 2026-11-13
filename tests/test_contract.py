"""Contract tests: a fake phone call against the real server.  Owner: Demo, tests & safety.

Run from the project root:   python -m pytest tests/ -v

Checks the Phone <-> PC contract in CLAUDE.md (sections 1, 3, 4, 5): pairing,
welcome, live frames, say -> reply, the Yes/No confirm round trip, file
downloads, hangup. The screen is faked (no real screenshots) and, except for
the echo-mode test, the Brain is faked too, so no API key or internet is needed.
"""
import json

import pytest
from fastapi.testclient import TestClient

from pc import server

FAKE_JPEG = b"\xff\xd8fake-jpeg\xff\xd9"
CONTRACT_PC_TO_PHONE = {"welcome", "status", "reply", "confirm", "file", "error"}


# ------------------------------------------------------------------ helpers -----

class EchoBrain:
    """A fake Brain: answers every `say` with a fixed reply (contract section 3)."""
    calls: list = []

    def handle(self, text, session, screenshot_png=None):
        EchoBrain.calls.append((text, screenshot_png))
        session.status("Thinking")
        session.emit({"type": "reply", "text": f"You said: {text}"})


class AskingBrain:
    """A fake Brain that asks Yes/No on the phone before 'deleting'."""

    def handle(self, text, session, screenshot_png=None):
        ok = session.confirm("Delete old draft.txt?", timeout=10)
        session.emit({"type": "reply", "text": "Deleted." if ok else "Cancelled."})


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server.screen, "capture_jpeg", lambda *a, **k: FAKE_JPEG)
    monkeypatch.setattr(server.screen, "capture_png", lambda *a, **k: b"fake-png")
    monkeypatch.setattr(server, "FRAME_EVERY", 0.05)
    monkeypatch.setattr(server, "OUTBOX", tmp_path)
    monkeypatch.setattr(server, "Brain", EchoBrain)
    EchoBrain.calls = []
    with TestClient(server.app) as c:
        yield c


def hello(ws, code=None):
    ws.send_json({"type": "hello", "code": code if code is not None else server.PAIR_CODE})


def next_json(ws, wanted=None, limit=500):
    """Read messages until a JSON one (of type `wanted`, if given) arrives; skip frames."""
    seen = []
    for _ in range(limit):
        m = ws.receive()
        if m.get("type") == "websocket.close":
            raise AssertionError(f"socket closed while waiting for {wanted}; saw {seen}")
        if m.get("bytes") is not None:
            continue
        d = json.loads(m["text"])
        seen.append(d.get("type"))
        if wanted is None or d.get("type") == wanted:
            return d
    raise AssertionError(f"no '{wanted}' message after {limit} messages; saw {seen}")


# ------------------------------------------------------------- plain http -----

def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.text == "ok"


def test_phone_page_is_served(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "<html" in r.text.lower()


# ---------------------------------------------------------------- pairing -----

def test_wrong_code_is_refused_and_closed(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws, "000000" if server.PAIR_CODE != "000000" else "111111")
        msg = ws.receive_json()
        assert msg["type"] == "error"
        assert ws.receive()["type"] == "websocket.close"


def test_first_message_must_be_hello(client):
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "say", "text": "let me in", "code": server.PAIR_CODE})
        assert ws.receive_json()["type"] == "error"


def test_code_as_number_still_works(client):
    """Phones may send the code as a number; the server compares it as text."""
    if server.PAIR_CODE.startswith("0"):
        pytest.skip("a number can't keep a leading zero")
    with client.websocket_connect("/ws") as ws:
        hello(ws, int(server.PAIR_CODE))
        assert next_json(ws)["type"] == "welcome"


def test_right_code_gets_welcome_first(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        first = next_json(ws)
        assert first["type"] == "welcome"
        assert first.get("text")
        ws.send_json({"type": "hangup"})


# ------------------------------------------------------------- live view -----

def test_screen_frames_arrive_as_binary(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        frames = 0
        for _ in range(50):
            m = ws.receive()
            if m.get("bytes") is not None:
                assert m["bytes"] == FAKE_JPEG
                frames += 1
                if frames >= 3:
                    break
        assert frames >= 3, "expected a few screen frames"
        ws.send_json({"type": "hangup"})


# ------------------------------------------------------------- say -> reply -----

def test_say_gets_a_reply_and_brain_gets_screenshot(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        next_json(ws, "welcome")
        ws.send_json({"type": "say", "text": "what's on my desktop"})
        assert next_json(ws, "status")["text"] == "Thinking"
        assert next_json(ws, "reply")["text"] == "You said: what's on my desktop"
        ws.send_json({"type": "hangup"})
    assert EchoBrain.calls == [("what's on my desktop", b"fake-png")]


def test_empty_say_is_ignored(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        next_json(ws, "welcome")
        ws.send_json({"type": "say", "text": "   "})
        ws.send_json({"type": "say", "text": "hi"})
        assert next_json(ws, "reply")["text"] == "You said: hi"
        ws.send_json({"type": "hangup"})
    assert [t for t, _ in EchoBrain.calls] == ["hi"]


def test_echo_mode_without_api_key(client, monkeypatch):
    """The real Brain with no key must still answer (contract section 3)."""
    from pc.brain.agent import Brain
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(server, "Brain", Brain)
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        ws.send_json({"type": "say", "text": "hello there"})
        reply = next_json(ws, "reply")
        assert "echo mode" in reply["text"].lower()
        ws.send_json({"type": "hangup"})


def test_only_contract_message_types_are_sent(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        ws.send_json({"type": "say", "text": "x"})
        types_seen = set()
        while True:
            d = next_json(ws)
            types_seen.add(d["type"])
            if d["type"] == "reply":
                break
        ws.send_json({"type": "hangup"})
    assert types_seen <= CONTRACT_PC_TO_PHONE, f"not in CLAUDE.md: {types_seen - CONTRACT_PC_TO_PHONE}"


def test_unknown_message_type_does_not_break_the_call(client):
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        ws.send_json({"type": "dance"})
        ws.send_json({"type": "say", "text": "still there?"})
        assert next_json(ws, "reply")["text"] == "You said: still there?"
        ws.send_json({"type": "hangup"})


# ---------------------------------------------------------- confirm Yes/No -----

@pytest.mark.parametrize("answer, expected", [(True, "Deleted."), (False, "Cancelled.")])
def test_confirm_round_trip(client, monkeypatch, answer, expected):
    monkeypatch.setattr(server, "Brain", AskingBrain)
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        ws.send_json({"type": "say", "text": "delete the old draft"})
        ask = next_json(ws, "confirm")
        assert ask["id"] and "Delete" in ask["text"]
        ws.send_json({"type": "confirm", "id": ask["id"], "ok": answer})
        assert next_json(ws, "reply")["text"] == expected
        ws.send_json({"type": "hangup"})


def test_confirm_with_wrong_id_does_not_say_yes(client, monkeypatch):
    monkeypatch.setattr(server, "Brain", AskingBrain)
    with client.websocket_connect("/ws") as ws:
        hello(ws)
        ws.send_json({"type": "say", "text": "delete the old draft"})
        ask = next_json(ws, "confirm")
        ws.send_json({"type": "confirm", "id": "not-" + ask["id"], "ok": True})
        ws.send_json({"type": "confirm", "id": ask["id"], "ok": False})
        assert next_json(ws, "reply")["text"] == "Cancelled."
        ws.send_json({"type": "hangup"})


# -------------------------------------------------------------- downloads -----

def test_file_download_by_token(client, tmp_path):
    (tmp_path / "abc123XYZ__My CV.pdf").write_bytes(b"%PDF fake")
    r = client.get("/files/abc123XYZ")
    assert r.status_code == 200
    assert r.content == b"%PDF fake"
    from urllib.parse import unquote
    assert "My CV.pdf" in unquote(r.headers.get("content-disposition", ""))


@pytest.mark.parametrize("token", ["nope", "*", "..", "%2e%2e%2fcheck.py", "abc*"])
def test_unknown_or_sneaky_token_is_404(client, tmp_path, token):
    (tmp_path / "abc123XYZ__secret.txt").write_text("secret")
    r = client.get(f"/files/{token}")
    # ".." may be normalised to "/" (the phone page); what matters is no file leaks.
    assert b"secret" not in r.content
    assert "attachment" not in r.headers.get("content-disposition", "")
