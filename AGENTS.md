# Read CLAUDE.md first

The rules for this project (who owns which folder, the contract between the
parts, branch and merge rules) are in CLAUDE.md in this folder. Read it fully
and follow it exactly. The plan is in PLAN.md.

In short: only edit files inside the area of the person you are helping, never
work on `main`, and stop and ask before changing shared files or the contract.

At the start of every session, run `bash .claude/hooks/briefing.sh` and act on
what it prints (it tells you if the branch is behind main, if the contract
changed, and what teammates asked for). Before saying you're done, run
`python check.py` and `python -m pytest tests -q`; fix failures in your area.

(This file exists for AI tools that look for AGENTS.md instead of CLAUDE.md,
such as Codex. For Codex the same edit guard is wired up in `.codex/hooks.json`;
the person must trust it once with `/hooks` inside Codex. If the guard isn't
active, be extra careful to stay inside the person's area.)
