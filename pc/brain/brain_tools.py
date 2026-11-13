"""The Brain's own two tools, shared by the "api" and "max" modes.  (Owner: Brain)

  look_at_screen  take a fresh screenshot, so the AI checks each step worked
  ask_user        a Yes/No card on the phone, e.g. before sending a message

The Hands' tools (pc.actions.TOOLS) do things on the PC; these two only let the
AI see and ask. Same names and wording in both modes, so the AI behaves the same.
"""
import io

LOOK_NAME = "look_at_screen"
LOOK_DESCRIPTION = (
    "Take a fresh screenshot of the PC screen. Use it after every action that changes the "
    "screen (opening an app, clicking, typing, pressing keys) to check it worked before the "
    "next step. Coordinates for click_at refer to this picture."
)

ASK_NAME = "ask_user"
ASK_DESCRIPTION = (
    "Ask the user a Yes/No question on their phone and wait for the answer. Use it before "
    "sending a message, posting, emailing, or anything you're not sure they want: say exactly "
    "what will happen, e.g. 'Send \"hi\" to Tomas on Discord?'."
)
ASK_SCHEMA = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "The Yes/No question."}},
    "required": ["question"],
}

YES = "The user tapped Yes."
NO = "The user tapped No (or didn't answer): don't do it."
NO_PHONE = "No phone connected: don't do it."


def as_jpeg(png: bytes, quality: int = 70) -> bytes:
    """Re-encode a PNG screenshot as JPEG: about 10x smaller, so faster and cheaper to send."""
    from PIL import Image
    buf = io.BytesIO()
    Image.open(io.BytesIO(png)).convert("RGB").save(buf, "JPEG", quality=quality)
    return buf.getvalue()


def look() -> bytes:
    """A fresh JPEG of the screen, 1280 px wide (the size click_at expects)."""
    from pc import screen
    return screen.capture_jpeg(1280, 70)


def ask(session, question: str) -> str:
    """Show a Yes/No card on the phone and wait. Returns the text the AI gets back."""
    if session is None:
        return NO_PHONE
    return YES if session.confirm(str(question)[:300]) else NO
