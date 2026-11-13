"""One phone call = one Session.  (Owner: Server & connection)

The server creates a Session when a phone connects. The Brain and the Hands
(tools) use it to talk back to the phone. Tools run in a worker thread, so
every method here is safe to call from any thread.

    session.status("Looking for your CV...")   # small text under the screen
    session.emit({"type": "reply", "text": "Found it."})  # any message from the contract
    if session.confirm("Delete report.docx?"): ...  # waits for Yes/No on the phone
"""
import asyncio
import threading
import uuid


class Session:
    def __init__(self, loop: asyncio.AbstractEventLoop, outgoing: asyncio.Queue):
        self._loop = loop
        self._outgoing = outgoing          # the server sends everything in this queue to the phone
        self._pending: dict[str, tuple[threading.Event, list]] = {}

    # ---- sending to the phone -------------------------------------------------
    def emit(self, event: dict) -> None:
        """Send one JSON message to the phone (see the contract in CLAUDE.md)."""
        self._loop.call_soon_threadsafe(self._outgoing.put_nowait, event)

    def status(self, text: str) -> None:
        self.emit({"type": "status", "text": text})

    # ---- asking the phone a yes/no question -----------------------------------
    def confirm(self, question: str, timeout: float = 60) -> bool:
        """Ask the phone 'Yes/No?' and wait for the answer. No answer = No."""
        cid = uuid.uuid4().hex[:8]
        done, box = threading.Event(), [False]
        self._pending[cid] = (done, box)
        self.emit({"type": "confirm", "id": cid, "text": question})
        answered = done.wait(timeout)
        self._pending.pop(cid, None)
        return box[0] if answered else False

    def answer_confirm(self, cid: str, ok: bool) -> None:
        """Called by the server when the phone taps Yes or No."""
        pending = self._pending.get(cid)
        if pending:
            pending[1][0] = bool(ok)
            pending[0].set()
