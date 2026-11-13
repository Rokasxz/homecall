#!/usr/bin/env bash
# Before the AI says it's done: if files changed, run python check.py. If it
# fails, the AI is sent back to fix it (exit 2). Claude Code: Stop hook in
# .claude/settings.json. Runs at most once in a row (stop_hook_active), so it
# can't loop forever, and does nothing when nothing changed.

INPUT=$(cat)
case "$INPUT" in *'"stop_hook_active":true'*|*'"stop_hook_active": true'*) exit 0 ;; esac
cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || exit 0
[ -z "$(git status --porcelain 2>/dev/null)" ] && exit 0      # nothing changed: nothing to check

PY=.venv/bin/python
[ -x "$PY" ] || PY=.venv/Scripts/python.exe
[ -x "$PY" ] || exit 0                                          # no venv yet: skip quietly

OUT=$("$PY" check.py 2>&1); CODE=$?
[ "$CODE" -eq 0 ] && exit 0
{
  echo "python check.py FAILED after the changes in this session. Fix the FAIL lines that are in the"
  echo "person's area, then run it again. If a failure is in someone else's area, don't fix it: tell the person."
  echo "$OUT" | grep -E "FAIL|passed" | tail -15
} >&2
exit 2
