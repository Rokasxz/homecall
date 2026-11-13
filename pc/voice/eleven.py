"""Talking to ElevenLabs over plain HTTPS (no extra library).  (Owner: Voice)

Settings are read from .env EVERY time they're used, so pasting a key into
.env works right away, without restarting the app:
    ELEVENLABS_API_KEY=...        your key (elevenlabs.io -> profile -> API Keys)
    ELEVENLABS_AGENT_ID=...       the duplex agent (see pc/voice/DUPLEX.md)
    ELEVENLABS_VOICE_ID=...       optional: voice for /voice/speak
    HOMECALL_AGENT_SECRET=...     random; only ElevenLabs and this PC know it
"""
import json
import os
import ssl
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

API = "https://api.elevenlabs.io"
ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_VOICE = "JBFqnCBsd6RMkjVDRZzb"  # "George", one of ElevenLabs' default voices
TTS_MODEL = "eleven_multilingual_v2"
STT_MODEL = "scribe_v1"


class NotConfigured(Exception):
    """A setting (e.g. the API key) is missing: the caller answers 501."""


def setting(name: str) -> str:
    """Value from the environment, else from .env (read fresh each time)."""
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env = Path(os.environ.get("HOMECALL_ENV_FILE") or ROOT / ".env")  # tests point this elsewhere
    try:
        for line in env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                if k.strip() == name:
                    return v.strip().strip('"').strip("'")
    except OSError:
        pass
    return ""


def require(name: str) -> str:
    value = setting(name)
    if not value:
        raise NotConfigured(f"{name} is not set in .env")
    return value


def _ssl() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # python.org's Python on a Mac ships without certificates: use the system's.
    if not ctx.get_ca_certs() and Path("/etc/ssl/cert.pem").exists():
        ctx.load_verify_locations("/etc/ssl/cert.pem")
    return ctx


def _request(method: str, path: str, body: bytes | None = None, headers: dict | None = None,
             timeout: float = 30) -> tuple[bytes, str]:
    req = urllib.request.Request(API + path, data=body, method=method,
                                 headers={"xi-api-key": require("ELEVENLABS_API_KEY"), **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl()) as r:
            return r.read(), r.headers.get("content-type", "")
    except urllib.error.HTTPError as e:
        detail = e.read()[:300].decode("utf-8", "replace")
        raise RuntimeError(f"ElevenLabs said {e.code}: {detail}") from None


def text_to_speech(text: str) -> bytes:
    """MP3 bytes of `text` spoken by the configured voice."""
    voice = setting("ELEVENLABS_VOICE_ID") or DEFAULT_VOICE
    body = json.dumps({"text": text[:2000], "model_id": TTS_MODEL}).encode()
    audio, _ = _request("POST", f"/v1/text-to-speech/{urllib.parse.quote(voice)}?output_format=mp3_44100_128",
                        body, {"Content-Type": "application/json", "Accept": "audio/mpeg"})
    return audio


def speech_to_text(audio: bytes, mime_type: str) -> str:
    """Text of a recording (webm/ogg/m4a/wav)."""
    boundary = uuid.uuid4().hex
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/x-m4a": "m4a",
           "audio/wav": "wav", "audio/mpeg": "mp3"}.get((mime_type or "").split(";")[0], "webm")
    parts = [
        f'--{boundary}\r\nContent-Disposition: form-data; name="model_id"\r\n\r\n{STT_MODEL}\r\n'.encode(),
        (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="clip.{ext}"\r\n'
         f'Content-Type: {mime_type or "application/octet-stream"}\r\n\r\n').encode(),
        audio, f"\r\n--{boundary}--\r\n".encode(),
    ]
    raw, _ = _request("POST", "/v1/speech-to-text", b"".join(parts),
                      {"Content-Type": f"multipart/form-data; boundary={boundary}"}, timeout=60)
    return (json.loads(raw).get("text") or "").strip()


def signed_url() -> str:
    """A one-time address the call page uses to start a private conversation with our agent."""
    agent = require("ELEVENLABS_AGENT_ID")
    raw, _ = _request("GET", "/v1/convai/conversation/get-signed-url?agent_id=" + urllib.parse.quote(agent))
    return json.loads(raw)["signed_url"]
