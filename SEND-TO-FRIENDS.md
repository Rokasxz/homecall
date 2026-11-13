# Send-to-friends kit

**Shortcut:** ONE-MESSAGE.md is a single message that does the job of Message 1,
1b and 2 together. Use it if you'd rather send one thing.

Ready-to-paste messages for your teammates, plus the steps for you (the lead).
Replace every [bracket] before sending.

| When | What |
|---|---|
| Right now | **Message 1**: the idea, how we work, what to install, pick an area |
| Right after | **Message 1b**: everyone replies with name, GitHub username, area choice |
| Before day 1 (30 min) | **Lead steps A-D** below, then **Message 2** |
| Once people start building | **Message 3**: the daily routine (pin it in the chat) |

---

## Message 1: send NOW

```
------------------------------------------------
Hey! Hackathon plan.

THE IDEA: "HomeCall". An app on your home PC that you can CALL from your phone when you're away. You see the PC's screen live, you say "find my CV and send it to me" or "open Spotify", and the AI on the PC does it and answers out loud. The skeleton already runs; we build the real thing in 2 days.

HOW WE WORK (so 5 people with AI don't wreck each other's work): the project lives on GitHub. Each of us owns ONE area and works on their OWN branch (= your own copy). Nobody edits someone else's area. A rules file tells everyone's AI the same rules, and a guard blocks your AI from editing files outside your area. We merge small pieces every 1-2 hours.

THE FIVE AREAS (tell me which you want, first come first served):
1. Server & connection: the Python server on the PC, the live screen stream, the tunnel that lets the phone reach the PC from anywhere. Also the integrator. ([I'll take this unless someone really wants it.])
2. Hands: the Python functions the AI can use on the PC: find/open/send files, open apps, keyboard.
3. Brain: the AI loop (Claude API): turns what you say into tool calls and a short spoken reply.
4. Phone app: the web page on the phone: live view, hold-to-talk mic, speaker, Yes/No and download cards.
5. Voice: speech-to-text and text-to-speech on the PC (Whisper-style), so talking works on every phone, iPhone included.

PLEASE DO TODAY:
1. Free GitHub account (github.com), send me your username.
2. Install Git (git-scm.com, Windows: "Git for Windows") and Python 3.11 or newer (python.org, Windows: tick "Add Python to PATH").
3. Your AI coding tool, one of: Claude Code (the Claude desktop app, "Code" tab) or Codex (ChatGPT's coding tool: install Node from nodejs.org, then `npm install -g @openai/codex`, sign in with your ChatGPT account). Plain ChatGPT in the browser also works but is slower, I'll explain.
4. Whoever takes Brain: get an Anthropic API key at console.anthropic.com (a few dollars of credit is plenty for the weekend). Whoever takes Voice: an OpenAI API key (platform.openai.com) unless you prefer a free local option.

SCHEDULE: Day 1, hour 1, all together: everyone runs the app on their own laptop. Then everyone builds their own area, we merge every 1-2 hours, evening: full demo from a phone. Day 2: finish and polish; [3-4] hours before the deadline we FREEZE and practise the demo.
------------------------------------------------
```

---

## Message 1b: collect everyone's details (send right after Message 1)

Everyone replies with one line in a fixed format. Paste all the replies to
Claude and it fills the names into CLAUDE.md and TASKS.md, assigns the areas,
and invites everyone to the repo.

```
------------------------------------------------
Reply to this message with your line filled in. Keep the format (one line) so I can paste it straight into our setup:

NAME: ___ | GITHUB: ___ | AREA: 1st choice __, 2nd choice __ | AI TOOL: Claude Code / Codex / ChatGPT web | PHONE: iPhone / Android | PC: Windows / Mac

Areas (one owner each, first come first served):
1 Server & connection: taken by me
2 Hands: the Python functions the AI can use on the PC (files, apps, keyboard)
3 Brain: the Claude API loop (what you say -> tool calls -> spoken reply)
4 Phone app: the web page on the phone (live view, mic, speaker, cards)
5 Voice: speech-to-text and text-to-speech on the PC

GITHUB = the name in your profile address, github.com/<that>. No account yet? Make one at github.com (free, 2 minutes), then reply.
Example: NAME: Jonas | GITHUB: jonas-dev | AREA: 1st choice 3, 2nd choice 2 | AI TOOL: Codex | PHONE: Android | PC: Windows
------------------------------------------------
```

## Lead steps (you, about 30 minutes, before day 1)

### A. Put the names in
Open the project in Claude Code and paste (fill the brackets):
```
Read CLAUDE.md and TASKS.md. Replace the placeholders: [Name 1] = [your name]
(lead, Server & connection), [Name 2] = [name] (Hands), [Name 3] = [name]
(Brain), [Name 4] = [name] (Phone app), [Name 5] = [name] (Voice), and [day 2, time] = [the feature
freeze time]. Change nothing else. Show me the diff.
```

### B. Run it once
Follow README.md ("Run it"). You should see the pairing code, open
http://localhost:8000, enter the code, type "what's on my desktop" and get an
echo-mode answer. Also install cloudflared and try the tunnel once (README).

### C. Put it on GitHub
1. github.com -> New repository -> name it `homecall`, **Private**, leave it
   empty (no README, no .gitignore).
2. In the project folder, one command at a time (replace the address with the
   one GitHub shows you):
   ```
   echo "." > .claude/my-area
   git init
   git add .
   git commit -m "HomeCall starter: plan, rules, skeleton"
   git branch -M main
   git remote add origin https://github.com/[you]/homecall.git
   git push -u origin main
   ```
   If git says "Please tell me who you are", run
   `git config --global user.name "Your Name"` and
   `git config --global user.email "you@example.com"`, then repeat the commit.
   (Or ask Claude: "Create the private GitHub repo homecall and push this
   folder. Ask me before you push.")
3. Check on GitHub that `.env` is NOT there (it's gitignored) and that `pc/`,
   `phone/`, `CLAUDE.md`, `PLAN.md` are.
4. Add everyone: repo -> Settings -> Collaborators -> Add people.
5. Optional: protect `main` (TEAM-SETUP.md, Part 1, step 4).

### D. Send Message 2

---

## Message 2: send when the repo is up

```
------------------------------------------------
The project is on GitHub: [repo link]. Check your GitHub email and ACCEPT the invite.

Your areas:
[Name 1] (lead): Server & connection -> pc/server.py, pc/screen.py, pc/session.py, shared files
[Name 2]: Hands -> pc/actions/
[Name 3]: Brain -> pc/brain/
[Name 4]: Phone app -> phone/
[Name 5]: Voice -> pc/voice/

Do this once, in this order (15 min):

1. GET THE PROJECT. Open your AI tool (Claude Code or Codex) in a folder where you keep projects (e.g. Documents) and paste PROMPT 1 below.

2. OPEN THE AI TOOL INSIDE THE PROJECT FOLDER (Claude Code: new session, pick the "homecall" folder. Codex: cd into the folder, then run codex). This matters: that's when the rules and the guard switch on.

3. SET UP. Paste PROMPT 2 below with YOUR area folder in it (from the list above). Codex users: also run /hooks inside Codex once and trust the project's hook (that's the guard).

4. Read TEAMMATE-GUIDE.md in the project (10 min): the rules, the prompts for every situation, and how to test. Then your section in TASKS.md. Write "ready" in the chat when python check.py passes on your laptop.

Then paste the kickoff prompt (PROMPTS.md, prompt 5) followed by the "Start prompt" from your TASKS.md section, and go.

>>> PROMPT 1 (copy from here) >>>
Download our team project with git: run git clone [repo link] into a new folder inside the current folder. Then tell me the full path of the new folder and exactly how to open this AI tool inside it (I'm new to this). Don't do anything else.
<<< (to here) <<<

>>> PROMPT 2 (copy from here) >>>
Help me set up for our team hackathon project. I'm new to git and Python, so explain each step in plain words.
1. Read CLAUDE.md, PLAN.md and TASKS.md. Summarize in 5 short bullets how our team works, what we're building, and which area I own.
2. My area folder is: [YOUR AREA FOLDER, e.g. pc/actions/]. Create the private file .claude/my-area with exactly that folder as its only line, using a shell command: echo "[YOUR AREA FOLDER]" > .claude/my-area (the edit tool is blocked for this file on purpose). Don't commit it.
3. Follow README.md to create the virtual environment and install the requirements. Run python check.py and show me the result; if something FAILS, explain it. Then run the app, open http://localhost:8000 in my browser, show me where the pairing code is, and check that typing "what's on my desktop" gets an answer.
4. Create my branch feature/[my area]-[first task from my TASKS.md section] from the latest main.
Don't change any other file yet.
<<< (to here) <<<
------------------------------------------------
```

### If someone uses ChatGPT in the browser (no Codex)
It works, just slower:
- At the start of every chat they paste the whole CLAUDE.md, then the kickoff
  prompt (PROMPTS.md, prompt 5), then their task. ChatGPT writes code; they
  paste it into the files themselves and run `python -m pc.server` to test.
- There's no guard for them, so before merging their Pull Request, check the
  "Files changed" tab on GitHub: anything outside their area goes back.
- Better: Codex (the terminal tool) reads AGENTS.md automatically, edits files
  itself, and the guard works with it (`.codex/hooks.json`). I couldn't test
  the Codex guard myself; if it doesn't load, the GitHub check above is the backstop.

---

## Message 3: the daily routine (pin it in the chat)

```
------------------------------------------------
CHEAT SHEET

Start of every work session (in the project folder):
  git checkout main
  git pull
  (new task)      git checkout -b feature/<area>-<task>
  (continuing)    git checkout <your branch>   then   git pull origin main

Then open your AI tool in the project and start with the kickoff prompt (PROMPTS.md, prompt 5): your area, your task, what "done" looks like.

While working: small steps, run python -m pc.server and try it after each one, commit whenever something works.

Finished a piece? Prompt 9 ("check my branch"), push, open a Pull Request on GitHub, ask someone for a 2-minute look, merge. Every 1-2 hours, not once a day.
After a merge: everyone pulls main. The lead runs prompt 9b (do the pieces still fit together?).

Golden rules:
- Only edit your own area. Never work on main.
- Need something from someone else? Write it under "Needs from others" in your TASKS.md section, or message them. Don't edit their files.
- "Blocked: outside your area" = the guard. Don't work around it, tell the owner.
- Never commit .env (your API key). It's gitignored, keep it that way.
- Stuck for more than 20 minutes? Ask in the chat.
------------------------------------------------
```
