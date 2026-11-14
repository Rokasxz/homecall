"""Call or text your PC in Telegram.  (Owner: lead)

Runs the PC's own Telegram account ("Home PC") next to HomeCall (start.py starts it):

  Text it   It does what you write and answers in the chat. Files (your CV) arrive in the
            chat, Yes/No questions are asked in the chat (answer yes or no). Voice notes work too.
  "call"    Write "call" (or call it): it calls you back as a Telegram call. You see this PC's
            screen and talk to the same AI as in HomeCall's voice call (the ElevenLabs agent).
            You can interrupt it. Write "hang up" (or leave the call) to end.

It is a second "phone" for HomeCall: it talks to the HomeCall server running on this PC
through the same doors as the web page (/ws, /voice/call/start, /voice/call/news,
/voice/call/files, /voice/transcribe), so the Brain, the Hands and the voice agent are the same.
Only YOUR Telegram account (TG_ALLOWED) can use it.

    .venv-tgcall/bin/python -m pc.telegram.home_pc --login   once: log the Home PC account in
    .venv-tgcall/bin/python -m pc.telegram.home_pc           run (start.py does this for you)

Needs: .venv-tgcall with pc/telegram/requirements.txt, and TG_API_ID, TG_API_HASH, TG_ALLOWED
in .env. Telegram calls need UDP to Telegram's call servers: some Wi-Fi (like the venue's)
blocks it; then use the phone's hotspot.
"""
import asyncio
import base64
import inspect
import io
import json
import logging
import os
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections import deque
from pathlib import Path

from pc.telegram.media import (CALL_CHANNELS, CALL_RATE, SILENCE, ScreenVideo, agent_to_call, call_to_agent,
                               rate_of)

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
PORT = int(os.environ.get("HOMECALL_PORT", "8000"))
BASE = f"http://127.0.0.1:{PORT}"
VIDEO_FPS = 10
LINK_IDLE = 180            # close the text link to HomeCall after 3 min without messages
ANSWER_TIMEOUT = 60        # seconds to wait for you to pick up
CALL_WORDS = {"call", "call me", "skambink", "paskambink", "video", "videocall"}
HANGUP_WORDS = {"hang up", "hangup", "stop", "end", "bye", "baik"}
YES = {"yes", "y", "yeah", "yep", "ok", "okay", "sure", "do it", "taip", "gerai", "jo"}
NO = {"no", "n", "nope", "cancel", "don't", "dont", "ne", "nereikia"}

log = logging.getLogger("home_pc")


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def pairing_code() -> str:
    """The code of the HomeCall server running now: from start.py, else from homecall.log."""
    code = os.environ.get("HOMECALL_CODE", "")
    if code:
        return code
    try:
        found = re.findall(r"Pairing code: (\d{6})", (ROOT / "homecall.log").read_text(encoding="utf-8", errors="replace"))
        return found[-1] if found else ""
    except OSError:
        return ""


async def done(x):
    """The call library's methods may or may not be async: wait for them either way."""
    return await x if inspect.isawaitable(x) else x


# ----------------------------------------------------------- HomeCall's doors ---

def _http(method: str, path: str, body: bytes | None = None, headers: dict | None = None, timeout: float = 30):
    req = urllib.request.Request(BASE + path, data=body, method=method, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def post_json(path: str, data: dict) -> dict:
    return json.loads(_http("POST", path, json.dumps(data).encode(), {"Content-Type": "application/json"}))


def get_json(path: str) -> dict:
    return json.loads(_http("GET", path))


def transcribe(audio: bytes, mime: str, code: str) -> str:
    """A voice note -> text, through HomeCall's /voice/transcribe (ElevenLabs)."""
    boundary = uuid.uuid4().hex
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"audio\"; filename=\"note.ogg\"\r\n"
            f"Content-Type: {mime}\r\n\r\n").encode() + audio + f"\r\n--{boundary}--\r\n".encode()
    raw = _http("POST", "/voice/transcribe", body, {"Content-Type": f"multipart/form-data; boundary={boundary}",
                                                    "X-HomeCall-Code": code}, timeout=60)
    return (json.loads(raw).get("text") or "").strip()


class PhoneLink:
    """Text chat: a HomeCall "phone" over /ws (the same messages as the phone page). Opened when you
    write, closed after a few quiet minutes so the web phone can use HomeCall too."""

    def __init__(self, home: "HomePC") -> None:
        self.home = home
        self.ws = None
        self.last = 0.0
        self.reader = None

    async def say(self, text: str) -> None:
        await self._open()
        await self.ws.send(json.dumps({"type": "say", "text": text}))
        self.last = time.time()

    async def confirm(self, confirm_id: str, ok: bool) -> None:
        await self._open()
        await self.ws.send(json.dumps({"type": "confirm", "id": confirm_id, "ok": ok}))
        self.last = time.time()

    async def _open(self) -> None:
        import websockets
        if self.ws is not None and self.ws.state.name == "OPEN":
            return
        for attempt in (1, 2):
            ws = await websockets.connect(f"ws://127.0.0.1:{PORT}/ws", max_size=None, open_timeout=10)
            await ws.send(json.dumps({"type": "hello", "code": self.home.code}))
            while True:  # skip screen pictures until the PC answers the hello
                msg = await asyncio.wait_for(ws.recv(), 10)
                if isinstance(msg, str):
                    break
            first = json.loads(msg)
            if first.get("type") == "welcome":
                self.ws, self.last = ws, time.time()
                self.reader = asyncio.create_task(self._read(ws))
                return
            await ws.close()
            if attempt == 1 and "code" in first.get("text", "").lower():
                self.home.code = pairing_code()  # HomeCall restarted: it has a new code
                continue
            raise RuntimeError(first.get("text", "HomeCall refused the connection"))

    async def _read(self, ws) -> None:
        try:
            async for msg in ws:
                if isinstance(msg, str):
                    self.last = time.time()
                    await self.home.on_phone_message(json.loads(msg))
        except Exception as e:  # noqa: BLE001
            log.info("text link closed: %s", e)
        finally:
            if self.ws is ws:
                self.ws = None

    async def close_when_idle(self) -> None:
        while True:
            await asyncio.sleep(15)
            if self.ws is not None and not self.home.pending and time.time() - self.last > LINK_IDLE:
                ws, self.ws = self.ws, None
                try:
                    await ws.send(json.dumps({"type": "hangup"}))
                    await ws.close()
                except Exception:  # noqa: BLE001
                    pass


# --------------------------------------------------------------------- a call ---

class VoiceCall:
    """One Telegram call: screen as video, your voice <-> the ElevenLabs agent."""

    def __init__(self, signed_url: str, token: str) -> None:
        self.signed_url, self.token = signed_url, token
        self.ws = None                    # the agent's websocket
        self.out: deque[bytes] = deque()  # agent voice, 10 ms call frames
        self.mic = b""                    # your voice, waiting to go to the agent
        self.in_rate = self.out_rate = 16000
        self.joined = asyncio.Event()
        self.tasks: list[asyncio.Task] = []
        self.files_seen: set[str] = set()


class HomePC:
    def __init__(self) -> None:
        self.code = pairing_code()
        self.owner = int(env("TG_ALLOWED") or 0)
        self.client = self.calls = self.video = None
        self.link = PhoneLink(self)
        self.pending: str | None = None  # Yes/No question waiting for your answer (its id)
        self.call: VoiceCall | None = None
        self._typing = 0.0

    async def say(self, text: str) -> None:
        await self.client.send_message(self.owner, text)

    # ------------------------------------------------------------ text chat ---
    async def on_phone_message(self, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "status" and time.time() - self._typing > 4:
            from pyrogram import enums
            self._typing = time.time()
            await self.client.send_chat_action(self.owner, enums.ChatAction.TYPING)
        elif kind == "reply":
            await self.say(msg.get("text") or "Done.")
        elif kind == "confirm":
            self.pending = msg.get("id")
            await self.say(f"❓ {msg.get('text')}\nAnswer yes or no.")
        elif kind == "file":
            await self.send_file(msg.get("name", "file"), msg.get("url", ""))
        elif kind == "error":
            await self.say(f"⚠️ {msg.get('text')}")

    async def send_file(self, name: str, url: str) -> None:
        try:
            data = await asyncio.to_thread(_http, "GET", url, None, None, 120)
        except Exception as e:  # noqa: BLE001
            await self.say(f"⚠️ Couldn't get {name}: {e}")
            return
        doc = io.BytesIO(data)
        doc.name = name
        if name.lower().endswith((".png", ".jpg", ".jpeg")):
            await self.client.send_photo(self.owner, doc, caption=name)
        else:
            await self.client.send_document(self.owner, doc, file_name=name)

    async def on_text(self, text: str) -> None:
        low = text.strip().lower().rstrip("!. ")
        if low in CALL_WORDS:
            await self.start_call()
        elif low in HANGUP_WORDS and self.call:
            await self.end_call("Call ended.")
        elif self.pending:
            ok = low in YES or low.startswith("yes")
            if not ok and not (low in NO or low.startswith("no")):
                await self.say("Answer yes or no, please.")
                return
            cid, self.pending = self.pending, None
            await self.link.confirm(cid, ok)
        else:
            if not self.code:
                await self.say("⚠️ HomeCall isn't running on the PC. Start it first.")
                return
            try:
                await self.link.say(text)
            except Exception as e:  # noqa: BLE001
                await self.say(f"⚠️ Can't reach HomeCall on the PC ({e}). Is it running?")

    async def on_voice_note(self, message) -> None:
        note = await self.client.download_media(message, in_memory=True)
        mime = getattr(message.voice or message.audio, "mime_type", None) or "audio/ogg"
        try:
            text = await asyncio.to_thread(transcribe, bytes(note.getbuffer()), mime, self.code)
        except Exception as e:  # noqa: BLE001
            await self.say(f"⚠️ Couldn't understand the voice note ({e}).")
            return
        if not text:
            await self.say("I didn't catch that. Try again?")
            return
        await self.say(f"\U0001f3a4 {text}")
        await self.on_text(text)

    # ----------------------------------------------------------- voice call ---
    async def start_call(self) -> None:
        from pytgcalls.types import AudioQuality, CallConfig, ExternalMedia, MediaStream, RecordStream
        from pytgcalls.types.raw import AudioParameters, VideoParameters
        if self.call:
            await self.say("We're already on a call.")
            return
        try:
            start = await asyncio.to_thread(post_json, "/voice/call/start", {"code": self.code})
        except urllib.error.HTTPError as e:
            detail = json.loads(e.read() or b"{}").get("detail", e.reason)
            await self.say(f"⚠️ Voice calls aren't ready on the PC: {detail}")
            return
        except Exception as e:  # noqa: BLE001
            await self.say(f"⚠️ Can't reach HomeCall on the PC ({e}). Is it running?")
            return
        call = self.call = VoiceCall(start["signed_url"], start["token"])
        try:  # the screen comes from HomeCall's server (one program taking screenshots, not two)
            self.video = await asyncio.to_thread(
                ScreenVideo, lambda: _http("GET", f"/voice/call/screen?token={call.token}", timeout=15))
        except Exception as e:  # noqa: BLE001
            self.call = None
            await self.say(f"\u26a0\ufe0f Couldn't get the PC's screen ({e}).")
            return
        print(f"Calling you... (screen {self.video.width}x{self.video.height})", flush=True)
        stream = MediaStream(ExternalMedia.VIDEO,
                             audio_parameters=AudioParameters(bitrate=CALL_RATE, channels=CALL_CHANNELS),
                             video_parameters=VideoParameters(width=self.video.width, height=self.video.height,
                                                              frame_rate=VIDEO_FPS),
                             audio_path=ExternalMedia.AUDIO)
        try:
            # Conference-style: how current Telegram apps call (the old 1:1 call gets refused).
            await done(self.calls.play(self.owner, stream, CallConfig(conference=True)))
            await done(self.calls.record(self.owner, RecordStream(True, AudioQuality.HIGH)))
        except Exception as e:  # noqa: BLE001
            log.exception("call failed")
            self.call = None
            await self.say(f"⚠️ Couldn't call you: {type(e).__name__}: {e}")
            return
        call.tasks = [asyncio.create_task(t) for t in (self._sound_out(call), self._video_out(call),
                                                        self._agent(call), self._news(call), self._files(call))]

    async def end_call(self, why: str = "") -> None:
        call, self.call = self.call, None
        if call is None:
            return
        for t in call.tasks:
            t.cancel()
        if call.ws is not None:
            try:
                await call.ws.close()
            except Exception:  # noqa: BLE001
                pass
        try:
            await done(self.calls.leave_call(self.owner, close=True))
        except Exception:  # noqa: BLE001
            pass
        print(f"Call ended. {why}", flush=True)
        if why:
            await self.say(why)

    async def _agent(self, call: VoiceCall) -> None:
        """Talk to the ElevenLabs agent (the same one as the web voice call) once you've picked up."""
        import websockets
        try:
            await asyncio.wait_for(call.joined.wait(), ANSWER_TIMEOUT)
        except asyncio.TimeoutError:
            await self.end_call("You didn't pick up. Write \"call\" to try again.")
            return
        try:
            async with websockets.connect(call.signed_url, max_size=None) as ws:
                call.ws = ws
                await ws.send(json.dumps({"type": "conversation_initiation_client_data"}))
                async for raw in ws:
                    msg = json.loads(raw)
                    kind = msg.get("type")
                    if kind == "conversation_initiation_metadata":
                        meta = msg.get("conversation_initiation_metadata_event", {})
                        call.out_rate = rate_of(meta.get("agent_output_audio_format", "pcm_16000"))
                        call.in_rate = rate_of(meta.get("user_input_audio_format", "pcm_16000"))
                    elif kind == "audio":
                        pcm = base64.b64decode(msg["audio_event"]["audio_base_64"])
                        call.out.extend(agent_to_call(pcm, call.out_rate))
                    elif kind == "interruption":
                        call.out.clear()  # you started talking: stop speaking
                    elif kind == "ping":
                        await ws.send(json.dumps({"type": "pong", "event_id": msg["ping_event"]["event_id"]}))
                    elif kind == "user_transcript":
                        print("  you:", msg["user_transcription_event"]["user_transcript"], flush=True)
                    elif kind == "agent_response":
                        print("  PC: ", msg["agent_response_event"]["agent_response"], flush=True)
        except asyncio.CancelledError:
            raise
        except Exception as e:  # noqa: BLE001
            log.exception("agent connection")
            if self.call is call:
                await self.end_call(f"⚠️ The voice stopped ({type(e).__name__}).")
            return
        if self.call is call:
            await self.end_call("Call ended.")

    async def on_call_audio(self, frames) -> None:
        """Your voice from the call -> the agent, in ~100 ms pieces."""
        call = self.call
        if call is None or call.ws is None:
            return
        for f in frames:
            call.mic += call_to_agent(f.frame, call.in_rate)
        if len(call.mic) >= call.in_rate // 5:  # 100 ms of 16-bit mono
            chunk, call.mic = call.mic, b""
            try:
                await call.ws.send(json.dumps({"user_audio_chunk": base64.b64encode(chunk).decode()}))
            except Exception:  # noqa: BLE001
                pass

    async def _sound_out(self, call: VoiceCall) -> None:
        """One 10 ms frame every 10 ms: the agent's voice, or silence."""
        from pytgcalls.types import Device
        t = time.monotonic()
        while True:
            t += 0.01
            await asyncio.sleep(max(0, t - time.monotonic()))
            frame = call.out.popleft() if call.out else SILENCE
            try:
                await done(self.calls.send_frame(self.owner, Device.MICROPHONE, frame))
            except Exception:  # noqa: BLE001
                await asyncio.sleep(0.2)

    async def _video_out(self, call: VoiceCall) -> None:
        """About 10 screen pictures a second (captured in a thread so the sound never stutters)."""
        from pytgcalls.types import Device, Frame
        while True:
            t0 = time.monotonic()
            try:
                data = await asyncio.to_thread(self.video.frame)
                await done(self.calls.send_frame(self.owner, Device.CAMERA, data,
                                                 Frame.Info(width=self.video.width, height=self.video.height)))
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001
                log.exception("video frame")
                await asyncio.sleep(0.5)
            await asyncio.sleep(max(0, 1 / VIDEO_FPS - (time.monotonic() - t0)))

    async def _news(self, call: VoiceCall) -> None:
        """A long task finished (or a Yes/No question is ready): nudge the agent to say it now."""
        last = 0.0
        while True:
            await asyncio.sleep(1.5)
            if call.ws is None or time.time() - last < 4:
                continue
            try:
                news = (await asyncio.to_thread(get_json, f"/voice/call/news?token={call.token}")).get("news")
                if news:
                    last = time.time()
                    await call.ws.send(json.dumps({"type": "user_message", "text": "(PC update)"}))
            except Exception:  # noqa: BLE001
                pass

    async def _files(self, call: VoiceCall) -> None:
        """Files sent during the call (your CV) arrive in the Telegram chat."""
        while True:
            await asyncio.sleep(2)
            try:
                files = (await asyncio.to_thread(get_json, f"/voice/call/files?token={call.token}")).get("files", [])
            except Exception:  # noqa: BLE001
                continue
            for f in files:
                if f.get("url") and f["url"] not in call.files_seen:
                    call.files_seen.add(f["url"])
                    await self.send_file(f.get("name", "file"), f["url"])

    # ------------------------------------------------------------------- run ---
    async def run(self, login_only: bool = False) -> None:
        from pyrogram import Client
        from pyrogram import filters as pf
        from pytgcalls import PyTgCalls
        from pytgcalls import filters as cf
        from pytgcalls.types import ChatUpdate, Device, Direction, GroupCallParticipant

        api_id, api_hash = env("TG_API_ID"), env("TG_API_HASH")
        if not (api_id and api_hash and self.owner):
            sys.exit("Telegram: TG_API_ID, TG_API_HASH and TG_ALLOWED are missing in .env.")
        self.client = Client("homepc", api_id=int(api_id), api_hash=api_hash, workdir=str(HERE))
        await self.client.start()  # the first time (--login): asks for the phone number and the code
        me = await self.client.get_me()
        if login_only:
            print(f"Logged in as {me.first_name}. HomeCall's start.py now starts the Telegram part by itself.")
            await self.client.stop()
            return
        if me.id == self.owner:
            sys.exit("TG_ALLOWED is the Home PC account itself: put YOUR Telegram account's id in .env.")
        try:
            await self.client.add_contact(self.owner, first_name="Owner")  # Telegram hides calls from strangers
        except Exception:  # noqa: BLE001
            pass
        self.calls = PyTgCalls(self.client)
        await done(self.calls.start())

        owner_only = pf.private & pf.user(self.owner)

        @self.client.on_message(owner_only & pf.text)
        async def text(_, message) -> None:
            await self.on_text(message.text)

        @self.client.on_message(owner_only & (pf.voice | pf.audio))
        async def voice_note(_, message) -> None:
            await self.on_voice_note(message)

        @self.calls.on_update(cf.chat_update(ChatUpdate.Status.INCOMING_CALL))
        async def incoming(_, update) -> None:
            """You called the Home PC: hang that up and call you back the way that works (conference)."""
            if update.chat_id != self.owner:
                return
            try:
                await done(self.calls.leave_call(update.chat_id))
            except Exception:  # noqa: BLE001
                pass
            await asyncio.sleep(1.5)
            await self.start_call()

        @self.calls.on_update(cf.call_participant(GroupCallParticipant.Action.JOINED))
        async def joined(_, update) -> None:
            if self.call and update.participant.user_id == self.owner:
                print("You picked up.", flush=True)
                self.call.joined.set()

        @self.calls.on_update(cf.call_participant(GroupCallParticipant.Action.LEFT))
        async def left(_, update) -> None:
            if self.call and update.participant.user_id == self.owner:
                await self.end_call("Call ended.")

        @self.calls.on_update(cf.chat_update(ChatUpdate.Status.DISCARDED_CALL | ChatUpdate.Status.LEFT_CALL
                                             | ChatUpdate.Status.CLOSED_VOICE_CHAT | ChatUpdate.Status.KICKED))
        async def gone(_, update) -> None:
            if self.call and update.chat_id == self.owner:
                await self.end_call("Call ended.")

        @self.calls.on_update(cf.stream_frame(Direction.INCOMING, Device.MICROPHONE))
        async def your_voice(_, update) -> None:
            if self.call and not self.call.joined.is_set():
                self.call.joined.set()  # we hear you, so you're there
            await self.on_call_audio(update.frames)

        asyncio.create_task(self.link.close_when_idle())
        print(f"Telegram: {me.first_name} (@{me.username or '-'}) is on. Text it, or write \"call\".", flush=True)
        await asyncio.Event().wait()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s",
                        stream=sys.stdout)
    for noisy in ("pyrogram", "pytgcalls", "ntgcalls", "websockets", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        asyncio.run(HomePC().run(login_only="--login" in sys.argv))
    except KeyboardInterrupt:
        print("Telegram part stopped.")


if __name__ == "__main__":
    main()
