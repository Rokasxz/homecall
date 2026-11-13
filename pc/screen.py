"""Screenshots of the PC.  (Owner: Server & connection)

capture_jpeg()  -> small JPEG for the live view on the phone (a few per second)
capture_png()   -> bigger PNG the AI looks at (one per request)

If capturing fails (no permission, no display), both return a grey placeholder
image that says why, so the rest of the app keeps working.
"""
import io
import time

from PIL import Image, ImageDraw


def _grab() -> Image.Image:
    import mss  # imported here so a missing/broken mss only breaks capture, not the app

    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])  # 1 = the main screen (0 = all screens together)
        return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")


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
