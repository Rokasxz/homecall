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

Automatic runs: `tests/ci/run-tests.yml` is a ready-made GitHub check that runs
these tests on every Pull Request and every merge into main. It switches on once
the lead copies it to `.github/workflows/tests.yml` (a shared folder).
