# The one message to send everyone

Copy everything between the lines into the group chat. It contains the idea,
the area list, what to install, and the two prompts that make their AI
download the project, set it up, and start their first task.

The repo is public, so they can download it at once. Their comment on the
"Join the team" issue gives you their GitHub name and area choice. Then run
`python team/invite.py --invite --assign` (or ask Claude): it adds them as
collaborators and writes their names into CLAUDE.md and TASKS.md.

```
------------------------------------------------
HACKATHON: "HomeCall". An app on your home PC you can CALL from your phone when you're away: you see the PC's screen live, say "find my CV and send it to me", and the AI on the PC does it and answers out loud. The skeleton already runs. We build the real thing in 2 days, 5 people, each owning ONE area, everyone's AI following the same rules file. Project: https://github.com/Rokasxz/homecall

STEP 1: JOIN (30 seconds): open https://github.com/Rokasxz/homecall/issues/1 and comment ONE line, like:
AREA: 3 (2nd choice: 2) | AI: Codex | PHONE: Android | PC: Windows
Areas (one owner each, first come first served by comment time):
  2 Hands: the Python functions the AI can use on the PC (files, apps, keyboard)
  3 Brain: the Claude API loop (what you say -> tool calls -> spoken reply)
  4 Phone app: the web page on the phone (live view, mic, speaker, cards)
  5 Voice: speech-to-text and text-to-speech on the PC
  (1 Server & connection: taken)
No GitHub account? github.com, free, 2 minutes. I add you to the project from your comment; accept the invite email when it comes. You don't need to wait for it to do steps 2-4.

STEP 2: INSTALL (while you wait for the invite):
  - Git: git-scm.com (Windows: "Git for Windows", keep defaults)
  - Python 3.11+: python.org (Windows: tick "Add Python to PATH")
  - Your AI tool: Claude Code (the Claude desktop app, "Code" tab, sign in) OR Codex (install Node from nodejs.org, then in a terminal: npm install -g @openai/codex, run codex, sign in with ChatGPT)
  - Brain: an Anthropic API key (console.anthropic.com). Voice: an OpenAI API key (platform.openai.com) unless you go local.

STEP 3: GET THE PROJECT. Open your AI tool in the folder where you keep projects (e.g. Documents) and paste:
>>> PROMPT 1 >>>
Download our team project with git: run git clone https://github.com/Rokasxz/homecall into a new folder inside the current folder. If it asks me to log in to GitHub, tell me exactly what to do (never ask me for a password). Then tell me the full path of the new folder and exactly how to open this AI tool inside it (I'm new to this). Don't do anything else.
<<< end <<<

STEP 4: OPEN YOUR AI TOOL INSIDE THE homecall FOLDER (Claude Code: new session, pick the folder. Codex: cd into it, run codex; then type /hooks once and trust the project's hook). This is when the rules and the guard switch on. Then paste, with YOUR name and area:
>>> PROMPT 2 >>>
I'm [MY NAME], joining our hackathon team project. My area is [AREA NAME], folder [pc/actions/ | pc/brain/ | phone/ | pc/voice/]. I'm new to git and Python: do everything step by step, explain in plain words, and stop and tell me if something fails.
1. Read TEAMMATE-GUIDE.md, CLAUDE.md, PLAN.md and TASKS.md. Summarize in 5 bullets: what we build, how the team works, what I own, my first task.
2. If git has no name/email set on this computer, ask me and set them (git config --global). Create the private file .claude/my-area with my folder as its only line, using a shell command: echo "[MY FOLDER]" > .claude/my-area (the edit tool is blocked for it on purpose). Don't commit it.
3. Follow README.md: create the virtual environment, install the requirements, run python check.py and show me the result. Explain any FAIL.
4. Run the app (python -m pc.server), open http://localhost:8000 in my browser, show me where the pairing code is, and check that typing "what's on my desktop" gets an answer.
5. Create my branch feature/[my area]-[my first task] from the latest main.
6. Read the "Start prompt" in my section of TASKS.md and begin that task: show me your plan in 3-5 bullets first, then go. Only edit files inside my folder; if something needs a change elsewhere, tell me instead.
<<< end <<<

RULES (the short version; the full guide is TEAMMATE-GUIDE.md in the project):
  - Only edit your own folder. Never work on main. Merge small pieces every 1-2 hours.
  - When a piece works: tell your AI "I'm done with this piece" + PROMPT M from the guide (it commits, pushes and opens a Pull Request). Send the link in the chat; someone takes a 2-minute look; merge.
  - Need something from another area? Write it under "Needs from others" in your TASKS.md section, or ask here. Don't edit their files.
  - Stuck for 20 minutes? Ask here.

PLAN: Day 1 hour 1: everyone writes "ready" here once python check.py passes. Then build. Evening: full demo from a phone. Day 2: finish, then [3-4] hours before the deadline we FREEZE and practise the demo.
------------------------------------------------
```

When the STEP 1 replies come in, paste them to Claude: it fills the names into
CLAUDE.md and TASKS.md, settles the areas, and invites everyone.
