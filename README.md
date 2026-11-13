# HomeCall

Call your home PC from your phone. See its screen, tell it what to do, get files
sent back. A 2-day hackathon project.

- Plan, decisions and why: PLAN.md
- Team rules and the contract between the parts: CLAUDE.md
- Who does what: TASKS.md
- Teammates start here: TEAMMATE-GUIDE.md (login, rules, prompts, testing)
- How we work together: TEAM-SETUP.md, PROMPTS.md

## Connect your own computer (one command)

After the install steps below, run:
```
python start.py
```
It starts the app, opens a tunnel so your phone can reach your computer from anywhere,
points YOUR voice agent at it (if `ELEVENLABS_API_KEY` is in your `.env`), and prints:
the phone address, the voice-call address (`/voice/call`, Safari), and the pairing code.
Keep the window open; Ctrl+C stops everything. Use it to test on your own PC and find bugs
(GitHub -> Issues -> New issue -> Bug).
- **Real AI on your PC:** ask Rokas privately for the team's Claude API key and put it in
  `.env` as `ANTHROPIC_API_KEY=...` (and `HOMECALL_BRAIN=api`, or no `HOMECALL_BRAIN` line).
  It costs the team a cent or two per request, so test, don't leave it chatting. Other
  option: `HOMECALL_BRAIN=max`, `pip install claude-agent-sdk` and `claude auth login` once
  (your own Claude subscription). Without either it runs in echo mode (no AI).
- **Voice on your PC:** ask Rokas privately for the ElevenLabs key, put it in `.env` as
  `ELEVENLABS_API_KEY=...`; `start.py` creates your own voice agent the first time.
- **Needs** `cloudflared` (Mac `brew install cloudflared`, Windows
  `winget install Cloudflare.cloudflared`). If your Wi-Fi blocks it, use your phone's hotspot.

## Run it (on the PC)

Needs Python 3.11 or newer.

```
python -m venv .venv
```
Mac/Linux: `source .venv/bin/activate`   Windows: `.venv\Scripts\activate`
```
pip install -r requirements.txt
python check.py
python -m pc.server
```

`check.py` tests your setup and tells you what to fix. The server prints a 6-digit pairing code. On the same computer, open
http://localhost:8000, enter the code, and you're "on the call".

### Let the AI think (optional while building)
Create a file named `.env` in the project root with one line:
```
ANTHROPIC_API_KEY=sk-ant-...
```
Without it the app runs in "echo mode": everything works except the thinking.

**No API credits?** On a computer where Claude Code is installed and logged in
(e.g. with a Claude Max plan), put `HOMECALL_BRAIN=max` in `.env` and run
`pip install claude-agent-sdk`. The Brain then thinks through Claude Code's login.
Start the server from a normal Terminal window. If replies say "Failed to
authenticate", run `claude auth login` once in Terminal.

### From the phone (and from anywhere, not just home Wi-Fi)
The phone's microphone only works on https pages, so we use a free tunnel that
gives the PC an https address. Install `cloudflared` once
(Mac: `brew install cloudflared`, Windows: `winget install Cloudflare.cloudflared`),
then in a second terminal:
```
cloudflared tunnel --url http://localhost:8000
```
It prints an address like `https://something.trycloudflare.com`. Open that on the
phone. The address changes every time you restart cloudflared.

If cloudflared keeps logging QUIC timeouts or "Allow outbound TCP on port 7844",
the network (e.g. venue or school Wi-Fi) blocks the tunnel. Connect the PC to a
phone hotspot instead. (`--protocol http2` doesn't help: it also needs port 7844.)

The server only listens on this PC (`127.0.0.1`), so phones always come in
through the tunnel, never straight over the Wi-Fi. For a quick test at home
without the tunnel, put `HOMECALL_HOST=0.0.0.0` in `.env` and open
`http://<the PC's IP>:8000` on a phone on the same Wi-Fi (no microphone: that
needs https). Never do that at the venue.

Pairing rules: after 5 wrong codes in a row nobody can pair for 60 seconds;
only one phone can be on the call at a time; files sent to the phone stop
downloading when the call ends.

### Mac only
The first time, macOS asks for Screen Recording and Accessibility permission
for your terminal (System Settings -> Privacy & Security). Without them the
live view is a grey placeholder and typing/clicking does nothing.

## Folders
```
pc/server.py     the server: phone page, screen stream, messages   (Server & connection)
pc/screen.py     screenshots                                         (Server & connection)
pc/session.py    one call; talk back to the phone from anywhere      (Server & connection)
pc/actions/      what the AI can DO on the PC: the tools             (Hands)
pc/brain/        the AI loop: words -> tool calls -> spoken reply     (Brain)
pc/voice/        speech-to-text and text-to-speech on the PC          (Voice)
phone/           the phone web app: live view, mic, speech           (Phone app)
```
