"""The demo, end to end, as one test.  Owner: Demo, tests & safety.

Plays demo/DEMO-SCRIPT.md through the REAL server, the REAL Hands tools and the
REAL demo files (demo/desktop/), with a scripted Brain that calls the tools the
way the AI should. If this goes red after a merge, the demo is broken: tell the
team before anyone builds on top of it.

Nothing real is touched: a temporary fake home folder, a fake screen, and app
launches are recorded instead of run. No API key needed.
"""
import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import pc.actions as actions
from pc import server
from pc.actions import basic

DEMO_FILES = Path(__file__).resolve().parent.parent / "demo" / "desktop"
CV, DRAFT, NOTES = "CV_Alex_Demo.pdf", "Old draft - essay.txt", "notes.md"


def _call(name: str, *args):
    """Call a Hands tool by name, the way the Brain does (from pc.actions.TOOLS)."""
    tool = {f.__name__: f for f in actions.TOOLS}[name]
    return tool(*args)


def _paths(found: str) -> list[str]:
    """find_file's text -> the file paths in it (works with old and new output formats)."""
    return [line.strip() for line in found.splitlines() if Path(line.strip()).is_file()]


class ScriptedBrain:
    """Does what a good AI does for each demo request, using the real tools."""

    def handle(self, text, session, screenshot_png=None):
        actions.current_session = session
        t = text.lower()
        if "desktop" in t:
            session.status("list_files")
            reply = "On your Desktop: " + _call("list_files", "Desktop").replace("\n", ", ")
        elif "cv" in t:
            session.status("find_file")
            hits = _paths(_call("find_file", "cv"))
            if not hits:
                reply = "I couldn't find your CV."
            else:
                session.status("send_file_to_phone")
                reply = _call("send_file_to_phone", hits[0])
        elif "spotify" in t:
            reply = _call("open_app", "Spotify")
        elif "delete" in t:
            hits = _paths(_call("find_file", "draft"))
            reply = _call("delete_file", hits[0]) if hits else "No draft found."
        else:
            reply = "?"
        session.emit({"type": "reply", "text": reply})


@pytest.fixture
def demo(monkeypatch, tmp_path):
    home = tmp_path / "home"
    roots = {n: home / n for n in ("Desktop", "Documents", "Downloads", "Pictures")}
    for r in roots.values():
        r.mkdir(parents=True)
    for f in DEMO_FILES.iterdir():
        shutil.copy2(f, roots["Desktop"] / f.name)
    outbox = tmp_path / "outbox"
    outbox.mkdir()
    monkeypatch.setattr(basic, "HOME", home)
    monkeypatch.setattr(basic, "ALLOWED_ROOTS", list(roots.values()))
    if hasattr(basic, "SPECIAL_FOLDERS"):
        monkeypatch.setattr(basic, "SPECIAL_FOLDERS", roots)
    monkeypatch.setattr(basic, "OUTBOX", outbox)
    monkeypatch.setattr(server, "OUTBOX", outbox)

    launched = []
    monkeypatch.setattr(basic.subprocess, "Popen", lambda *a, **k: launched.append(a))
    monkeypatch.setattr(basic.subprocess, "run",
                        lambda *a, **k: launched.append(a) or type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    if hasattr(basic, "_windows_apps"):
        monkeypatch.setattr(basic, "_windows_apps", lambda: {"Spotify": "SpotifyAB.Spotify!App"})

    monkeypatch.setattr(server.screen, "capture_jpeg", lambda *a, **k: b"\xff\xd8demo")
    monkeypatch.setattr(server.screen, "capture_png", lambda *a, **k: b"png")
    monkeypatch.setattr(server, "FRAME_EVERY", 0.05)
    monkeypatch.setattr(server, "Brain", ScriptedBrain)
    with TestClient(server.app) as client:
        yield client, roots["Desktop"], launched


def _until(ws, wanted, limit=500):
    seen = []
    for _ in range(limit):
        m = ws.receive()
        if m.get("text") is None:
            continue
        d = json.loads(m["text"])
        seen.append(d)
        if d["type"] == wanted:
            return d, seen
    raise AssertionError(f"no {wanted}: saw {[s['type'] for s in seen]}")


def test_demo_files_exist():
    for name in (CV, DRAFT, NOTES):
        assert (DEMO_FILES / name).is_file(), f"demo/desktop/{name} missing: run python demo/make_demo_files.py"


def test_the_whole_demo(demo):
    client, desktop, launched = demo
    with client.websocket_connect("/ws") as ws:
        # 1. Pair: the live screen appears.
        ws.send_json({"type": "hello", "code": server.PAIR_CODE})
        welcome, _ = _until(ws, "welcome")
        frames = 0
        while frames < 2:
            if ws.receive().get("bytes"):
                frames += 1

        # 2. "What's on my desktop?"
        ws.send_json({"type": "say", "text": "What's on my desktop?"})
        reply, seen = _until(ws, "reply")
        for name in (CV, DRAFT, NOTES):
            assert name in reply["text"], f"step 2: {name} not mentioned: {reply['text']}"
        assert any(s["type"] == "status" for s in seen), "step 2: no status shown"

        # 3. "Find my CV and send it to me." -> download card -> the PDF downloads.
        ws.send_json({"type": "say", "text": "Find my CV and send it to me."})
        card, seen = _until(ws, "file")
        assert card["name"] == CV
        statuses = [s["text"] for s in seen if s["type"] == "status"]
        assert "find_file" in statuses and "send_file_to_phone" in statuses
        _until(ws, "reply")
        r = client.get(card["url"])
        assert r.status_code == 200 and r.content.startswith(b"%PDF"), "step 3: download failed"

        # 4. "Open Spotify and play something." -> an app launch is requested.
        ws.send_json({"type": "say", "text": "Open Spotify and play something."})
        reply, _ = _until(ws, "reply")
        assert not reply["text"].startswith("Error"), f"step 4: {reply['text']}"
        assert launched, "step 4: nothing was launched"

        # 5. "Delete the old draft." -> Yes/No on the phone -> No -> "Cancelled", file stays.
        ws.send_json({"type": "say", "text": "Delete the old draft."})
        ask, _ = _until(ws, "confirm")
        assert DRAFT in ask["text"]
        ws.send_json({"type": "confirm", "id": ask["id"], "ok": False})
        reply, _ = _until(ws, "reply")
        assert reply["text"].startswith("Cancelled"), f"step 5: {reply['text']}"
        assert (desktop / DRAFT).exists(), "step 5: the draft was deleted after No!"

        ws.send_json({"type": "hangup"})
