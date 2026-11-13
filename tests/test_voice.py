"""Tests for Voice (pc/voice/): ElevenLabs speak/transcribe + the duplex call bridge.  Owner: Voice.

No network, no key, no real AI: ElevenLabs calls are faked, the Brain is echo or a
fake that asks Yes/No. conftest.py hides every real key and .env.
"""
import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

from pc import server
from pc.voice import duplex, eleven

SECRET = "test-secret-123"


@pytest.fixture
def client(monkeypatch, tmp_path):
    monkeypatch.setattr(server.screen, "capture_jpeg", lambda *a, **k: b"\xff\xd8x")
    monkeypatch.setattr(server.screen, "capture_png", lambda *a, **k: b"png")
    monkeypatch.setattr(server, "OUTBOX", tmp_path)
    monkeypatch.setattr(duplex, "CALL", duplex.VoiceCall())
    monkeypatch.setattr(duplex._Door, "wrong", 0)
    monkeypatch.setattr(duplex._Door, "locked_until", 0.0)
    with TestClient(server.app) as c:
        yield c


def with_settings(monkeypatch, **values):
    real = eleven.setting
    monkeypatch.setattr(eleven, "setting", lambda name: values.get(name, real(name)))


def ask(client, text, secret=SECRET):
    """Send one user turn the way ElevenLabs' Custom LLM does; return the streamed text."""
    body = {"model": "homecall", "stream": True,
            "messages": [{"role": "system", "content": "x"}, {"role": "user", "content": text}]}
    r = client.post(f"/voice/llm/{secret}/chat/completions", json=body)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    events = [line[6:] for line in r.text.splitlines() if line.startswith("data: ")]
    assert events[-1] == "[DONE]"
    chunks = [json.loads(e) for e in events[:-1]]
    assert chunks[-1]["choices"][0]["finish_reason"] == "stop"
    return "".join(c["choices"][0]["delta"].get("content") or "" for c in chunks).removeprefix("... ")


# ------------------------------------------------- speak / transcribe (contract 6) -----

CODE = {"X-HomeCall-Code": server.PAIR_CODE}


def test_no_key_means_501_so_the_phone_falls_back(client):
    assert client.get("/voice/speak", params={"text": "hi"}, headers=CODE).status_code == 501
    r = client.post("/voice/transcribe", files={"audio": ("a.webm", b"xx", "audio/webm")}, headers=CODE)
    assert r.status_code == 501


def test_speak_and_transcribe_need_the_pairing_code(client, monkeypatch):
    with_settings(monkeypatch, ELEVENLABS_API_KEY="k")
    monkeypatch.setattr(eleven, "text_to_speech", lambda text: b"mp3")
    assert client.get("/voice/speak", params={"text": "hi"}).status_code == 403
    assert client.post("/voice/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}).status_code == 403
    assert client.get("/voice/speak", params={"text": "hi", "code": server.PAIR_CODE}).status_code == 200


def test_speak_returns_mp3_with_a_key(client, monkeypatch):
    with_settings(monkeypatch, ELEVENLABS_API_KEY="k")
    monkeypatch.setattr(eleven, "text_to_speech", lambda text: b"ID3fake-mp3:" + text.encode())
    r = client.get("/voice/speak", params={"text": "hello"}, headers=CODE)
    assert r.status_code == 200 and r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3fake-mp3:hello"


def test_transcribe_returns_text_with_a_key(client, monkeypatch):
    with_settings(monkeypatch, ELEVENLABS_API_KEY="k")
    monkeypatch.setattr(eleven, "speech_to_text", lambda audio, mime: "find my cv")
    r = client.post("/voice/transcribe", files={"audio": ("a.m4a", b"xx", "audio/mp4")}, headers=CODE)
    assert r.json() == {"text": "find my cv"}


def test_provider_error_is_502_not_a_crash(client, monkeypatch):
    with_settings(monkeypatch, ELEVENLABS_API_KEY="k")

    def boom(text):
        raise RuntimeError("ElevenLabs said 401: out of credits")
    monkeypatch.setattr(eleven, "text_to_speech", boom)
    r = client.get("/voice/speak", params={"text": "hi"}, headers=CODE)
    assert r.status_code == 502 and "credits" in r.json()["detail"]


# -------------------------------------------------------- the LLM bridge (duplex) -----

def test_llm_endpoint_needs_the_secret(client, monkeypatch):
    body = {"messages": [{"role": "user", "content": "hi"}]}
    assert client.post("/voice/llm/anything/chat/completions", json=body).status_code == 404  # no secret set
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)
    assert client.post("/voice/llm/wrong/chat/completions", json=body).status_code == 404
    assert client.post(f"/voice/llm/{SECRET}/v1/chat/completions", json=body).status_code == 200


def test_turn_goes_to_the_real_brain_and_streams_its_reply(client, monkeypatch):
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)
    said = ask(client, "hello there")
    assert "Echo mode" in said and "hello there" in said  # the team's Brain, in echo mode


class AskingBrain:
    """A fake Brain whose tool asks Yes/No, like delete_file does."""

    def handle(self, text, session, screenshot_png=None):
        ok = session.confirm("Delete old draft?")
        session.emit({"type": "reply", "text": "Deleted." if ok else "Cancelled."})


@pytest.fixture
def asking(client, monkeypatch):
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)
    duplex.CALL.brain = AskingBrain()
    return client


@pytest.mark.parametrize("answer, result", [("yes please", "Deleted."), ("no", "Cancelled."),
                                            ("Taip", "Deleted."), ("don't do it", "Cancelled.")])
def test_yes_no_by_voice(asking, answer, result):
    question = ask(asking, "delete the old draft")
    assert "Delete old draft?" in question and "yes or no" in question
    assert ask(asking, answer) == result


def test_unclear_answer_asks_again(asking):
    ask(asking, "delete the old draft")
    assert "yes or a no" in ask(asking, "hmm what")
    assert ask(asking, "no") == "Cancelled."


def test_stop_while_busy_turns_the_next_yes_no_into_no(client, monkeypatch):
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)
    gate = threading.Event()

    class SlowBrain:
        def handle(self, text, session, screenshot_png=None):
            gate.wait(5)                       # still working when the user says "stop"
            ok = session.confirm("Send the email?")
            session.emit({"type": "reply", "text": "Sent." if ok else "Not sent."})

    call = duplex.CALL
    call.brain = SlowBrain()
    result = {}
    t = threading.Thread(target=lambda: result.setdefault("first", call.turn("send the email")))
    t.start()
    time.sleep(0.2)
    assert "stopping" in call.turn("stop!").lower()
    gate.set()
    t.join(5)
    assert result["first"] == "Not sent."     # the confirm was answered No automatically


def test_sent_file_shows_on_the_call_page(client, monkeypatch):
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)

    class FileBrain:
        def handle(self, text, session, screenshot_png=None):
            session.emit({"type": "file", "name": "cv.pdf", "url": "/files/abc"})
            session.emit({"type": "reply", "text": "Sent your CV."})

    duplex.CALL.brain = FileBrain()
    said = ask(client, "send me my cv")
    assert said.startswith("Sent your CV.") and "download link" in said
    files = client.get("/voice/call/files", params={"token": duplex.CALL.token}).json()["files"]
    assert files == [{"name": "cv.pdf", "url": "/files/abc"}]
    assert client.get("/voice/call/files", params={"token": "guess"}).json()["files"] == []


def test_brain_crash_is_spoken_not_silence(client, monkeypatch):
    with_settings(monkeypatch, HOMECALL_AGENT_SECRET=SECRET)

    class Broken:
        def handle(self, *a, **k):
            raise RuntimeError("boom")
    duplex.CALL.brain = Broken()
    assert "went wrong" in ask(client, "hi")


@pytest.mark.parametrize("text, expected", [("yes", True), ("Yeah, go ahead", True), ("no", False),
                                            ("stop", False), ("ne", False), ("banana", None)])
def test_yes_or_no(text, expected):
    assert duplex.yes_or_no(text) is expected


# ------------------------------------------------------------------ call page -----

def test_call_page_is_served(client):
    r = client.get("/voice/call")
    assert r.status_code == 200 and "Call my PC" in r.text and "@elevenlabs/client@" in r.text


def test_call_start_needs_the_pairing_code(client):
    assert client.post("/voice/call/start", json={"code": "000000" if server.PAIR_CODE != "000000" else "111111"}
                       ).status_code == 403


def test_call_start_locks_after_5_wrong_codes(client):
    wrong = "000000" if server.PAIR_CODE != "000000" else "111111"
    for _ in range(5):
        client.post("/voice/call/start", json={"code": wrong})
    assert client.post("/voice/call/start", json={"code": server.PAIR_CODE}).status_code == 429


def test_call_start_without_setup_says_so(client):
    r = client.post("/voice/call/start", json={"code": server.PAIR_CODE})
    assert r.status_code == 501 and "DUPLEX.md" in r.json()["detail"]


def test_call_start_returns_signed_url(client, monkeypatch):
    monkeypatch.setattr(eleven, "signed_url", lambda: "wss://example/signed")
    r = client.post("/voice/call/start", json={"code": server.PAIR_CODE})
    assert r.status_code == 200 and r.json()["signed_url"] == "wss://example/signed"
    assert r.json()["token"] == duplex.CALL.token
