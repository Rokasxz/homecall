"""The server on the PC: serves the phone page, streams the screen, relays
messages between the phone and the Brain.  (Owner: Server & connection)

Run from the project root:   python -m pc.server
Then open the printed address on the phone and enter the pairing code.
"""
import asyncio
import os
import pathlib
import secrets

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
FRAME_EVERY = float(os.environ.get("HOMECALL_FPS_DELAY", "0.5"))  # seconds between screen frames
OUTBOX = ROOT / "pc" / "outbox"
OUTBOX.mkdir(exist_ok=True)
PHONE_DIR = ROOT / "phone"

app = FastAPI(title="HomeCall")
app.mount("/static", StaticFiles(directory=PHONE_DIR), name="static")
app.include_router(voice_router)  # /voice/transcribe and /voice/speak (owner: Voice)


@app.get("/")
def phone_page() -> HTMLResponse:
    return HTMLResponse((PHONE_DIR / "index.html").read_text(encoding="utf-8"))


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
    if hello.get("type") != "hello" or str(hello.get("code")) != PAIR_CODE:
        await ws.send_json({"type": "error", "text": "Wrong pairing code."})
        await ws.close()
        return

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
    try:
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
    finally:
        for t in tasks:
            t.cancel()


def main() -> None:
    print("\n  HomeCall is running.")
    print(f"  Pairing code: {PAIR_CODE}")
    print(f"  On this PC:   http://localhost:{PORT}")
    print("  From the phone: use the https address that cloudflared prints, e.g.")
    print(f"      cloudflared tunnel --url http://localhost:{PORT}")
    print("  (The phone's microphone only works over https or localhost.)\n")
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")


if __name__ == "__main__":
    main()
