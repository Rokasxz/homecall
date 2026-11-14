"""TEST: can the PC answer a Telegram call, share its screen, hear you and talk back?  (Owner: lead)

The 2-hour test before building "call your PC in Telegram". It runs the PC's own
Telegram account ("Home PC") and, when YOU call it from your phone:

  1. answers (only calls from your own account, TG_ALLOWED in .env)
  2. shares this computer's screen as the call's video
  3. plays a short chime        -> sound PC -> phone works
  4. echoes your voice 1 s late -> the PC hears you, and sound flows both ways
  5. prints PASS / FAIL for each step, and saves the first 15 s of your voice to
     experiments/telegram_call/heard.wav

Run it (Terminal, from the homecall folder; the first time it asks for the Home PC
account's phone number and the code Telegram sends, which only you type):

    .venv-tgcall/bin/python experiments/telegram_call/call_test.py

Needs in .env (private): TG_API_ID, TG_API_HASH (my.telegram.org, logged in with the
Home PC account) and TG_ALLOWED (YOUR Telegram @username or numeric id, the only caller it
answers; not the Home PC account's own).
"""
import asyncio
import inspect
import logging
import math
import os
import struct
import sys
import time
import traceback
import wave
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RATE, CHANNELS = 48000, 2                     # what the call library sends and expects
FRAME_BYTES = RATE * 2 * CHANNELS // 100      # 10 ms of 16-bit stereo = 1920 bytes
ECHO_DELAY_FRAMES = 100                       # 1 s
results: dict[str, str] = {}
LOG = HERE / "debug.log"   # every step of the call library, to find bugs (private, gitignored)
logging.basicConfig(filename=str(LOG), filemode="w", level=logging.DEBUG,
                    format="%(asctime)s %(name)s %(levelname)s %(message)s")
for noisy in ("pyrogram.session", "pyrogram.connection", "pyrogram.dispatcher", "asyncio"):
    logging.getLogger(noisy).setLevel(logging.WARNING)
log = logging.getLogger("call_test")


def env(name: str) -> str:
    value = os.environ.get(name, "")
    if not value and (ROOT / ".env").exists():
        for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
            if line.startswith(name + "="):
                value = line.split("=", 1)[1].strip().strip('"').strip("'")
    return value


def report(step: str, ok: bool, detail: str = "") -> None:
    if results.get(step) == "PASS":
        return
    results[step] = "PASS" if ok else "FAIL"
    print(f"  {'PASS' if ok else 'FAIL'}  {step}" + (f"  ->  {detail}" if detail else ""), flush=True)
    log.info("%s %s %s", results[step], step, detail)
    if not ok:
        log.error(traceback.format_exc())


async def done(x):
    """The library's calls may or may not be async: wait for them either way."""
    return await x if inspect.isawaitable(x) else x


def chime() -> list[bytes]:
    """Two short tones (like a doorbell), as 10 ms stereo frames."""
    frames, buf = [], b""
    for freq, secs in ((880, 0.25), (0, 0.05), (660, 0.35)):
        for i in range(int(RATE * secs)):
            v = int(9000 * math.sin(2 * math.pi * freq * i / RATE)) if freq else 0
            buf += struct.pack("<hh", v, v)
            if len(buf) >= FRAME_BYTES:
                frames.append(buf[:FRAME_BYTES]); buf = buf[FRAME_BYTES:]
    return frames


def level(pcm: bytes) -> int:
    """Loudness 0-100 of a 16-bit frame, to show that the PC hears you."""
    n = len(pcm) // 2
    if not n:
        return 0
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    return min(100, int(math.sqrt(sum(s * s for s in samples[::8]) / max(1, n // 8)) / 80))


async def main() -> None:
    from pyrogram import Client
    from pyrogram import filters as pf
    from pytgcalls import MediaDevices, PyTgCalls, filters
    from pytgcalls.types import (AudioQuality, ChatUpdate, Device, Direction, ExternalMedia, MediaStream,
                                 RecordStream, StreamFrames, VideoQuality)
    from pytgcalls.types.raw import AudioParameters

    api_id, api_hash, allowed = env("TG_API_ID"), env("TG_API_HASH"), env("TG_ALLOWED").lstrip("@")
    if not (api_id and api_hash and allowed):
        sys.exit("Missing in .env: TG_API_ID, TG_API_HASH and TG_ALLOWED (see the top of this file).")

    # Pyrogram (the call library's own version): it follows Telegram's switch of 1:1 calls to the new
    # conference-call format. With Telethon the library took that switch for "declined" and hung up.
    client = Client("homepc_pyrogram", api_id=int(api_id), api_hash=api_hash, workdir=str(HERE))
    await client.start()  # first time: asks for the phone number and the login code (you type them)
    me = await client.get_me()
    owner_id = int(allowed) if allowed.isdigit() else (await client.get_users(allowed)).id
    if owner_id == me.id:
        sys.exit(f"TG_ALLOWED is this PC's OWN account (@{me.username}). Put the account you call FROM in .env.")
    print(f"\nHome PC account: {me.first_name} (@{me.username or '-'}). Answers calls only from {allowed}.")
    calls = PyTgCalls(client)
    await done(calls.start())

    screens = MediaDevices.screen_devices()
    if not screens:
        sys.exit("No screen found to share (Screen Recording permission for Terminal?).")
    chime_frames = chime()
    out_queue: deque[bytes] = deque()   # what we send: chime first, then your voice 1 s late
    heard: list[bytes] = []
    state = {"chat": None, "heard_frames": 0, "sent_frames": 0, "last_level": 0.0}

    @calls.on_update(filters.chat_update(ChatUpdate.Status.INCOMING_CALL))
    async def incoming(_, update: ChatUpdate) -> None:
        if update.chat_id != owner_id:
            try:
                who = await client.get_users(update.chat_id)
                who = f"{who.first_name} (@{who.username or '-'})"
            except Exception:  # noqa: BLE001
                who = "unknown"
            print(f"  (ignored a call from someone else: {who}, id {update.chat_id}. "
                  f"If that's you, put TG_ALLOWED={update.chat_id} in .env)")
            return
        print("\nYour call is coming in...")
        await connect(update.chat_id, "1. call answered")

    async def connect(chat_id: int, step: str) -> None:
        """Answer (incoming) or place (outgoing) the call with the screen as video and our own sound."""
        stream = MediaStream(screens[0], audio_parameters=AudioParameters(bitrate=RATE, channels=CHANNELS),
                             video_parameters=VideoQuality.HD_720p, audio_path=ExternalMedia.AUDIO)
        try:
            await done(calls.play(chat_id, stream))
            report(step, True)
            report("2. screen shared as the call's video", True, "look at your phone: you should see this screen")
        except Exception as e:  # noqa: BLE001
            report(step, False, f"{type(e).__name__}: {e}  (details: {LOG.name})")
            return
        try:
            await done(calls.record(chat_id, RecordStream(True, AudioQuality.HIGH)))
        except Exception as e:  # noqa: BLE001
            report("3. PC hears you", False, f"recording didn't start: {type(e).__name__}: {e}")
        state["chat"] = chat_id
        out_queue.extend(chime_frames)

    @client.on_message(pf.private & pf.user(owner_id) & pf.text)
    async def call_me(_, message) -> None:
        """Other way round: send "call" to the Home PC account in Telegram and it calls YOU."""
        if message.text.strip().lower() in ("call", "call me", "skambink"):
            print("\nYou asked me to call you: calling...")
            await message.reply("Calling you now...")
            await connect(owner_id, "1. PC called you")

    @client.on_raw_update()
    async def raw(_, update, users, chats) -> None:  # the order of Telegram's call events, for debug.log
        name = type(update).__name__
        if "PhoneCall" in name or "GroupCall" in name:
            call = getattr(update, "phone_call", None)
            log.info("RAW %s %s reason=%s", name, type(call).__name__,
                     type(getattr(call, "reason", None)).__name__)

    @calls.on_update(filters.chat_update(ChatUpdate.Status.MIGRATE_TO_CONFERENCE_CALL))
    async def moved(_, update: ChatUpdate) -> None:
        print("  (Telegram moved the call to its new conference format: following it)", flush=True)

    @calls.on_update(filters.stream_frame(Direction.INCOMING, Device.MICROPHONE))
    async def your_voice(_, update: StreamFrames) -> None:
        for f in update.frames:
            state["heard_frames"] += 1
            out_queue.append(f.frame)                     # echo back (sender keeps it 1 s behind)
            if len(heard) < 1500:                         # first 15 s, for heard.wav
                heard.append(f.frame)
            lvl = level(f.frame)
            if lvl > 5 and time.time() - state["last_level"] > 1:
                state["last_level"] = time.time()
                print(f"  hearing you: {'#' * (lvl // 5)}", flush=True)
                report("3. PC hears you", True, "your voice arrives on the PC")

    @calls.on_update(filters.chat_update(ChatUpdate.Status.DISCARDED_CALL))
    async def hung_up(_, update: ChatUpdate) -> None:
        if update.chat_id == state["chat"]:
            print("\nCall ended.")
            state["chat"] = None

    async def sender() -> None:
        """Send one 10 ms frame every 10 ms: the chime, then your own voice 1 s late."""
        next_t = time.monotonic()
        while True:
            next_t += 0.01
            await asyncio.sleep(max(0, next_t - time.monotonic()))
            chat = state["chat"]
            if chat is None or not out_queue:
                continue
            if state["sent_frames"] >= len(chime_frames) and len(out_queue) < ECHO_DELAY_FRAMES:
                continue  # keep the echo 1 s behind
            frame = out_queue.popleft()
            frame = (frame + b"\0" * FRAME_BYTES)[:FRAME_BYTES]
            try:
                await done(calls.send_frame(chat, Device.MICROPHONE, frame))
                state["sent_frames"] += 1
                if state["sent_frames"] == 50:
                    report("4. PC sends sound", True, "you should hear a chime, then yourself 1 s late")
            except Exception as e:  # noqa: BLE001
                report("4. PC sends sound", False, f"{type(e).__name__}: {e}")

    asyncio.create_task(sender())
    print("Ready. From your phone, call this Telegram account, OR send it the message: call")
    print("(then it calls you). Ctrl+C here stops the test.\n")
    try:
        await asyncio.Event().wait()
    finally:
        if heard:
            with wave.open(str(HERE / "heard.wav"), "wb") as w:
                w.setnchannels(CHANNELS); w.setsampwidth(2); w.setframerate(RATE)
                w.writeframes(b"".join(heard))
            print(f"\nSaved what the PC heard: {HERE / 'heard.wav'}")
        print("\nResults:", results or "no call yet")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nStopped. Results:", results or "no call yet")
