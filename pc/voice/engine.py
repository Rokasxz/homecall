"""Speech in and out.  (Owner: Voice)

The phone's browser has a built-in recognizer and voice, but they're patchy
(iPhone "add to home screen" has no mic at all). This module is the reliable
path: the phone records audio, the PC turns it into text; the PC turns reply
text into audio the phone plays.

Provider: ElevenLabs (pc/voice/eleven.py), with ELEVENLABS_API_KEY in .env.
Without a key both functions raise NotImplementedError, so /voice/* answers 501
and the phone falls back to the browser's own voice (contract section 6).
"""
from pc.voice import eleven


def transcribe(audio_bytes: bytes, mime_type: str) -> str:
    """Turn a recording from the phone (webm/ogg/m4a/wav) into text."""
    if not eleven.setting("ELEVENLABS_API_KEY"):
        raise NotImplementedError("Voice: no ELEVENLABS_API_KEY in .env, so the phone uses its own recognizer")
    if not audio_bytes:
        return ""
    return eleven.speech_to_text(audio_bytes, mime_type)


def speak(text: str) -> bytes:
    """Turn reply text into audio. Return MP3 bytes."""
    if not eleven.setting("ELEVENLABS_API_KEY"):
        raise NotImplementedError("Voice: no ELEVENLABS_API_KEY in .env, so the phone uses its own voice")
    return eleven.text_to_speech(text)
