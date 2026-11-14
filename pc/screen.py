"""Screenshots of the PC.  (Owner: Server & connection)

capture_jpeg()  -> small JPEG for the live view on the phone (a few per second)
capture_png()   -> bigger PNG the AI looks at (one per request)

If capturing fails (no permission, no display), both return a grey placeholder
image that says why, so the rest of the app keeps working.
"""
import io
import os
import subprocess
import sys
import tempfile
import threading
import time

from PIL import Image, ImageDraw


# One screenshot at a time. On recent macOS, screen capture goes through a system
# service; two captures at the same moment (live view + the AI's screenshot) can
# make one of them wait until a ~30 s timeout. A lock makes them take turns.
_LOCK = threading.Lock()

# On a Mac, a screenshot from two programs at the same moment can freeze the normal way of
# capturing (it waits forever, for every program). If a capture doesn't finish in 5 s, use
# macOS's own `screencapture` tool for a minute (it keeps working), then try the normal way again.
GRAB_TIMEOUT = 5.0
_stuck_until = 0.0
# HOMECALL_CAPTURE=macos: always use macOS's own tool. Needed while the screen is being recorded
# (QuickTime, Cmd+Shift+5, screencapture -V): a recording freezes the normal way of capturing.
ALWAYS_MACOS_TOOL = sys.platform == "darwin" and os.environ.get("HOMECALL_CAPTURE", "").lower() == "macos"


def _grab_mss() -> Image.Image:
    import mss  # imported here so a missing/broken mss only breaks capture, not the app

    with _LOCK, mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])  # 1 = the main screen (0 = all screens together)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


def _grab_macos_tool() -> Image.Image:
    """macOS's own screenshot tool: slower (~0.2 s) but it works when the normal way is frozen."""
    fd, path = tempfile.mkstemp(suffix=".png", prefix="homecall-shot-")
    os.close(fd)
    try:
        subprocess.run(["screencapture", "-x", "-m", "-t", "png", path], timeout=10, check=True)
        with Image.open(path) as img:
            return img.convert("RGB")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def _grab() -> Image.Image:
    global _stuck_until
    if ALWAYS_MACOS_TOOL or (sys.platform == "darwin" and time.time() < _stuck_until):
        return _grab_macos_tool()
    result: dict = {}

    def work() -> None:
        try:
            result["img"] = _grab_mss()
        except Exception as e:  # noqa: BLE001
            result["error"] = e

    worker = threading.Thread(target=work, daemon=True, name="screenshot")
    worker.start()
    worker.join(GRAB_TIMEOUT)
    if worker.is_alive():  # frozen: don't wait for it (it may never come back)
        _stuck_until = time.time() + 60
        if sys.platform == "darwin":
            return _grab_macos_tool()
        raise TimeoutError(f"screen capture took longer than {GRAB_TIMEOUT:.0f} s")
    if "error" in result:
        raise result["error"]
    return result["img"]


def _placeholder(reason: str) -> Image.Image:
    img = Image.new("RGB", (960, 540), (40, 40, 48))
    d = ImageDraw.Draw(img)
    d.text((30, 30), "HomeCall: screen capture not available", fill=(255, 255, 255))
    d.text((30, 60), reason[:120], fill=(200, 200, 200))
    d.text((30, 90), time.strftime("%H:%M:%S"), fill=(120, 200, 255))
    return img


LAST_ERROR: str | None = None  # why the last capture fell back to the placeholder, or None


def _capture(max_width: int) -> Image.Image:
    global LAST_ERROR
    try:
        img = _grab()
        LAST_ERROR = None
    except Exception as e:  # noqa: BLE001 - any failure -> placeholder
        LAST_ERROR = f"{type(e).__name__}: {e}"
        img = _placeholder(LAST_ERROR)
    if img.width > max_width:
        img = img.resize((max_width, int(img.height * max_width / img.width)))
    return img


def capture_jpeg(max_width: int = 960, quality: int = 55) -> bytes:
    """Small JPEG for the phone's live view."""
    buf = io.BytesIO()
    _capture(max_width).save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def capture_png(max_width: int = 1280) -> bytes:
    """PNG for the AI. 1280 px wide stays well inside the model's image limits."""
    buf = io.BytesIO()
    _capture(max_width).save(buf, "PNG")
    return buf.getvalue()
