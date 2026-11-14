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
Home PC account) and TG_ALLOWED (your own Telegram @username, the only one it answers).
"""
import asyncio
import inspect
import math
import os
import struct
import sys
import time
import wave
from collections import deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RATE, CHANNELS = 48000, 2                     # what the call library sends and expects
FRAME_BYTES = RATE * 2 * CHANNELS // 100      # 10 ms of 16-bit stereo = 1920 bytes
ECHO_DELAY_FRAMES = 100                       # 1 s
results: dict[str, str] = {}


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
    from telethon import TelegramClient
    from pytgcalls import MediaDevices, PyTgCalls, filters
    from pytgcalls.types import (AudioQuality, ChatUpdate, Device, Direction, ExternalMedia, MediaStream,
                                 RecordStream, StreamFrames, VideoQuality)
    from pytgcalls.types.raw import AudioParameters

    api_id, api_hash, allowed = env("TG_API_ID"), env("TG_API_HASH"), env("TG_ALLOWED").lstrip("@")
    if not (api_id and api_hash and allowed):
        sys.exit("Missing in .env: TG_API_ID, TG_API_HASH and TG_ALLOWED (see the top of this file).")

    client = TelegramClient(str(HERE / "homepc"), int(api_id), api_hash)  # homepc.session: private, gitignored
    await client.start()  # first time: asks for the phone number and the login code (you type them)
    me = await client.get_me()
    owner = await client.get_entity(allowed)
    print(f"\nHome PC account: {me.first_name} (@{me.username or '-'}). Answers calls only from @{allowed}.")
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
        if update.chat_id != owner.id:
            print(f"  (ignored a call from someone else: {update.chat_id})")
            return
        print("\nYour call is coming in...")
        stream = MediaStream(screens[0], audio_parameters=AudioParameters(bitrate=RATE, channels=CHANNELS),
                             video_parameters=VideoQuality.HD_720p, audio_path=ExternalMedia.AUDIO)
        try:
            await done(calls.play(update.chat_id, stream))
            report("1. call answered", True)
            report("2. screen shared as the call's video", True, "look at your phone: you should see this screen")
        except Exception as e:  # noqa: BLE001
            report("1. call answered", False, f"{type(e).__name__}: {e}")
            return
        try:
            await done(calls.record(update.chat_id, RecordStream(True, AudioQuality.HIGH)))
        except Exception as e:  # noqa: BLE001
            report("3. PC hears you", False, f"recording didn't start: {type(e).__name__}: {e}")
        state["chat"] = update.chat_id
        out_queue.extend(chime_frames)

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
    print("Ready. From your phone, call this Telegram account. Ctrl+C here stops the test.\n")
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
