# Tasks

Each person has ONE section and edits only their own (so this file itself never
causes merge conflicts). Tick a box when the piece is merged into `main`.
The "Start prompt" is what you paste into your AI after the kickoff prompt
(PROMPTS.md, prompt 5) to begin.

## Checkpoints (everyone)
- [ ] Day 1, hour 1: everyone has the app running on their own laptop in echo mode
- [ ] Day 1, hour 1: everyone has opened the tunnel address on their own phone once
- [ ] Day 1, evening: full demo path (PLAN.md) works from a phone on mobile data
- [ ] Day 2, [time]: FEATURE FREEZE
- [ ] Day 2: demo practised twice on the real laptop + phone

## Rokas, lead: Brain + Server & connection + integration (`pc/brain/`, `pc/server.py`, `pc/screen.py`, `pc/session.py`, shared files)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract section 3. I'm
the lead and I own Brain. Task: put my ANTHROPIC_API_KEY in .env (never in
code), run the app, and make the real brain answer. Then tune SYSTEM in
pc/brain/agent.py so replies are one or two spoken sentences, and so 'find my
CV and send it to me' runs find_file and send_file_to_phone in one go."
Brain:
- [ ] Real Claude replies working with a key in `.env`
- [ ] Multi-step requests done in one go ("find X and send it", "open X and play")
- [ ] Short spoken replies; friendly errors (no key, no internet) as a `reply`, never silence
- [ ] "What's on my screen?" uses the screenshot well
- [ ] Nice: `HOMECALL_MODEL=claude-sonnet-5-5` + `HOMECALL_EFFORT=low` if it feels slow
Server & connection (the skeleton already works; these are improvements):
- [ ] Install cloudflared, start the tunnel, open the https address on a phone over mobile data
- [ ] Only send a frame when the screen changed; tune size/quality for mobile
- [ ] Lockout after 5 wrong codes
Lead:
- [ ] Hour 1: everyone's check.py passes; areas confirmed
- [ ] Integration check after every merge (PROMPTS.md 9b); keep `main` runnable; review Pull Requests (TEAMMATE-GUIDE.md prompt O)
- [ ] Approve or refuse new libraries; call the feature freeze
Needs from others: Hands: clear docstrings. Phone: reconnect when the socket drops.

## nojuzaid-spec: Demo, tests & safety (`tests/`, `demo/`)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract sections 1, 2
and 7, plus tests/README.md and demo/README.md. My area is Demo, tests &
safety. Task: write tests/test_hands.py with pytest: one test per function in
pc/actions/basic.py, using a temporary folder as ALLOWED_ROOTS (see check.py
for the pattern) and a fake session object; never touch my real files. Run
them and show me the result. Don't change files outside tests/ and demo/."
- [ ] `tests/test_hands.py`: every tool in pc/actions tested with a temp folder (find, open, send, delete-asks-first)
- [ ] `tests/test_contract.py`: fake phone call over the websocket (wrong code refused, right code welcomed, frames arrive, reply comes)
- [ ] `demo/desktop/`: fake CV PDF, an "old draft" to delete, a notes file; `demo/DEMO-SCRIPT.md`: the 5 requests in order with expected results
- [ ] Safety pass: try to break it (wrong codes, paths like ../, huge files, weird voice input) and write findings under "Needs from others" for the owner
- [ ] Device log: each evening, try every feature on a real phone and PC; note what broke, for whom
- [ ] `demo/PITCH.md`: 1-minute pitch + the honest security answer; practise the demo twice on day 2
Needs from others: everyone: tell me when a piece is merged so I test it.

## Mantas: Hands (`pc/actions/`)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract section 2. My
area is Hands. Task: test every tool in pc/actions/basic.py on this computer by
calling them from a small Python script, fix what doesn't work on this OS, then
add read_file_text(path) that returns the first 3000 characters of a .txt, .md
or .pdf file (use pypdf for pdf only if the lead approves adding it). Follow
the docstring format exactly."
- [ ] Every starter tool works on the demo PC (Windows and/or Mac)
- [ ] `read_file_text(path)`: text of .txt/.md (and .pdf if approved)
- [ ] `media_key(action)`: play/pause, next, volume up/down (pyautogui `playpause` etc.)
- [ ] `click_at(x, y)` and `click_text(text)`? (needs screen coordinates; talk to Brain first)
- [ ] `lock_pc()` / `sleep_pc()` with confirm
- [ ] Better `find_file`: also match "cv" to "Curriculum Vitae", recent files first
Needs from others: Brain: tell me which tools the AI misuses, I'll fix the docstrings.
Lead: OK to add `pypdf` to requirements.txt? `read_file_text` already uses it for .pdf if it's installed (CVs are often PDFs); without it, it says it can't read PDFs.
Lead: on Python 3.15 (Windows), `pip install -r requirements.txt` fails: `uvicorn[standard]` pulls in `pyyaml`, which has no 3.15 build yet and needs a C compiler. Workaround: install plain `uvicorn` + `websockets httptools watchfiles python-dotenv`. check.py then passes.
nojuzaid-spec: I ran your `tests/test_hands.py` against my branch: 37 pass. 3 need a test update, not a Hands fix: (1) new tool `read_file_text` has no test yet (reads .txt/.md/.csv/.docx, first 3000 chars); (2) `open_app` on Windows now looks the app up in the Start menu first, so it launches with `explorer.exe shell:AppsFolder\...` and gives "Error: no app called ..." for unknown names, so `test_open_app_launches_and_shows_status` sees a different launch call; (3) the null-character bug is fixed, so drop the `xfail` in `test_file_tools_never_raise_on_weird_input`.

## Matuuunej: Phone app (`phone/`)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract section 1. My
area is Phone app. Task: run the app, open http://localhost:8000 in the laptop
browser, then make it look and feel like a phone call: full-screen live view,
a big hold-to-talk button, the status under the screen, replies read aloud,
and a clear fallback to typing when the microphone isn't available. Don't
change the message contract."
- [ ] Tested on a real phone over the https tunnel: mic works? speaker works? (iPhone: Safari only, not "add to home screen")
- [ ] Call-like layout; big mic button; status line animates while the AI works
- [ ] Mic fallback: show the text box prominently when SpeechRecognition is missing
- [ ] File card with a download button; confirm card that's hard to miss
- [ ] Reconnect automatically if the socket drops; remember the code (localStorage)
- [ ] Nice: "Calling..." animation, vibration on reply, dark/light theme
Needs from others: Server: send frames only when the screen changed (less mobile data). Voice: the two endpoints in contract section 6, so the mic works on every phone.

## Nexurent: Voice (`pc/voice/`)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract section 6. My
area is Voice. Task: implement transcribe() and speak() in pc/voice/engine.py
with [OpenAI Whisper + TTS, or a local option]. Tell me which library you need
before adding it, so I can ask the lead. Test with: curl -F audio=@sample.webm
http://localhost:8000/voice/transcribe and open
http://localhost:8000/voice/speak?text=hello in the browser."
- [ ] Pick the provider with the lead (OpenAI key? or local faster-whisper + edge-tts) and get it approved in requirements.txt
- [ ] `transcribe()` works on a recording from a phone browser (webm from Android, m4a from iPhone)
- [ ] `speak()` returns MP3; sounds natural; under 2 seconds for one sentence
- [ ] Agree with Phone: record with MediaRecorder -> POST /voice/transcribe -> send `say`; play /voice/speak for replies
- [ ] Nice: language auto-detect; a short "listening" beep file for the phone
Needs from others: Phone: the record button and audio playback; Lead: OK for the libraries.

## Feature freeze: [day 2, time]
After this only bug fixes and demo polish.
