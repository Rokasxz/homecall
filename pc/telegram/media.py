"""Screen pictures and sound for the Telegram call.  (Owner: lead)

Telegram call: 48 kHz, 16-bit, stereo, in 10 ms pieces; video as I420 (yuv420p) pictures.
ElevenLabs agent: 16 kHz (usually), 16-bit, mono.
"""
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
CALL_RATE, CALL_CHANNELS = 48000, 2
CALL_FRAME_BYTES = CALL_RATE * 2 * CALL_CHANNELS // 100   # 10 ms = 1920 bytes
SILENCE = b"\0" * CALL_FRAME_BYTES


class ScreenVideo:
    """The screen as call video. The pictures come from the HomeCall server (its screen door for
    voice calls), so only ONE program takes screenshots: on a Mac, two programs capturing at the
    same time can lock up screenshots for everyone."""

    def __init__(self, fetch_jpeg, width: int = 720) -> None:
        self._fetch = fetch_jpeg               # () -> JPEG bytes of the screen
        w, h = self._picture().size
        self.width = min(width, w) // 2 * 2    # smaller video = less upload, fewer frozen pictures
        self.height = int(self.width * h / w) // 2 * 2

    def _picture(self):
        import io
        from PIL import Image
        return Image.open(io.BytesIO(self._fetch())).convert("RGB")

    def frame(self) -> bytes:
        """One picture as I420 (yuv420p), the raw format the call engine takes."""
        from PIL import Image
        img = self._picture()
        if img.size != (self.width, self.height):
            img = img.resize((self.width, self.height), Image.BILINEAR)
        y, cb, cr = img.convert("YCbCr").split()
        half = (self.width // 2, self.height // 2)
        return y.tobytes() + cb.resize(half, Image.BILINEAR).tobytes() + cr.resize(half, Image.BILINEAR).tobytes()


def _resample(mono: np.ndarray, rate_in: int, rate_out: int) -> np.ndarray:
    if rate_in == rate_out or mono.size == 0:
        return mono
    if rate_in % rate_out == 0:  # e.g. 48000 -> 16000: average groups of 3 (also smooths)
        step = rate_in // rate_out
        n = mono.size // step * step
        return mono[:n].reshape(-1, step).mean(axis=1)
    n_out = max(1, int(round(mono.size * rate_out / rate_in)))
    return np.interp(np.linspace(0, mono.size - 1, n_out), np.arange(mono.size), mono)


def call_to_agent(pcm: bytes, rate_out: int = 16000) -> bytes:
    """Your voice from the call (48 kHz stereo) -> what the agent takes (mono, usually 16 kHz)."""
    a = np.frombuffer(pcm[: len(pcm) // 4 * 4], dtype="<i2").astype(np.float32)
    mono = a.reshape(-1, 2).mean(axis=1)
    return np.clip(_resample(mono, CALL_RATE, rate_out), -32768, 32767).astype("<i2").tobytes()


def agent_to_call(pcm: bytes, rate_in: int = 16000, carry: bytes = b"") -> tuple[list[bytes], bytes]:
    """The agent's voice (mono) -> 10 ms call frames (48 kHz stereo), plus what's left over (less
    than one frame), to put in front of the next piece instead of padding it with silence (clicks)."""
    mono = np.frombuffer(pcm[: len(pcm) // 2 * 2], dtype="<i2").astype(np.float32)
    up = _resample(mono, rate_in, CALL_RATE)
    stereo = carry + np.clip(np.repeat(up, 2), -32768, 32767).astype("<i2").tobytes()
    full = len(stereo) // CALL_FRAME_BYTES * CALL_FRAME_BYTES
    frames = [stereo[i:i + CALL_FRAME_BYTES] for i in range(0, full, CALL_FRAME_BYTES)]
    return frames, stereo[full:]


def rate_of(audio_format: str, default: int = 16000) -> int:
    """'pcm_16000' -> 16000."""
    try:
        kind, rate = audio_format.split("_", 1)
        return int(rate) if kind == "pcm" else default
    except (ValueError, AttributeError):
        return default
