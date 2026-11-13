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

## [Name 1], lead: Server & connection (`pc/server.py`, `pc/screen.py`, `pc/session.py`, shared files)
Start prompt: "Read PLAN.md and CLAUDE.md. My area is Server & connection. Task:
run the app, then make the live view feel smoother: only send a screen frame
when the screen actually changed (compare with the previous JPEG), and let me
tune frame rate and JPEG quality from .env. Don't change the message contract."
- [x] Skeleton runs end to end in echo mode (done before the hackathon)
- [ ] Install cloudflared, start the tunnel, open the https address on a phone over mobile data
- [ ] Only send a frame when the screen changed; tune size/quality for mobile
- [ ] Reconnect-friendly: a second `hello` with the right code replaces the old call
- [ ] Lockout after 5 wrong codes (cheap security win)
- [ ] Integration check after every merge (PROMPTS.md 9b); keep `main` runnable
- [ ] Day 2: demo laptop prepared (fake CV on Desktop, a draft to "delete", permissions granted)
Needs from others: Phone: reconnect automatically when the socket drops.

## [Name 2]: Hands (`pc/actions/`)
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

## [Name 3]: Brain (`pc/brain/`)
Start prompt: "Read PLAN.md and CLAUDE.md, especially contract section 3. My
area is Brain. Task: put my ANTHROPIC_API_KEY in .env (never in code), run the
app, and make the real brain answer. Then tune SYSTEM in pc/brain/agent.py so
replies are one or two spoken sentences, and so 'find my CV and send it to me'
runs find_file and send_file_to_phone in one go without asking questions."
- [ ] Real Claude replies working with a key in `.env`
- [ ] Multi-step requests done in one go ("find X and send it", "open X and play")
- [ ] Short spoken replies; no lists, no markdown
- [ ] Friendly errors (no key, no internet, API error) as a `reply`, never silence
- [ ] "What's on my screen?" uses the screenshot well
- [ ] Nice: `HOMECALL_MODEL=claude-sonnet-5-5` + `HOMECALL_EFFORT=low` if it feels slow
- [ ] Stretch: computer-use toolset (`computer_toolset_20260801`) so the AI can click on the screen itself
Needs from others: Hands: clear docstrings; Server: screenshot of the right monitor.

## [Name 4]: Phone app (`phone/`)
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

## [Name 5]: Voice (`pc/voice/`)
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
