# HomeCall

Call your home PC from your phone: see its screen live, say what you want
("find my CV and send it to me", "open Spotify"), the AI on the PC does it and
answers out loud. A 2-day hackathon; 5 people build at the same time.
Why and how: PLAN.md. How to run it: README.md.

## Tech
- PC side: Python 3.11+, FastAPI + websockets, `mss` (screenshots), `pyautogui`
  (keyboard/mouse), Anthropic SDK (`anthropic`) for the brain. Folder `pc/`.
- Phone side: plain HTML/CSS/JS served by the PC. No framework, no build step. Folder `phone/`.
- Reach the PC from outside: `cloudflared tunnel --url http://localhost:8000`.
- Run: `python -m pc.server` from the project root (needs the venv active).
- Tests: `python check.py` (setup, tool format, and a fake phone call). "Tested"
  also means: run the app and try the demo path in PLAN.md.

## Who owns what
Every area has ONE owner. In your own area, edit freely. In someone else's,
don't edit: ask the owner, or write it under "Needs from others" in your own
section of TASKS.md.

| Area                    | Files                                                     | Owner           |
|-------------------------|-----------------------------------------------------------|-----------------|
| Lead: integration, shared files | `check.py`, `team/`, README, requirements.txt, CLAUDE.md, .env.example; merges, reviews, demo | Rokas |
| Server & connection     | `pc/server.py`, `pc/screen.py`, `pc/session.py`           | nojuzaid-spec   |
| Hands (what the AI can do) | `pc/actions/`                                          | Mantas        |
| Brain (the AI loop)     | `pc/brain/`                                               | [Name 3]        |
| Phone app               | `phone/`                                                  | Matuuunej       |
| Voice (speech in and out) | `pc/voice/`                                             | Nexurent        |

## Rules for the AI (Claude, Codex, or any other)
- Work only inside the area of the person you are helping. If a task needs a
  change outside it, STOP and tell the person. Don't make the change yourself.
- Never work on `main`. Before editing, check with `git branch --show-current`.
  If it says `main`, stop and ask.
- Never force-push, never rewrite git history, never delete branches that aren't yours.
- Keep changes small and about one task. Don't reformat or "clean up" files you
  weren't asked to touch.
- Don't add libraries or change `requirements.txt` without asking: it affects
  everyone. Only the lead commits dependency changes.
- Prefer adding NEW files inside your own folder over editing shared ones.
- If two areas seem to overlap, or the contract below is unclear: stop and ask.
- A guard (`.claude/hooks/stay-in-my-area.sh`) blocks edits outside the person's
  area. If it blocks you, don't look for a way around it. Tell the person.
- Explain what you changed in plain language (we are new to coding).
- Before saying you're done, run `python -m pc.server`, try the thing in the
  browser, and say whether it worked.
- If your change touches the contract below, update it in the same change and
  tell the person to warn the team.
- Never put an API key in code or in a committed file. It lives in `.env` (gitignored).

## How the parts talk to each other (the "contract")
Change this only when the whole team agrees, and in the same Pull Request as the code.

### 1. Phone <-> PC: one websocket at `/ws`
Phone -> PC (JSON text messages):
| Message | Meaning |
|---|---|
| `{"type":"hello","code":"123456"}` | First message. Wrong code: PC sends `error` and closes. |
| `{"type":"say","text":"find my cv"}` | The user said or typed something. |
| `{"type":"confirm","id":"a1b2","ok":true}` | Answer to a `confirm` from the PC. |
| `{"type":"hangup"}` | End the call. |

PC -> Phone:
| Message | Meaning |
|---|---|
| binary message | One JPEG screenshot. Show it as the live view. A few per second. |
| `{"type":"welcome","text":"..."}` | Code accepted. Switch to the call screen. |
| `{"type":"status","text":"Opening Spotify"}` | What the AI is doing right now. Show under the screen; don't speak it. |
| `{"type":"reply","text":"Done, Spotify is open."}` | The AI's answer. Show it AND read it aloud. |
| `{"type":"confirm","id":"a1b2","text":"Delete report.docx?"}` | Show Yes / No; answer with a `confirm` message. |
| `{"type":"file","name":"cv.pdf","url":"/files/abc123"}` | A file for the user. Show a download card; the url is on the same host. |
| `{"type":"error","text":"..."}` | Something failed. Show it. |

Adding a message type = add a row here first.

### 2. Hands: `pc/actions/`
- A tool is a plain function in `pc/actions/basic.py` (or a new file in that folder),
  with type hints on every argument, returning `str`, and a Google-style
  docstring (one line, blank line, `Args:` with one line per argument). The
  Brain turns these into AI tools automatically; the docstring is what the AI
  reads to decide when to use it.
- Never raise. Return `"Error: ..."` text instead.
- Dangerous actions (delete, send money, close unsaved work, run commands) must
  call `actions.current_session.confirm("question?")` and stop if it returns False.
- Files only inside `ALLOWED_ROOTS` (Desktop, Documents, Downloads, Pictures).
- Register the function in the `TOOLS` list.
- Progress text for the phone: `actions.current_session.status("Opening X")`.

### 3. Brain: `pc/brain/agent.py`
- `Brain().handle(text, session, screenshot_png)` is called in a worker thread
  once per `say`. It must end with `session.emit({"type": "reply", "text": ...})`.
- It gets its tools from `pc.actions.TOOLS` and must set
  `pc.actions.current_session = session` before running them.
- Without `ANTHROPIC_API_KEY` it answers in "echo mode" so others can test.
- Settings via env vars: `HOMECALL_MODEL` (default `claude-opus-5-5`;
  `claude-sonnet-5-5` is faster), `HOMECALL_EFFORT` (low/medium/high).

### 4. Session: `pc/session.py` (made by the server, used by everyone)
- `session.emit(dict)`: send any PC -> Phone message. Thread-safe.
- `session.status(text)`: shortcut for a `status` message.
- `session.confirm(question, timeout=60) -> bool`: ask Yes/No on the phone and wait.

### 5. Files to the phone
Hands copy the file to `pc/outbox/<token>__<name>` and emit a `file` message
with `url: /files/<token>`. The server serves it from there.

### 6. Voice: `pc/voice/` (two web endpoints, used by the phone)
- `POST /voice/transcribe`, form field `audio` = the recording (webm/ogg/m4a/wav)
  -> `{"text": "find my cv"}`. The phone then sends that text as a normal `say`.
- `GET /voice/speak?text=...` -> MP3 audio. The phone plays it for a `reply`
  instead of the browser's built-in voice.
- Both live in `pc/voice/routes.py` and call `engine.transcribe(audio_bytes, mime_type) -> str`
  and `engine.speak(text) -> bytes` in `pc/voice/engine.py`. Until implemented they
  return 501 and the phone falls back to the browser's own voice. Provider keys
  (e.g. `OPENAI_API_KEY`) go in `.env`.

## Workflow
- Branch name: `feature/<area>-<short-task>`, e.g. `feature/hands-read-file`.
- Start each session by pulling the latest `main` into your branch.
- Commit small and often. The message says what changed and why.
- When a piece works, open a Pull Request into `main`. A teammate takes a quick
  look (minutes), then it gets merged. Merge small pieces every 1-2 hours.
  Nobody pushes straight to `main`.
- Keep `main` always runnable. If your branch breaks the app, fix that first.
- After each merge, the lead runs the integration check (PROMPTS.md, 9b).
- Feature freeze: [day 2, time]. After that, only bug fixes and demo polish.
- Tasks live in TASKS.md. Each person edits only their OWN section there.
- Anything the WHOLE team needs to know goes in this file (through a Pull
  Request). Personal preferences go in CLAUDE.local.md (gitignored). Keep this
  file under ~200 lines.
