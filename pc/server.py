"""The server on the PC: serves the phone page, streams the screen, relays
messages between the phone and the Brain.  (Owner: Server & connection)

Run from the project root:   python -m pc.server
Then open the printed address on the phone and enter the pairing code.
"""
import asyncio
import math
import os
import pathlib
import secrets
import threading
import time
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _load_dotenv() -> None:
    """Read KEY=VALUE lines from .env in the project root (no extra library needed)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_dotenv()

from pc import screen  # noqa: E402  (after .env so settings apply)
from pc.brain.agent import Brain  # noqa: E402
from pc.session import Session  # noqa: E402
from pc.voice.routes import router as voice_router  # noqa: E402

PAIR_CODE = os.environ.get("HOMECALL_CODE") or f"{secrets.randbelow(10**6):06d}"
PORT = int(os.environ.get("HOMECALL_PORT", "8000"))
# 127.0.0.1 = only this PC (and the cloudflared tunnel running on it) can connect.
# HOMECALL_HOST=0.0.0.0 lets phones on the same Wi-Fi in directly: only for a quick test at home.
HOST = os.environ.get("HOMECALL_HOST", "127.0.0.1")
FRAME_EVERY = float(os.environ.get("HOMECALL_FPS_DELAY", "0.5"))  # seconds between screen frames
OUTBOX = ROOT / "pc" / "outbox"
OUTBOX.mkdir(exist_ok=True)
PHONE_DIR = ROOT / "phone"
PC_WINDOW = ROOT / "pc" / "pc_window.html"
PUBLIC_URL = os.environ.get("HOMECALL_PUBLIC_URL", "").rstrip("/")  # the tunnel address, from start.py

MAX_WRONG_CODES = 5    # this many wrong pairing codes in a row ...
LOCKOUT_SECONDS = 60   # ... and nobody can pair for this long (guessing 1,000,000 codes takes months)


class Door:
    """Who may start a call. Starts fresh every time the server starts."""

    def __init__(self) -> None:
        self.wrong_codes = 0      # wrong codes in a row
        self.locked_until = 0.0   # time.monotonic() when the lockout ends
        self.in_call = False      # only one phone at a time

    def refuse(self, hello) -> str | None:
        """Check the phone's first message. Returns why it's refused, or None to let it in."""
        now = time.monotonic()
        if now < self.locked_until:
            wait = math.ceil(self.locked_until - now)
            return f"Too many wrong codes. Pairing is locked for {wait} more seconds."
        if not isinstance(hello, dict) or hello.get("type") != "hello" or str(hello.get("code")) != PAIR_CODE:
            self.wrong_codes += 1
            if self.wrong_codes >= MAX_WRONG_CODES:
                self.wrong_codes = 0
                self.locked_until = now + LOCKOUT_SECONDS
                return (f"Wrong pairing code, {MAX_WRONG_CODES} times in a row. "
                        f"Pairing is locked for {LOCKOUT_SECONDS} seconds.")
            return "Wrong pairing code."
        if self.in_call:
            return ("Another phone is already on a call with this PC. Hang up there first "
                    "(if that phone lost its connection, try again in a minute).")
        self.wrong_codes = 0
        return None


door = Door()


def clean_outbox() -> None:
    """Delete the files sent to the phone (pc/outbox/<token>__<name>), so their links stop working."""
    for f in OUTBOX.glob("*__*"):
        try:
            if f.is_file() or f.is_symlink():
                f.unlink()
        except OSError:
            pass  # e.g. Windows while the phone is still downloading it: the next cleanup gets it


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Runs when the server starts: no lockout or call from an earlier run, no old files."""
    global door
    door = Door()
    clean_outbox()
    threading.Thread(target=_check_permissions, daemon=True).start()  # for the PC window
    yield


app = FastAPI(title="HomeCall", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=PHONE_DIR), name="static")
app.include_router(voice_router)  # /voice/transcribe and /voice/speak (owner: Voice)


@app.get("/")
def phone_page() -> HTMLResponse:
    return HTMLResponse((PHONE_DIR / "index.html").read_text(encoding="utf-8"))


# ------------------------------------------------------------- the PC window ---
# http://localhost:8000/pc on THIS computer: QR code, pairing code, permissions.
# It shows the code, so it must never answer through the tunnel or the network.

PERMISSIONS: list[dict] = []


def _check_permissions() -> None:
    from pc import permissions
    PERMISSIONS[:] = permissions.check(ask=False)


def this_pc_only(request: Request) -> None:
    host = (request.headers.get("host") or "").rsplit(":", 1)[0].strip("[]").lower()
    via_tunnel = any(h in request.headers for h in ("cf-connecting-ip", "cf-ray", "x-forwarded-for"))
    client = request.client.host if request.client else ""
    if via_tunnel or host not in ("localhost", "127.0.0.1", "::1") or client not in ("127.0.0.1", "::1"):
        raise HTTPException(status_code=404)


@app.get("/pc")
def pc_window(request: Request) -> HTMLResponse:
    this_pc_only(request)
    return HTMLResponse(PC_WINDOW.read_text(encoding="utf-8"))


@app.get("/pc/info")
def pc_window_info(request: Request, recheck: int = 0) -> dict:
    this_pc_only(request)
    if recheck or not PERMISSIONS:
        _check_permissions()
    brain = os.environ.get("HOMECALL_BRAIN", "").strip().lower()
    brain = brain if brain in ("api", "max", "echo") else ("api" if os.environ.get("ANTHROPIC_API_KEY") else "echo")
    names = {"api": "Claude (team key)", "max": "Claude (your Claude login)", "echo": "off: no key (echo mode)"}
    return {"code": PAIR_CODE, "url": PUBLIC_URL, "in_call": door.in_call, "brain": names[brain],
            "voice": bool(os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_AGENT_ID")),
            "permissions": PERMISSIONS}


@app.post("/pc/fix/{key}")
def pc_window_fix(key: str, request: Request) -> dict:
    this_pc_only(request)
    from pc import permissions
    permissions.open_settings(key)
    return {"ok": True}


@app.get("/health")
def health() -> PlainTextResponse:
    return PlainTextResponse("ok")


@app.get("/files/{token}")
def download(token: str):
    """Files the Hands put in pc/outbox as <token>__<name>."""
    safe = "".join(c for c in token if c.isalnum() or c in "-_")
    for f in OUTBOX.glob(f"{safe}__*"):
        return FileResponse(f, filename=f.name.split("__", 1)[1])
    return PlainTextResponse("Not found", status_code=404)


@app.websocket("/ws")
async def call(ws: WebSocket) -> None:
    await ws.accept()
    hello = await ws.receive_json()
    refused = door.refuse(hello)  # wrong code, locked out, or another phone is on the call
    if refused:
        await ws.send_json({"type": "error", "text": refused})
        await ws.close()
        return
    door.in_call = True  # set before any await, so a second phone can't slip in

    tasks: list[asyncio.Task] = []
    brain = None
    try:
        loop = asyncio.get_running_loop()
        outgoing: asyncio.Queue = asyncio.Queue()
        session = Session(loop, outgoing)
        brain = Brain()
        session.emit({"type": "welcome", "text": "Connected to your PC."})

        async def sender() -> None:  # the ONLY place that writes to the socket
            while True:
                item = await outgoing.get()
                if isinstance(item, bytes):
                    await ws.send_bytes(item)
                else:
                    await ws.send_json(item)

        async def frames() -> None:
            while True:
                outgoing.put_nowait(await asyncio.to_thread(screen.capture_jpeg))
                await asyncio.sleep(FRAME_EVERY)

        tasks = [asyncio.create_task(sender()), asyncio.create_task(frames())]
        while True:
            msg = await ws.receive_json()
            kind = msg.get("type")
            if kind == "say":
                text = (msg.get("text") or "").strip()
                if text:
                    shot = await asyncio.to_thread(screen.capture_png)
                    # Brain runs in a thread so the screen keeps streaming meanwhile.
                    asyncio.create_task(asyncio.to_thread(brain.handle, text, session, shot))
            elif kind == "confirm":
                session.answer_confirm(str(msg.get("id")), bool(msg.get("ok")))
            elif kind == "hangup":
                break
    except WebSocketDisconnect:
        pass
    except RuntimeError as e:  # newer Starlette: reading after the phone already left
        if "connect" not in str(e).lower():
            raise
    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.to_thread(getattr(brain, "close", lambda: None))  # e.g. stop Claude Code (max brain)
        finally:
            clean_outbox()  # files sent during this call can't be downloaded any more
            door.in_call = False  # the next phone may call


def main() -> None:
    print("\n  HomeCall is running.")
    print(f"  Pairing code: {PAIR_CODE}")
    print(f"  On this PC:   http://localhost:{PORT}")
    print("  From the phone: use the https address that cloudflared prints, e.g.")
    print(f"      cloudflared tunnel --url http://localhost:{PORT}")
    print("  (The phone's microphone only works over https or localhost.)")
    if HOST not in ("127.0.0.1", "localhost", "::1"):
        print(f"  WARNING: HOMECALL_HOST={HOST}: devices on this network can reach the server")
        print(f"  directly (http://<this PC's IP>:{PORT}). Only for a quick test at home.")
    print()
    # "info" lists every page load and call attempt (start.py turns it on and writes it to homecall.log).
    uvicorn.run(app, host=HOST, port=PORT, log_level=os.environ.get("HOMECALL_LOG_LEVEL", "warning"))


if __name__ == "__main__":
    main()
