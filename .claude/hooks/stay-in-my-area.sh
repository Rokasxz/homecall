#!/usr/bin/env bash
# stay-in-my-area.sh
#
# Runs before every file edit the AI makes (Claude Code: Edit/Write tools,
# Codex CLI: apply_patch). Blocks the edit if the file is inside this project
# but OUTSIDE the areas listed in .claude/my-area.
#
# .claude/my-area is a personal file (gitignored, every teammate makes their
# own). One folder or file per line, relative to the project root:
#     pc/actions/
#     phone/
#     README.md
# A single dot (.) means "everything" (the project lead uses that).
#
# Limits, so nobody is surprised:
#  - It guards the AI's edit tools only. A shell command such as `sed -i` can
#    still change files. It's a guard rail, not a lock.
#  - Files outside the project folder are always allowed.

INPUT=$(cat)

norm() { printf '%s' "$1" | tr '\\' '/' | sed 's#//*#/#g'; }

HAVE_JQ=0; command -v jq >/dev/null 2>&1 && HAVE_JQ=1

# Project root: Claude Code sets CLAUDE_PROJECT_DIR; Codex sends "cwd" in the JSON.
ROOT="${CLAUDE_PROJECT_DIR:-}"
if [ -z "$ROOT" ] && [ "$HAVE_JQ" = 1 ]; then
  ROOT=$(printf '%s' "$INPUT" | jq -r '.cwd // empty')
fi
ROOT="${ROOT:-$(pwd)}"
ROOT=$(norm "$ROOT"); ROOT="${ROOT%/}"

# ---- collect the file paths this edit touches ---------------------------------
PATHS=""
if [ "$HAVE_JQ" = 1 ]; then
  P=$(printf '%s' "$INPUT" | jq -r '.tool_input.file_path // empty')
else
  P=$(printf '%s' "$INPUT" \
    | grep -o '"file_path"[[:space:]]*:[[:space:]]*"[^"]*"' | head -1 \
    | sed 's/^"file_path"[[:space:]]*:[[:space:]]*"//; s/"$//')
fi
[ -n "$P" ] && PATHS="$P"
# Codex apply_patch: the paths are "*** Update File: path" lines inside the patch text.
APPLY=$(printf '%s' "$INPUT" | grep -o -E '\*\*\* (Add|Update|Delete) File: [^"\\]+' \
  | sed -E 's/^\*\*\* (Add|Update|Delete) File: //')
MOVES=$(printf '%s' "$INPUT" | grep -o -E '\*\*\* Move to: [^"\\]+' | sed -E 's/^\*\*\* Move to: //')
PATHS=$(printf '%s\n%s\n%s\n' "$PATHS" "$APPLY" "$MOVES" | sed '/^[[:space:]]*$/d')
[ -z "$PATHS" ] && exit 0   # not a file edit we understand -> allow

CONF="$ROOT/.claude/my-area"

check_one() {
  local FILE_PATH REL line
  FILE_PATH=$(norm "$1")

  # Only guard files inside the project.
  case "$FILE_PATH" in
    "$ROOT"/*) REL="${FILE_PATH#"$ROOT"/}" ;;
    /*|[A-Za-z]:/*) return 0 ;;
    *) REL="$FILE_PATH" ;;
  esac

  case "$REL" in
    ../*|*/../*|*/..)
      echo "Blocked: '$REL' uses '..'. Use a plain path inside your own area." >&2
      exit 2 ;;
  esac

  # Everyone may edit the shared task list (only their own section, see CLAUDE.md).
  [ "$REL" = "TASKS.md" ] && return 0

  if [ ! -f "$CONF" ]; then
    echo "Blocked: no area set yet. The person must create .claude/my-area with the folder(s) they own, one per line, with a shell command, e.g.:  echo \"pc/actions/\" > .claude/my-area   (project lead: a single dot)." >&2
    exit 2
  fi

  while IFS= read -r line || [ -n "$line" ]; do
    line=$(printf '%s' "$line" | tr -d '\r' | tr '\\' '/' \
      | sed 's#//*#/#g; s/^[[:space:]]*//; s/[[:space:]]*$//')
    line="${line%/}"
    [ -z "$line" ] && continue
    case "$line" in \#*) continue ;; esac
    if [ "$line" = "." ] || [ "$line" = "*" ]; then return 0; fi
    if [ "$REL" = "$line" ] || [[ "$REL" == "$line"/* ]]; then return 0; fi
  done < "$CONF"

  echo "Blocked: '$REL' is outside your area ($(tr '\n' ' ' < "$CONF")). Do NOT edit it. Tell the person; if the change is really needed, write it under 'Needs from others' in the person's own TASKS.md section." >&2
  exit 2
}

while IFS= read -r ONE; do
  [ -n "$ONE" ] && check_one "$ONE"
done <<< "$PATHS"
exit 0
