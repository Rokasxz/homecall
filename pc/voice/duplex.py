"""Duplex voice call: talk to your PC like a phone call, and interrupt it.  (Owner: Voice)

ElevenLabs runs the CALL (listening while talking, interruptions, a natural voice).
The THINKING stays ours: ElevenLabs' agent is set to "Custom LLM" and sends each
thing you say to this PC; we pass it to the team's Brain (pc/brain, unchanged),
which uses the Hands as usual, and stream its answer back for ElevenLabs to speak.

    phone (/voice/call page) <-- audio --> ElevenLabs agent
                                                |  each turn: POST /voice/llm/<secret>/chat/completions
                                                v
                                   this file -> Brain().handle(...) -> Hands tools

Yes/No by voice: when a tool asks (session.confirm), the agent says the question
and your next words ("yes" / "no") are the answer. Saying "stop" while the PC is
busy makes every further Yes/No a No, so nothing dangerous happens after it.

Setup: pc/voice/DUPLEX.md.
"""
import asyncio
import hmac
import json
import queue
import re
import secrets
import threading
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from pc.voice import eleven

router = APIRouter()
TURN_TIMEOUT = 120         # seconds one answer may take before we give up
CONFIRM_TIMEOUT = 60       # seconds to wait for a spoken yes/no
MAX_WRONG_CODES = 5
LOCK_SECONDS = 60

YES = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "confirm", "confirmed", "go", "taip", "gerai", "jo"}
YES_PHRASES = ("do it", "go ahead", "of course", "please do")
NO = {"no", "nope", "nah", "don't", "dont", "stop", "cancel", "wait", "ne", "nereikia", "sustok", "never"}
NO_PHRASES = ("do not", "don't do", "not now")
STOP_WORDS = {"stop", "wait", "cancel", "halt", "sustok", "palauk"}


def _words(text: str) -> list[str]:
    return re.findall(r"[\w']+", text.lower())


def yes_or_no(text: str) -> bool | None:
    """True for yes, False for no, None if it's neither (then we ask again)."""
    low, words = text.lower(), set(_words(text))
    if words & NO or any(p in low for p in NO_PHRASES):
        return False
    if words & YES or any(p in low for p in YES_PHRASES):
        return True
    return None


def is_stop(text: str) -> bool:
    return bool(set(_words(text)) & STOP_WORDS)


class VoiceSession:
    """Looks like pc.session.Session to the Brain and the Hands, but talks through the call."""

    def __init__(self, call: "VoiceCall"):
        self.call = call

    def emit(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "reply":
            self.call.out.put(("reply", str(event.get("text") or "Done.")))
        elif kind == "file":
            self.call.files.append({"name": event.get("name"), "url": event.get("url")})
            self.call.new_file = True
        # status / error: nothing to say out loud; the reply covers it

    def status(self, text: str) -> None:
        self.emit({"type": "status", "text": text})

    def confirm(self, question: str, timeout: float = CONFIRM_TIMEOUT) -> bool:
        if self.call.stopped:
            return False
        done, box = threading.Event(), [False]
        self.call.pending = (done, box)
        self.call.out.put(("ask", f"{question.rstrip()} Say yes or no."))
        answered = done.wait(timeout)
        self.call.pending = None
        return box[0] if answered else False

    def answer_confirm(self, cid: str, ok: bool) -> None:  # same API as Session; unused here
        pass


class VoiceCall:
    """One voice call: one Brain (so it remembers the conversation), one task at a time."""

    def __init__(self) -> None:
        self.brain = None
        self.out: queue.Queue = queue.Queue()
        self.pending: tuple[threading.Event, list] | None = None
        self.busy = False
        self.stopped = False
        self.files: list[dict] = []
        self.new_file = False
        self.token = secrets.token_urlsafe(16)

    def _work(self, text: str) -> None:
        try:
            if self.brain is None:
                from pc.brain.agent import Brain
                self.brain = Brain()
            try:
                from pc import screen
                shot = screen.capture_png()
            except Exception:  # noqa: BLE001 - no screen is fine, the Brain copes
                shot = None
            self.brain.handle(text, VoiceSession(self), shot)
        except Exception as e:  # noqa: BLE001 - never leave the caller in silence
            self.out.put(("reply", f"Sorry, something went wrong on the PC: {type(e).__name__}."))
        finally:
            self.busy = False

    def turn(self, text: str) -> str:
        """What the user just said -> what the agent should say now (blocking)."""
        text = text.strip()
        if not text:
            return ""
        if self.pending:  # a tool is waiting for a spoken yes/no
            answer = yes_or_no(text)
            if answer is None:
                return "Sorry, was that a yes or a no?"
            done, box = self.pending
            box[0] = answer
            done.set()
            return self._next()
        if self.busy:
            if is_stop(text):
                self.stopped = True
                return "Okay, stopping. I won't do anything else that needs your yes."
            return self._next("About what you asked before: ")
        self.stopped = False
        self.new_file = False
        self.busy = True
        threading.Thread(target=self._work, args=(text,), daemon=True).start()
        return self._next()

    def _next(self, prefix: str = "") -> str:
        try:
            kind, said = self.out.get(timeout=TURN_TIMEOUT)
        except queue.Empty:
            return "Sorry, that's taking too long. Check the screen, or ask me again."
        if kind == "reply" and self.new_file:
            said += " The download link is on your call screen."
            self.new_file = False
        return prefix + said


CALL = VoiceCall()


# --------------------------------------------- the "LLM" ElevenLabs talks to -----

def _last_user_text(body: dict) -> str:
    for m in reversed(body.get("messages") or []):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, list):
                return " ".join(p.get("text", "") for p in c if isinstance(p, dict))
            return str(c or "")
        if m.get("role") == "assistant":
            break  # the agent spoke last: nothing new from the user
    return ""


def _chunk(text: str | None, model: str, cid: str, finish: str | None = None) -> str:
    delta = {"role": "assistant", "content": text} if text is not None else {}
    data = {"id": cid, "object": "chat.completion.chunk", "created": int(time.time()), "model": model,
            "choices": [{"index": 0, "delta": delta, "finish_reason": finish}]}
    return f"data: {json.dumps(data)}\n\n"


def check_secret(secret: str) -> None:
    expected = eleven.setting("HOMECALL_AGENT_SECRET")
    if not expected or not hmac.compare_digest(secret.encode(), expected.encode()):
        raise HTTPException(status_code=404, detail="Not found")


@router.post("/llm/{secret}/chat/completions")
@router.post("/llm/{secret}/v1/chat/completions")
async def chat_completions(secret: str, request: Request):
    """OpenAI-style streaming endpoint (what ElevenLabs' Custom LLM calls). The secret is in the URL."""
    check_secret(secret)
    body = await request.json()
    text, model = _last_user_text(body), str(body.get("model") or "homecall")
    cid = "chatcmpl-" + secrets.token_hex(8)

    async def stream():
        yield _chunk("... ", model, cid)  # ElevenLabs' tip for slower LLMs: a short buffer first
        task = asyncio.create_task(asyncio.to_thread(CALL.turn, text))
        while not task.done():
            await asyncio.wait({task}, timeout=5)
            if not task.done():
                yield ": still working\n\n"  # SSE comment: keeps the connection alive
        yield _chunk(task.result() or "", model, cid)
        yield _chunk(None, model, cid, finish="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


# ----------------------------------------------------------- the call page -----

class _Door:
    wrong = 0
    locked_until = 0.0


def pair_code() -> str:
    """The pairing code the RUNNING app printed.

    `python -m pc.server` runs the server as the module "__main__". Importing
    pc.server from here would load a SECOND copy with its own random code, so look
    at __main__ first."""
    import sys
    main = sys.modules.get("__main__")
    if main is not None and getattr(main, "PAIR_CODE", None):
        return str(main.PAIR_CODE)
    from pc import server  # tests and other launchers: the normal module
    return str(server.PAIR_CODE)


def _check_code(code: str) -> None:
    now = time.monotonic()
    if now < _Door.locked_until:
        raise HTTPException(status_code=429, detail="Too many wrong codes. Wait a minute.")
    if not hmac.compare_digest(str(code).encode(), pair_code().encode()):
        _Door.wrong += 1
        if _Door.wrong >= MAX_WRONG_CODES:
            _Door.wrong, _Door.locked_until = 0, now + LOCK_SECONDS
        raise HTTPException(status_code=403, detail="Wrong pairing code.")
    _Door.wrong = 0


@router.get("/call")
def call_page() -> HTMLResponse:
    return HTMLResponse((Path(__file__).parent / "call.html").read_text(encoding="utf-8"))


@router.post("/call/start")
async def call_start(request: Request):
    """Pairing code -> a one-time ElevenLabs address for a private call with our agent."""
    global CALL
    data = await request.json()
    _check_code(str(data.get("code", "")))
    try:
        url = await asyncio.to_thread(eleven.signed_url)
    except eleven.NotConfigured as e:
        raise HTTPException(status_code=501, detail=f"Voice call not set up yet: {e} (see pc/voice/DUPLEX.md)")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"Couldn't reach ElevenLabs: {e}")
    CALL = VoiceCall()  # a fresh call: new Brain memory, no leftovers
    return {"signed_url": url, "token": CALL.token}


@router.get("/call/files")
def call_files(token: str):
    if not hmac.compare_digest(token.encode(), CALL.token.encode()):
        return JSONResponse({"files": []})
    return {"files": CALL.files}
