#!/usr/bin/env bash
# Team briefing for the AI at the start of every session (and after /clear or a
# summary). Claude Code: SessionStart hook in .claude/settings.json. Codex:
# AGENTS.md asks it to run this first. Prints plain text; the AI reads it.
# Only uses git (and gh if installed). Never changes anything.

cd "${CLAUDE_PROJECT_DIR:-$(pwd)}" 2>/dev/null || exit 0
git rev-parse --git-dir >/dev/null 2>&1 || exit 0
GIT_TERMINAL_PROMPT=0 git -c http.lowSpeedLimit=1000 -c http.lowSpeedTime=5 fetch -q origin main 2>/dev/null

branch=$(git branch --show-current 2>/dev/null)
areas=$(grep -v '^[[:space:]]*$' .claude/my-area 2>/dev/null | tr -d '\r' | tr '\n' ' ')
behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo "?")
base=$(git merge-base HEAD origin/main 2>/dev/null)

echo "## Team briefing (automatic, $(date +%H:%M)). Read before starting."
if [ "$branch" = "main" ]; then
  echo "- WARNING: on main. Before editing anything, create a branch: feature/<area>-<task> (CLAUDE.md rules)."
else
  echo "- Branch: $branch"
fi
if [ -n "$areas" ]; then
  echo "- The person's area (.claude/my-area): $areas. Edit only there."
else
  echo "- The person's area is NOT set: ask which folder they own and create .claude/my-area with a shell command (TEAMMATE-GUIDE.md, PROMPT B)."
fi
if [ "$behind" != "0" ] && [ "$behind" != "?" ]; then
  echo "- main has $behind new commit(s) since this branch was updated. First bring it up to date (git pull origin main), then run python check.py."
fi
if [ -n "$base" ] && ! git diff --quiet "$base" origin/main -- CLAUDE.md 2>/dev/null; then
  echo "- The contract (CLAUDE.md) changed on main since this branch started. Re-read it after pulling."
fi
needs=$(git show origin/main:TASKS.md 2>/dev/null | grep -E "^Needs from others:" | grep -v -E "\(nothing yet\)|^Needs from others:[[:space:]]*$")
if [ -n "$needs" ]; then
  echo "- Requests in TASKS.md (check if any is for this person's area):"
  echo "$needs" | sed 's/^/    /' | cut -c1-220
fi
if command -v gh >/dev/null 2>&1 && [ -n "$areas" ]; then
  for a in $areas; do
    [ "$a" = "." ] && continue
    gh pr list --state open --json number,title,author,files \
      --jq ".[] | select(any(.files[]; .path | startswith(\"${a%/}\"))) | \"- Open PR touching $a: #\(.number) \(.title) by \(.author.login)\"" 2>/dev/null
  done
fi
# This person's next step, from the pinned Team status issue (#8).
if command -v gh >/dev/null 2>&1 && [ -n "$areas" ]; then
  first=$(echo "$areas" | awk '{print $1}')
  if [ "$first" = "." ]; then
    who="Rokas"
  else
    who=$(git show origin/main:TASKS.md 2>/dev/null | grep -E "^## " | grep -F "\`${first}" | head -1 | sed -E 's/^## ([^:,]+).*/\1/')
  fi
  case "$who" in nojuzaid-spec) alias="Nojus" ;; Rokas) alias="Rokasxz" ;; *) alias="$who" ;; esac
  if [ -n "$who" ]; then
    body=$(gh issue view 8 --repo Rokasxz/homecall --json body -q .body 2>/dev/null)
    step=$(printf '%s\n' "$body" | grep -F -e "- **${who}:**" -e "- **${alias}:**" | head -1 | sed -E 's/^- \*\*[^*]+:\*\* ?//' | cut -c1-1200)
    if [ -n "$step" ]; then
      echo "- YOUR NEXT STEP (from the pinned Team status issue #8, set by the lead): $step"
      echo "  Start with this unless the person asks for something else."
    fi
  fi
fi
echo "- Team status and each person's next step: https://github.com/Rokasxz/homecall/issues/8"
exit 0
