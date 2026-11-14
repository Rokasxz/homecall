"""Who may use the Home PC in Telegram.  (Owner: lead)

Pairing: the PC window shows a Telegram QR code. It opens the Home PC chat with "connect <code>"
already typed (the 6-digit pairing code of this start). You tap Send, the Home PC checks the code
and from then on answers that account, also after a restart.

Shared by the Telegram part (pc/telegram/home_pc.py) and the server (the PC window), so no
Telegram libraries here. Both files are gitignored:
  people.json  the accounts paired with the QR code (kept between starts)
  live.json    the Home PC account's name and who may use it; rewritten every 20 s while the
               Telegram part runs, so the PC window knows it is on
"""
import hmac
import json
import os
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
PEOPLE = HERE / "people.json"
LIVE = HERE / "live.json"
LIVE_FRESH = 60          # live.json older than this: the Telegram part isn't running
PAIR_WORDS = ("connect", "pair", "code")


def _read(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _write(path: Path, data: dict) -> None:
    """All at once (a half-written file is never read)."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def is_pairing_code(text: str, code: str) -> bool:
    """True for exactly the code: "connect 731676", "731676", "731 676".

    A message full of numbers doesn't count, so nobody can try many codes in one message.
    """
    if not code or not text:
        return False
    words = text.strip().lower().split()
    if words and words[0] in PAIR_WORDS:
        words = words[1:]
    return hmac.compare_digest("".join(words).replace("-", ""), code)


def looks_like_a_code(text: str) -> bool:
    """Someone trying a code (counted as a try when wrong), not just saying hello."""
    return any(c.isdigit() for c in text or "")


def paired(path: Path | None = None) -> dict[int, dict]:
    """{telegram id: {"id", "name", "username", "since"}} of everyone paired with the QR code."""
    out = {}
    for p in _read(path or PEOPLE).get("people", []):
        if isinstance(p, dict) and str(p.get("id", "")).isdigit():
            out[int(p["id"])] = p
    return out


def add(uid: int, name: str, username: str = "", path: Path | None = None) -> None:
    path = path or PEOPLE
    people = paired(path)
    people[uid] = {"id": uid, "name": name or "?", "username": username or "",
                   "since": time.strftime("%Y-%m-%d %H:%M")}
    _write(path, {"people": list(people.values())})


def remove(uid: int, path: Path | None = None, live_path: Path | None = None) -> bool:
    """Forget a paired account (the PC window's Remove button). False if it wasn't paired."""
    path, live_path = path or PEOPLE, live_path or LIVE
    people = paired(path)
    if uid not in people:
        return False
    del people[uid]
    _write(path, {"people": list(people.values())})
    data = _read(live_path)  # the PC window shows it at once, without waiting for the next refresh
    if data:
        data["people"] = [p for p in data.get("people", []) if p.get("id") != uid]
        _write(live_path, data)
    return True


def write_live(name: str, username: str, people: list[dict], path: Path | None = None) -> None:
    """people: [{"id", "name", "username", "paired": True if it can be removed in the PC window}]"""
    _write(path or LIVE, {"name": name, "username": username, "people": people, "seen": time.time()})


def live(path: Path | None = None) -> dict | None:
    """What the PC window shows about Telegram, or None when the Telegram part isn't running."""
    data = _read(path or LIVE)
    if not data or time.time() - float(data.get("seen") or 0) > LIVE_FRESH:
        return None
    return {"name": data.get("name", ""), "username": data.get("username", ""),
            "people": [p for p in data.get("people", []) if isinstance(p, dict)]}


class Guard:
    """Stops guessing: 5 wrong codes and that account is ignored; 20 wrong codes in all and
    pairing is off until HomeCall starts again (with a new code)."""
    PER_PERSON = 5
    IN_ALL = 20

    def __init__(self) -> None:
        self.wrong: dict[int, int] = {}
        self.total = 0

    def blocked(self, uid: int) -> bool:
        return self.total >= self.IN_ALL or self.wrong.get(uid, 0) >= self.PER_PERSON

    def miss(self, uid: int) -> int:
        """Count a wrong code. Returns how many tries that account has left."""
        self.wrong[uid] = self.wrong.get(uid, 0) + 1
        self.total += 1
        return 0 if self.total >= self.IN_ALL else max(0, self.PER_PERSON - self.wrong[uid])
