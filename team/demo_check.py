#!/usr/bin/env python3
"""Run the demo from demo/DEMO-SCRIPT.md like a phone would, and time every step.  (Owner: lead)

    python team/demo_check.py https://xxxx.trycloudflare.com 123456
    python team/demo_check.py http://localhost:8000 123456          (without the tunnel)
    python team/demo_check.py URL CODE --app Spotify                (step 4 opens Spotify instead of Calculator)

It really talks to the running app (and its real Brain), so step 4 really opens
an app on the PC. Deleting is always answered "No", so nothing is deleted.
Only one phone can be on a call: hang up on your own phone first.
Needs the demo files on the Desktop: python demo/make_demo_files.py --install
"""
import argparse
import asyncio
import json
import ssl
import sys
import time
import urllib.request

import websockets

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, what: str, detail: str = "") -> None:
    RESULTS.append((ok, what))
    print(f"  {'PASS' if ok else 'FAIL'}  {what}" + (f"  ->  {detail}" if detail else ""))


class Call:
    def __init__(self, ws):
        self.ws = ws
        self.frames = 0

    async def say(self, text: str, answer_confirm: bool | None = False, timeout: float = 90):
        """Send what the user says; collect status, cards, confirm questions and the reply."""
        await self.ws.send(json.dumps({"type": "say", "text": text}))
        t0, out = time.time(), {"status": [], "files": [], "confirms": [], "reply": None, "errors": []}
        while time.time() - t0 < timeout:
            m = await asyncio.wait_for(self.ws.recv(), timeout)
            if isinstance(m, bytes):
                self.frames += 1
                continue
            d = json.loads(m)
            kind = d.get("type")
            if kind == "status":
                out["status"].append(d.get("text", ""))
            elif kind == "file":
                out["files"].append((d, time.time() - t0))
            elif kind == "confirm":
                out["confirms"].append(d.get("text", ""))
                if answer_confirm is not None:
                    await self.ws.send(json.dumps({"type": "confirm", "id": d["id"], "ok": answer_confirm}))
            elif kind == "error":
                out["errors"].append(d.get("text", ""))
            elif kind == "reply":
                out["reply"] = d.get("text", "")
                break
        out["seconds"] = time.time() - t0
        return out


def show(step: str, r: dict) -> None:
    tools = [s for s in r["status"] if s and s != "Thinking..."]
    print(f"\n{step}\n  {r['seconds']:.1f}s | status: {tools}\n  reply: {r['reply']}")


async def run(base: str, code: str, app: str) -> None:
    ws_url = base.replace("https://", "wss://").replace("http://", "ws://").rstrip("/") + "/ws"
    print(f"Calling {ws_url} ...")
    t0 = time.time()
    async with websockets.connect(ws_url, max_size=None, open_timeout=20) as ws:
        call = Call(ws)
        await ws.send(json.dumps({"type": "hello", "code": code}))
        welcome = None
        while time.time() - t0 < 20:
            m = await asyncio.wait_for(ws.recv(), 20)
            if isinstance(m, bytes):
                call.frames += 1
                if welcome:
                    break
                continue
            d = json.loads(m)
            if d.get("type") == "error":
                check(False, "call accepted", d.get("text", ""))
                return
            if d.get("type") == "welcome":
                welcome = time.time() - t0
        print("\nStep 1: pairing code")
        check(welcome is not None, "code accepted", f"{welcome:.1f}s" if welcome else "no welcome")
        first_frame = time.time() - t0
        check(call.frames > 0 and first_frame < 5, "live screen arrives within a few seconds", f"{first_frame:.1f}s")

        r = await call.say("What's on my desktop?")
        show("Step 2: \"What's on my desktop?\"", r)
        low = (r["reply"] or "").lower()
        check(all(w in low for w in ("cv", "draft", "notes")), "reply names the CV, the old draft and the notes")
        check(r["seconds"] < 15, "answer in under 15 s", f"{r['seconds']:.1f}s")

        r = await call.say("Find my CV and send it to me.")
        show("Step 3: \"Find my CV and send it to me.\"", r)
        cards = [f for f, _ in r["files"]]
        card_time = r["files"][0][1] if r["files"] else None
        check(bool(cards) and "cv" in cards[0].get("name", "").lower(), "download card for the CV appears",
              cards[0].get("name", "") if cards else "no card")
        if card_time is not None:
            check(card_time < 10, "card in under 10 s", f"{card_time:.1f}s")
        if cards:
            url = base.rstrip("/") + cards[0]["url"]
            try:
                data = urllib.request.urlopen(url, timeout=20, context=ssl.create_default_context()).read()
                check(data[:4] == b"%PDF", "the CV downloads on the phone (it's a real PDF)", f"{len(data)} bytes")
            except Exception as e:  # noqa: BLE001
                check(False, "the CV downloads on the phone", str(e))

        r = await call.say(f"Open {app}.")
        show(f"Step 4: \"Open {app}.\"", r)
        low = (r["reply"] or "").lower()
        check(not any(w in low for w in ("error", "couldn't", "could not", "can't", "cannot", "not installed")),
              f"{app} opens (no error in the reply)")

        r = await call.say("Delete the old draft.", answer_confirm=False)
        show("Step 5: \"Delete the old draft.\" (we tap No)", r)
        check(bool(r["confirms"]), "the phone is asked Yes/No first", r["confirms"][0] if r["confirms"] else "never asked")
        check("cancel" in (r["reply"] or "").lower() or "not deleted" in (r["reply"] or "").lower(),
              "after No: says it's cancelled")

        r = await call.say("What does my notes file say?")
        show("Bonus: \"What does my notes file say?\"", r)
        check(bool(r["reply"]) and len(r["reply"]) > 10, "reads the notes file")

        check(call.frames >= 5, "live screen kept streaming during the call", f"{call.frames} frames")
        await ws.send(json.dumps({"type": "hangup"}))

    total = time.time() - t0
    check(total < 120, "whole demo in about 90 s", f"{total:.0f}s")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("code")
    ap.add_argument("--app", default="Calculator")
    a = ap.parse_args()
    try:
        asyncio.run(run(a.url, a.code, a.app))
    except Exception as e:  # noqa: BLE001
        check(False, "the call itself", f"{type(e).__name__}: {e}")
    passed = sum(ok for ok, _ in RESULTS)
    print(f"\n{passed} passed, {len(RESULTS) - passed} failed.")
    sys.exit(0 if passed == len(RESULTS) else 1)


if __name__ == "__main__":
    main()
