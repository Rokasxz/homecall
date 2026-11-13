# Tests  (Owner: Demo, tests & safety)

Automated checks that the pieces still do what the contract in CLAUDE.md says.
Run them with `python -m pytest tests/` from the project root (pytest is in
requirements.txt).

Rules for this folder:
- Tests only READ the app's code; they never change files in other areas. If a
  test finds a bug, write it under "Needs from others" in your TASKS.md section
  for the owner, with the failing test's name.
- Never touch the real Desktop/Documents: make files in a temporary folder and
  point `pc.actions.basic.ALLOWED_ROOTS` at it (see check.py for the pattern).
- One file per area: `test_hands.py`, `test_contract.py` (fake phone call over
  the websocket), `test_voice.py`, ...

Your own `.env` never changes the tests: `tests/conftest.py` forces the Brain into
echo mode and hides API keys before anything is imported, so no real AI, no
credits, and no Claude Code session start during tests.
