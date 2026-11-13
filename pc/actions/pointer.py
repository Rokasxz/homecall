"""Clicking on the screen.  (Owner: Hands)

The AI sees a screenshot of the MAIN screen, shrunk to at most 1280 px wide
(pc/screen.py, capture_png). It says where to click in THAT picture, and
click_at scales the point up to the real screen, e.g. on a 2880x1800 screen
the picture is 1280x800, so (100, 100) in the picture is (225, 225) on screen.
"""
import inspect

import pc.actions as actions  # for actions.current_session

DEFAULT_SHOT_WIDTH = 1280


def _session():
    return actions.current_session


def _shot_width() -> int:
    """The width the AI's screenshot is shrunk to, read from pc/screen.py so we stay in sync."""
    try:
        from pc import screen
        return int(inspect.signature(screen.capture_png).parameters["max_width"].default)
    except Exception:  # noqa: BLE001
        return DEFAULT_SHOT_WIDTH


def _main_screen() -> tuple[int, int, int, int]:
    """left, top, width, height of the main screen in real pixels (the same screen pc/screen.py captures)."""
    try:
        import mss
        maker = getattr(mss, "MSS", None) or mss.mss
        with maker() as sct:
            m = sct.monitors[1]
            return m["left"], m["top"], m["width"], m["height"]
    except Exception:  # noqa: BLE001
        import pyautogui
        w, h = pyautogui.size()
        return 0, 0, int(w), int(h)


def picture_size(screen_w: int, screen_h: int) -> tuple[int, int]:
    """Size of the screenshot the AI sees for a screen of this size (same maths as pc/screen.py)."""
    max_w = _shot_width()
    if screen_w > max_w:
        return max_w, int(screen_h * max_w / screen_w)
    return screen_w, screen_h


def to_screen(x: int, y: int) -> tuple[int, int] | None:
    """Turn a point in the AI's screenshot into a point on the real screen, or None if it's outside."""
    left, top, w, h = _main_screen()
    pic_w, pic_h = picture_size(w, h)
    if not (0 <= x < pic_w and 0 <= y < pic_h):
        return None
    return left + round(x * w / pic_w), top + round(y * h / pic_h)


def click_at(x: int, y: int, double: bool = False) -> str:
    """Click with the mouse at a point in the screenshot you were given (look at it first, aim at the middle of the button or link).

    Args:
        x: Pixels from the LEFT edge of the screenshot (not of the real screen).
        y: Pixels from the TOP edge of the screenshot.
        double: True for a double-click (e.g. to open a file on the desktop). Default False.
    """
    try:
        x, y = int(x), int(y)
    except (TypeError, ValueError):
        return "Error: x and y must be whole numbers (pixels in the screenshot)."
    left, top, w, h = _main_screen()
    pic_w, pic_h = picture_size(w, h)
    point = to_screen(x, y)
    if point is None:
        return f"Error: ({x}, {y}) is outside the screenshot, which is {pic_w} x {pic_h} pixels."
    real_x, real_y = point
    what = "Double-clicking" if double else "Clicking"
    if _session():
        _session().status(f"{what} on the screen")
    try:
        import pyautogui
        pyautogui.click(real_x, real_y, clicks=2 if double else 1, interval=0.1)
    except Exception as e:  # noqa: BLE001  (e.g. pyautogui's fail-safe when aiming at a screen corner)
        return f"Error clicking: {e}"
    return (f"{'Double-clicked' if double else 'Clicked'} at ({x}, {y}) in the screenshot "
            f"(= {real_x}, {real_y} on the {w}x{h} screen). Look at the next screenshot to see what happened.")


TOOLS = [click_at]
