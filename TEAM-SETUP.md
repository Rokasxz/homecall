# Team setup: how we work together

Plain-language guide. The idea: everyone works on their own copy (a "branch"),
and the work only joins the real project (`main`) after a teammate checks it.

Sending this to your team? SEND-TO-FRIENDS.md has the messages and prompts to paste.

## Part 0: The 2-day plan

**Day 1, first hour (everyone together)**
- The idea, tech, areas and contract are already decided (PLAN.md, CLAUDE.md).
  Read PLAN.md together (10 min) and confirm who takes which area.
- Everyone gets the project running on their own laptop (README.md). In echo
  mode it works without an API key.
- The Brain owner puts an API key in .env. The lead starts the tunnel and
  everyone opens the https address on their phone once.

**Rest of day 1: build in parallel**
- Everyone on their own branch, in their own area. Merge small pieces every 1-2 hours.
- Need a part that someone else hasn't built yet? Your AI makes a fake
  stand-in for it (prompt 8), so you're never waiting.
- Merge order: whoever finishes first merges right away. Everyone else pulls
  `main` into their branch BEFORE opening their Pull Request, so clashes show
  up on your own branch, not on `main`.
- Evening: everyone merges, pulls `main`, and you run the whole thing once
  (prompt 9b). Pieces that each work alone can still fail together, so this
  check matters. Fix what doesn't fit.

**Day 2: finish features, then freeze**
- Keep building until about 3-4 hours before the deadline.
- Then FEATURE FREEZE: only bug fixes and polish. Write the demo script
  (prompt 10) and practice the demo twice.

## Part 1: One-time setup (one person, the "project lead")

1. Create a repository on GitHub (github.com -> New repository). Keep it Private.
2. The skeleton is already built (README.md says how to run it). Run it once,
   then replace the [Name N] brackets in CLAUDE.md and TASKS.md with real names.
3. Commit it and push it to `main` (SEND-TO-FRIENDS.md has the exact commands).
   Teammates should NOT start until this is in.
4. (Optional) Protect `main`: GitHub repo -> Settings -> Branches -> Add rule
   for `main` -> tick "Require a pull request before merging" and set the
   required approvals to 0. Nobody can push straight to `main`, but you're
   never stuck waiting for a reviewer.
5. Invite everyone: Settings -> Collaborators -> Add people.
6. Make sure the first commit contains the whole folder (`git add .`): the
   docs (`CLAUDE.md`, `AGENTS.md`, `PLAN.md`, `TASKS.md`, `PROMPTS.md`,
   `README.md`, `TEAMMATE-GUIDE.md`), the code (`pc/`, `phone/`,
   `requirements.txt`, `.env.example`, `check.py`), `.gitignore`, `.github/pull_request_template.md`, and the
   "guard": `.claude/settings.json`, `.codex/hooks.json` and
   `.claude/hooks/stay-in-my-area.sh`. The guard blocks the AI from editing
   files outside a person's own area (rules in CLAUDE.md are only suggestions
   to the AI; the guard actually enforces them). It works on Mac/Linux, and on
   Windows with Git Bash. If it ever gives someone trouble, delete the `hooks`
   part of `.claude/settings.json` (or `.codex/hooks.json`); the rest still works.
   `.env` and `.claude/my-area` must NOT be in the commit (they're gitignored).
7. Create your own area file as the lead: `echo "." > .claude/my-area`
   (a single dot means "everything").

## Part 2: First time for everyone else

1. Accept the GitHub invite.
2. Copy the project to your computer: `git clone <the repo address>`.
3. Tell the guard which area is yours. Run this once, with your own folder:
   ```
   echo "pc/actions/" > .claude/my-area
   ```
   (Two folders? One per line, use `>>` for the second.) Claude's edits outside
   these folders are blocked automatically. The file stays on your computer
   only, it's gitignored.
4. Open the folder in Claude Code. It reads CLAUDE.md by itself.
5. Find your section in TASKS.md and pick your first task. Edit only your own
   section.

## Part 3: Every work session

Start (new task):
```
git checkout main
git pull
git checkout -b feature/hands-read-file
```

Start (continuing a task you already began):
```
git checkout feature/hands-read-file
git pull origin main
```
(That second command brings in what teammates finished. Doing it often keeps
clashes small.)

Work with Claude. Only touch files in your own area.

Finish:
```
git status
git add pc/actions
git commit -m "Add title screen with start button"
git push -u origin feature/hands-read-file
```
`git status` lists what changed. If you see files outside your area, stop and
ask (see Part 4).

Then on GitHub click "Compare & pull request", fill in the short form, and ask
a teammate for a quick look (2 minutes, not a full review). Check the app still
runs, then merge it. Then update your computer:
```
git checkout main
git pull
```

## Part 4: When something goes wrong

- **"Merge conflict" message:** two people changed the same lines. Don't panic.
  Ask Claude: "Help me resolve this merge conflict, and explain what you
  picked." Then check the app still runs.
- **I edited something that isn't in my area:** tell the owner. If the change
  isn't needed, undo it with `git restore <file>` (this throws away your
  unsaved edits to that file, so be sure).
- **I worked on `main` by accident:** don't commit. Run
  `git checkout -b feature/<my-task>`. Your edits come with you to the new branch.
- **Claude wants to change a shared file or add a library:** pause and ask the
  team in TASKS.md. These affect everyone.
- **Not sure about a git command:** ask Claude to explain it BEFORE running it.
- **"Blocked: ... is outside your area":** the guard doing its job. Tell the
  owner of that area, or write it under "Needs from others" in your TASKS.md
  section. Don't add the folder to your
  `.claude/my-area` just to get past it, unless the owner agreed.
- **Pieces work alone but break together:** normal, git can't see it. Run prompt
  9b after every merge, and check the contract in CLAUDE.md first.
