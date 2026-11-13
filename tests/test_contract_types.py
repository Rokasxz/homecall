"""Contract guard: every websocket message type in the code must be in CLAUDE.md.  Owner: Demo, tests & safety.

Reads the two tables in CLAUDE.md ("Phone -> PC" and "PC -> Phone") and scans the
real code on both sides:
  - pc/  (Python): every   emit({"type": "x"...})  /  send_json({"type": "x"...})
                   and every message the server reacts to   (kind == "x")
  - phone/ (JS):   every   send({ type: "x" })  /  JSON.stringify({ type: "x" })
                   and every   case "x":   in the message handler
A type that isn't in the right table fails, with the file and line, so a new
message can't sneak in without the team agreeing (CLAUDE.md: "Adding a message
type = add a row here first").
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CONTRACT = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")


def _table(after: str, before: str) -> set[str]:
    start = CONTRACT.index(after)
    end = CONTRACT.index(before, start)
    return set(re.findall(r'"type"\s*:\s*"(\w+)"', CONTRACT[start:end]))


PHONE_TO_PC = _table("Phone -> PC", "PC -> Phone")
PC_TO_PHONE = _table("PC -> Phone", "Adding a message type")

# Python: messages sent to the phone. Only emit()/send_json() count, so the
# Anthropic API's own {"type": "text"/"image"} blocks are ignored.
PY_SEND = re.compile(r'(?:emit|send_json)\(\s*\{\s*["\']type["\']\s*:\s*["\'](\w+)["\']')
PY_HANDLE = re.compile(r'\bkind\s*==\s*["\'](\w+)["\']|\.get\(\s*["\']type["\']\s*\)\s*[!=]=\s*["\'](\w+)["\']')
JS_SEND = re.compile(r'(?:send|stringify)\(\s*\{\s*type\s*:\s*["\'](\w+)["\']')
JS_HANDLE = re.compile(r'\bcase\s+["\'](\w+)["\']\s*:')


def _scan(folder: str, suffix: str, pattern: re.Pattern) -> list[tuple[str, str]]:
    """(type, "file:line") for every match in the folder's source files."""
    found = []
    for path in sorted((ROOT / folder).rglob(f"*{suffix}")):
        if "outbox" in path.parts or "node_modules" in path.parts:
            continue
        for n, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for m in pattern.finditer(line):
                kind = next(g for g in m.groups() if g)
                found.append((kind, f"{path.relative_to(ROOT)}:{n}"))
    return found


def _not_in(found, allowed) -> list[str]:
    return [f"'{k}' at {where}" for k, where in found if k not in allowed]


def test_contract_tables_were_read():
    assert {"hello", "say", "confirm", "hangup"} <= PHONE_TO_PC
    assert {"welcome", "status", "reply", "confirm", "file", "error"} <= PC_TO_PHONE


def test_pc_only_sends_types_from_the_contract():
    bad = _not_in(_scan("pc", ".py", PY_SEND), PC_TO_PHONE)
    assert not bad, "PC sends message types not in CLAUDE.md 'PC -> Phone': " + ", ".join(bad)


def test_phone_only_sends_types_from_the_contract():
    bad = _not_in(_scan("phone", ".js", JS_SEND), PHONE_TO_PC)
    assert not bad, "Phone sends message types not in CLAUDE.md 'Phone -> PC': " + ", ".join(bad)


def _server_handles():
    """Messages from the phone are received only in pc/server.py (helper scripts that
    filter their own fake messages, like try_tools.py, don't count)."""
    return [x for x in _scan("pc", ".py", PY_HANDLE) if x[1].startswith("pc/server.py")]


def test_pc_only_listens_for_types_from_the_contract():
    bad = _not_in(_server_handles(), PHONE_TO_PC)
    assert not bad, "PC expects message types not in CLAUDE.md 'Phone -> PC': " + ", ".join(bad)


def test_phone_only_listens_for_types_from_the_contract():
    bad = _not_in(_scan("phone", ".js", JS_HANDLE), PC_TO_PHONE)
    assert not bad, "Phone expects message types not in CLAUDE.md 'PC -> Phone': " + ", ".join(bad)


def test_phone_handles_every_pc_message():
    """A PC message the phone ignores is silently lost (e.g. a Yes/No nobody sees)."""
    handled = {k for k, _ in _scan("phone", ".js", JS_HANDLE)}
    missing = PC_TO_PHONE - handled
    assert not missing, f"phone/ has no 'case' for: {sorted(missing)}"


def test_pc_handles_every_phone_message():
    handled = {k for k, _ in _server_handles()}
    missing = PHONE_TO_PC - handled
    assert not missing, f"pc/ never reacts to: {sorted(missing)}"


@pytest.mark.parametrize("code, expected", [
    ('session.emit({"type": "dance", "text": "x"})', ["dance"]),
    ("await ws.send_json({'type': 'welcome'})", ["welcome"]),
    ('content.append({"type": "image"})', []),  # Anthropic blocks are not phone messages
])
def test_python_scanner_sees_what_it_should(code, expected):
    assert [m.group(1) for m in PY_SEND.finditer(code)] == expected


@pytest.mark.parametrize("code, expected", [
    ('send({ type: "dance" })', ["dance"]),
    ('ws.send(JSON.stringify({ type: "hello", code }))', ["hello"]),
    ('case "reply": speak(msg.text); break;', []),
])
def test_js_scanner_sees_what_it_should(code, expected):
    assert [m.group(1) for m in JS_SEND.finditer(code)] == expected
