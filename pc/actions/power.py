"""Lock and sleep.  (Owner: Hands)

Both ask Yes/No on the phone first: locking is harmless, but sleeping ends the
call and the PC can't be woken from the phone.
"""
import subprocess
import sys

import pc.actions as actions  # for actions.current_session

IS_WIN, IS_MAC = sys.platform == "win32", sys.platform == "darwin"


def _session():
    return actions.current_session


def _confirm(question: str) -> bool:
    return bool(_session()) and _session().confirm(question)


def _run_hidden(cmd: list[str]) -> None:
    """Start a command without flashing a console window."""
    subprocess.Popen(cmd, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


def lock_pc() -> str:
    """Lock the PC screen (like pressing Win+L). Asks the user to confirm on the phone first. The call keeps going."""
    if not _confirm("Lock the PC screen?"):
        return "Cancelled: the user did not confirm."
    if _session():
        _session().status("Locking the screen")
    try:
        if IS_WIN:
            import ctypes
            if not ctypes.windll.user32.LockWorkStation():
                return "Error: Windows refused to lock the screen."
        elif IS_MAC:
            _run_hidden(["osascript", "-e",
                         'tell application "System Events" to keystroke "q" using {control down, command down}'])
        else:
            _run_hidden(["loginctl", "lock-session"])
        return "Locked the PC screen."
    except Exception as e:  # noqa: BLE001
        return f"Error locking the PC: {e}"


def sleep_pc() -> str:
    """Put the PC to sleep. Asks the user to confirm first. Warning: this ENDS the call and the PC cannot be woken from the phone."""
    if not _confirm("Put the PC to sleep? The call will end and you can't wake it from the phone."):
        return "Cancelled: the user did not confirm."
    if _session():
        _session().status("Going to sleep")
    try:
        if IS_WIN:
            _run_hidden(["powershell", "-NoProfile", "-NonInteractive", "-Command",
                         "Start-Sleep -Seconds 2; Add-Type -AssemblyName System.Windows.Forms; "
                         "[System.Windows.Forms.Application]::SetSuspendState('Suspend', $false, $false)"])
        elif IS_MAC:
            _run_hidden(["pmset", "sleepnow"])
        else:
            _run_hidden(["systemctl", "suspend"])
        return "Going to sleep in a few seconds. Wake the PC at home to call again."
    except Exception as e:  # noqa: BLE001
        return f"Error putting the PC to sleep: {e}"


TOOLS = [lock_pc, sleep_pc]
