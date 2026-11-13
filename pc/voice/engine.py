"""Speech in and out.  (Owner: Voice)

The phone's browser has a built-in recognizer and voice, but they're patchy
(iPhone "add to home screen" has no mic at all). This module is the reliable
path: the phone records audio, the PC turns it into text; the PC turns reply
text into audio the phone plays.

Pick a provider and implement the two functions. Ideas:
  - OpenAI: Whisper for transcribe, TTS for speak (needs OPENAI_API_KEY in .env)
  - Local, no key: faster-whisper for transcribe, edge-tts or pyttsx3 for speak
New libraries go in requirements.txt only with the lead's OK (see CLAUDE.md).
"""


def transcribe(audio_bytes: bytes, mime_type: str) -> str:
    """Turn a recording from the phone (webm/ogg/m4a/wav) into text."""
    raise NotImplementedError("Voice: transcribe() is not implemented yet (pc/voice/engine.py)")


def speak(text: str) -> bytes:
    """Turn reply text into audio. Return MP3 bytes."""
    raise NotImplementedError("Voice: speak() is not implemented yet (pc/voice/engine.py)")
