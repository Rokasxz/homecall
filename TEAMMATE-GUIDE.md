# HomeCall: teammate guide

Read this once (10 minutes). It has everything: how to log in, how to start
working, the rules, the prompts to paste into your AI, and how to test.
Copy the prompts exactly and fill in the [brackets].

## 0. What we're building (30 seconds)
An app on your home PC that you can CALL from your phone when you're away: you
see the PC's screen live, say "find my CV and send it to me", and the AI on the
PC does it and answers out loud. Full plan: PLAN.md. The exact messages and
function shapes we all share ("the contract"): CLAUDE.md.

Five areas, one owner each. You only ever edit your own folder:
| Area | Folder |
|---|---|
| Lead + Server & connection + Brain | `pc/server.py`, `pc/screen.py`, `pc/session.py`, `pc/brain/`, shared files |
| Hands (what the AI can do) | `pc/actions/` |
| Phone app | `phone/` |
| Voice (speech in and out) | `pc/voice/` |
| Demo, tests & safety | `tests/`, `demo/` |

## 1. Install and log in (once, 20 minutes)
1. **GitHub**: free account at github.com. Send the lead your username, then
   accept the invite email.
2. **Git**: git-scm.com (Windows: "Git for Windows", keep the defaults).
3. **Python 3.11 or newer**: python.org (Windows: tick "Add Python to PATH").
4. **Your AI tool**, one of:
   - **Claude Code**: open the Claude desktop app, go to the "Code" tab, sign in
     with your Claude account (needs a plan that includes Claude Code).
   - **Codex** (ChatGPT's coding tool): install Node from nodejs.org, then in a
     terminal `npm install -g @openai/codex`, run `codex`, choose "Sign in with
     ChatGPT" (needs a plan that includes Codex).
   - **ChatGPT in the browser** works too but you'll paste code into files by
     hand. See section 8.
5. **Brain owner only**: an Anthropic API key from console.anthropic.com. It
   goes into a file called `.env` (step 2 below), never into code or chat.

## 2. Get the project running (once, 15 minutes)
**Step 1.** Open your AI tool in the folder where you keep projects (e.g.
Documents) and paste:
```
PROMPT A: download
Download our team project with git: run git clone [REPO LINK] into a new folder
inside the current folder. Then tell me the full path of the new folder and
exactly how to open this AI tool inside it (I'm new to this). Don't do anything else.
```
**Step 2.** Open the AI tool INSIDE the new `homecall` folder (Claude Code: new
session, pick that folder. Codex: `cd` into it, run `codex`). This matters:
that's when the rules file and the guard switch on.
Codex users: also type `/hooks` once inside Codex and trust the project's hook.

**Step 3.** Paste, with your folder from the table above:
```
PROMPT B: set up
Help me set up for our team project. I'm new to git and Python: explain each step in plain words.
1. Read CLAUDE.md, PLAN.md and TASKS.md. Summarize in 5 short bullets how the
   team works, what we're building, and which area I own.
2. My area folder is [YOUR AREA FOLDER]. Create the private file .claude/my-area
   with exactly that folder as its only line, using a shell command:
   echo "[YOUR AREA FOLDER]" > .claude/my-area   (the edit tool is blocked for
   this file on purpose). Don't commit it.
3. Follow README.md: create the virtual environment, install requirements, run
   python check.py and show me the result. If something FAILS, explain it to me.
4. Run the app (python -m pc.server), open http://localhost:8000 in my browser,
   show me where the pairing code is, and check that typing "what's on my
   desktop" gets an answer.
5. Create my branch feature/[my area]-[my first task from TASKS.md] from the
   latest main.
Don't change any other file yet.
```
**Step 4.** Write "ready" in the team chat. Brain owner: also create `.env`
with `ANTHROPIC_API_KEY=sk-ant-...` (copy `.env.example`).

## 2b. What happens automatically (no need to do anything)
- **Team briefing**: when you open Claude Code in the project, your AI gets a short
  briefing: your branch, whether main moved on (then it should pull first), contract
  changes, requests from teammates, open PRs in your folder. Codex users: AGENTS.md
  tells Codex to run it (`bash .claude/hooks/briefing.sh`).
- **Check before done**: if your AI changed files, it runs `python check.py` by
  itself before saying it's finished, and fixes what broke in your area.
- **On GitHub**: every Pull Request runs the checks (`check`) and verifies every
  file is inside your area (`area`). main only accepts PRs with both green.
- **Coordinator**: every 30 minutes Rokas's coordinator tests new PRs combined with
  the latest main, comments in plain words, and updates the pinned Team status issue.

## 3. The rules (memorize these)
1. **Only edit your own folder.** Need a change elsewhere? Write it under
   "Needs from others" in your TASKS.md section, or ask. Never edit it yourself.
2. **Never work on `main`.** Always on a branch named `feature/<area>-<task>`.
3. **Merge small pieces every 1-2 hours.** Don't sit on a day of changes.
4. **Pull `main` into your branch** at the start of every session.
5. **Run it before you say it works.** `python check.py` plus trying it in the browser.
6. **The contract in CLAUDE.md is shared.** Changing a message or a function
   shape needs the team's OK, in the same Pull Request as the code.
7. **Never commit `.env`** (your API key). It's gitignored; keep it that way.
8. **If your AI says "Blocked: outside your area"**, that's the guard doing its
   job. Don't work around it. Tell the owner.

## 4. Every work session
Start, in a terminal in the project folder:
```
git checkout main
git pull
git checkout -b feature/[area]-[task]        (new task)
git checkout feature/[area]-[task] && git pull origin main   (continuing)
```
Mac/Linux: `source .venv/bin/activate`. Windows: `.venv\Scripts\activate`.

Then open your AI tool in the folder and paste (every session, it's the most
important prompt):
```
PROMPT C: kickoff
Read CLAUDE.md and TASKS.md first. I'm [NAME]. I own [AREA], folder [FOLDER].
Today's task: [TASK FROM MY TASKS.md SECTION].
Done means: [what I should be able to see or do when it works].
Rules for this session:
- Check you're on branch feature/[area]-[task]. If not, create it from the latest main.
- Only edit files inside [FOLDER]. If you need a change anywhere else or in the
  contract in CLAUDE.md, STOP and tell me. Don't do it yourself. A guard may
  block edits outside my area: that's intended.
- Prefer new files in my folder over editing shared files.
- First give me your plan in 3-5 bullets. If it stays inside my folder, start.
- Work in small steps and tell me how to see each one working.
- Explain changes in plain language. Run python check.py before saying you're done.
```
For each new job inside the session:
```
PROMPT D: a task
Task: [one specific thing, e.g. "add read_file_text(path) that returns the first 3000 characters of a .txt file"].
Done when: [what I can see or do].
Edit only: [files or folder].
Don't touch: everything else, especially shared files and the contract.
Example: [1-2 lines of what the result should look like].
Run it after and tell me if it works.
```
One job per prompt. Five small prompts beat one giant one.

After a teammate merges something:
```
PROMPT E: sync
Bring my branch up to date with the latest main (git pull origin main). Tell me
in plain language what changed that affects my area, and whether anything of
mine broke. Don't fix anything yet, just report.
```

Need something that isn't built yet?
```
PROMPT F: fake stand-in
My task needs [e.g. the Brain's real replies], which isn't ready yet. Using the
contract in CLAUDE.md, make a FAKE version inside my own folder that returns
made-up data in the right shape so I can keep working. Name it clearly (fake_...)
and list what to change when the real one is merged.
```

## 4b. Let your AI do the git for you
You don't have to type git commands. These prompts make your AI do it and
explain each step. Use them in the project folder.

Once, on a new computer:
```
PROMPT K: set up git and GitHub for me
Set up git on this computer for our team project. Use the name [MY NAME] and
the email [MY GITHUB EMAIL] for my commits (git config --global). Then help me
log in to GitHub: check if the GitHub CLI (gh) is installed, install it if not
(Mac: brew install gh, Windows: winget install GitHub.cli), and then give me
the exact command to run MYSELF in a normal terminal window:
gh auth login --hostname github.com --git-protocol https --web
Explain what will happen (press Y, press Enter, a code appears, the browser
opens, paste the code). Never ask me for a password or a token, and don't try
to run the login yourself: it needs my keyboard.
```
(The login needs a real terminal window you can type in: Mac "Terminal" app,
Windows "Terminal" or "PowerShell". After it says "Logged in as ...", you're done.)

Every session:
```
PROMPT L: start my session
Start my work session: switch to main, pull the latest changes, then
[create a new branch feature/[area]-[task] / switch to my branch feature/[...] and
pull main into it]. Activate the virtual environment and run python check.py.
Tell me in plain words what changed on main since last time that affects my
area ([FOLDER]). Then wait for my task.
```
```
PROMPT M: commit, push and open a Pull Request
I'm done with this piece. 1) Show me git status and list the changed files;
anything outside [FOLDER] (except my section of TASKS.md) must NOT be included,
tell me if there is some. 2) Run python check.py; stop if it fails. 3) Commit
only my files with a short message saying what changed and why. 4) Push my
branch. 5) Open a Pull Request into main with gh pr create, using a plain-words
description and the checklist from the template, and give me the link to send
to the team. Never push to main directly, never force-push.
```
```
PROMPT N: a teammate's Pull Request was approved and merged
A teammate merged into main. Pull the latest main into my branch, run python
check.py and the app, and tell me if anything of mine broke or if the contract
in CLAUDE.md changed. Don't fix anything yet, just report.
```
Lead only:
```
PROMPT O: review a teammate's Pull Request
Review Pull Request #[NUMBER] with gh (gh pr view, gh pr diff). Check: 1) every
changed file is inside their area ([FOLDER]) or their own TASKS.md section;
2) no secrets, no .env, no new libraries without my OK; 3) check out the branch
in a temporary worktree, run python check.py and the app, and report;
4) if the contract in CLAUDE.md changed, say exactly what. Then tell me
"safe to merge" or list what must change, in plain words. Don't merge it yourself.
```

## 5. How to test (what "it works" means)
Everyone, before every Pull Request: `python check.py` must show 0 failed.
Then, by area:

**Server & connection**: start `python -m pc.server` and, in a second terminal,
`cloudflared tunnel --url http://localhost:8000`. Open the printed https address
on a phone using MOBILE DATA (not the Wi-Fi). The screen must stream and a
file the AI sends must download.

**Hands**: ask your AI:
```
PROMPT G: test my tools
Write pc/actions/try_tools.py: a small script that calls each function in TOOLS
with a safe example (list Desktop, find "cv", open a text file you create first
in Downloads, send it to the phone with a fake session object) and prints each
result. Never delete anything. Run it and show me the output. Then run python
check.py: every tool must PASS.
```

**Brain**: with the key in `.env`, run the app, open http://localhost:8000 and
type these three, one by one: "what's on my desktop", "find my cv and send it
to me", "delete the old draft". Check: replies are 1-2 spoken sentences, the
status line shows the tools it used, the second one runs find + send without
asking, the third one asks Yes/No on the page.

**Voice**: run the app and open http://localhost:8000/voice/speak?text=hello in
the browser: you should hear or download audio. For transcribe, record a short
clip on your phone (or use any .webm/.m4a file) and `curl -F audio=@clip.m4a
http://localhost:8000/voice/transcribe` must return the words.

**Phone app**: test in the laptop browser at http://localhost:8000 first, then on
a real phone through the lead's tunnel address. Check: live view, hold-to-talk
(mic needs https), replies read aloud, the Yes/No card, the download card.
iPhone: use Safari itself, not "Add to Home Screen" (no mic there).

## 6. Finishing a piece
```
PROMPT H: before my Pull Request
Check my branch against main before I open a Pull Request:
1. List the files I changed. Are they ALL inside [FOLDER]? Flag any that aren't.
2. Any leftover debug prints, commented-out junk, or secrets?
3. Run python check.py and the app: does my feature work as described?
4. Did I change the contract in CLAUDE.md? If so, remind me to tell the team.
Then write a short Pull Request description in plain words.
```
Then:
```
git add [your folder]
git commit -m "What changed and why"
git push -u origin feature/[area]-[task]
```
On GitHub click "Compare & pull request", fill in the short form, ask a
teammate for a 2-minute look, merge. Tell the chat: "merged X, pull main".

## 7. When something goes wrong
| What you see | What it means / what to do |
|---|---|
| `ModuleNotFoundError` | The virtual environment isn't active. Activate it (section 4). |
| `Address already in use` | The app is already running somewhere. Close it, or set `HOMECALL_PORT=8001` in `.env`. |
| Grey "screen capture not available" (Mac) | System Settings -> Privacy & Security -> Screen Recording: allow your terminal, restart it. |
| Mic button missing or mic error | The page isn't https. Use the tunnel address, or type instead. |
| "Blocked: ... outside your area" | The guard. Tell the owner of that folder. |
| Merge conflict | Paste PROMPT I. |

```
PROMPT I: merge conflict
I have a merge conflict. For each conflicting file: show me what both sides
changed, tell me which you'd keep and why, and wait for my OK before resolving.
After resolving, run python check.py and the app to check it still works.
```
```
PROMPT J: something is broken
[What I did, what I expected, what happened; paste the error.] Find the cause
BEFORE changing anything and explain it in plain words. Then make the smallest
fix that works, only inside [FOLDER]. If the cause is in another area, tell me
instead of fixing it.
```
Stuck for more than 20 minutes? Ask in the chat. That's not a weakness, it's the plan.

## 8. If you use ChatGPT in the browser (no Codex)
It works, just slower: at the start of each chat paste the whole CLAUDE.md,
then PROMPT C, then your task. ChatGPT writes code; you paste it into the files
yourself and test with `python check.py` and the app. There's no guard for you,
so be strict about staying in your folder; the lead checks "Files changed" on
your Pull Request. If you can, switch to Codex: it edits files itself and the
guard works with it.

## 9. The two days
- Day 1, hour 1: everyone has done sections 1-2, written "ready", and opened
  the tunnel address on their phone once.
- Day 1: build, merge every 1-2 hours. Evening: full demo from a phone on
  mobile data. Fix what doesn't fit.
- Day 2: finish MUST items (PLAN.md), then NICE ones. [3-4] hours before the
  deadline: FEATURE FREEZE, only bug fixes. Practise the demo twice on the
  exact laptop and phone. Charge the phone.
