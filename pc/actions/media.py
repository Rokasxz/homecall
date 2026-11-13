"""Media keys: play/pause, next, previous, volume.  (Owner: Hands)

They work like the media buttons on a keyboard: whatever is playing (Spotify,
YouTube in the browser, the Movies app...) reacts, no need to know which app.
"""
import sys

import pc.actions as actions  # for actions.current_session

IS_MAC = sys.platform == "darwin"

# What the user says -> the key pyautogui presses, and how to describe it.
ACTIONS = {
    "playpause": ("playpause", "play/pause"),
    "play": ("playpause", "play/pause"),
    "pause": ("playpause", "play/pause"),
    "play pause": ("playpause", "play/pause"),
    "play/pause": ("playpause", "play/pause"),
    "toggle": ("playpause", "play/pause"),
    "resume": ("playpause", "play/pause"),
    "stop": ("stop", "stop"),
    "next": ("nexttrack", "next track"),
    "next track": ("nexttrack", "next track"),
    "skip": ("nexttrack", "next track"),
    "previous": ("prevtrack", "previous track"),
    "previous track": ("prevtrack", "previous track"),
    "prev": ("prevtrack", "previous track"),
    "back": ("prevtrack", "previous track"),
    "volume up": ("volumeup", "volume up"),
    "up": ("volumeup", "volume up"),
    "louder": ("volumeup", "volume up"),
    "volume down": ("volumedown", "volume down"),
    "down": ("volumedown", "volume down"),
    "quieter": ("volumedown", "volume down"),
    "mute": ("volumemute", "mute/unmute"),
    "unmute": ("volumemute", "mute/unmute"),
}
MAX_TIMES = 20


def _session():
    return actions.current_session


def media_key(action: str, times: int = 1) -> str:
    """Press a media key: play/pause, next, previous, stop, volume up, volume down, or mute. Works for whatever is playing (Spotify, YouTube...).

    Args:
        action: One of: play, pause, next, previous, stop, volume up, volume down, mute.
        times: How many times to press it (volume keys change about 2% per press); 1 to 20. Default 1.
    """
    key_name = " ".join(action.lower().replace("_", " ").replace("-", " ").split())
    if key_name not in ACTIONS:
        return f"Error: unknown media action '{action}'. Use: play, pause, next, previous, stop, volume up, volume down, mute."
    key, label = ACTIONS[key_name]
    try:
        times = int(times)
    except (TypeError, ValueError):
        return "Error: times must be a whole number from 1 to 20."
    if not 1 <= times <= MAX_TIMES:
        return f"Error: times must be from 1 to {MAX_TIMES}."
    if key in ("playpause", "stop", "volumemute"):
        times = 1  # pressing play/pause or mute twice would undo itself
    if IS_MAC:
        return "Error: media keys are not supported on Mac yet. Open the app and use its own controls."
    if _session():
        _session().status(f"Pressing {label}" + (f" x{times}" if times > 1 else ""))
    try:
        import pyautogui
        pyautogui.press(key, presses=times, interval=0.05)
    except Exception as e:  # noqa: BLE001
        return f"Error pressing {label}: {e}"
    return f"Pressed {label}" + (f" {times} times." if times > 1 else ".")


TOOLS = [media_key]
