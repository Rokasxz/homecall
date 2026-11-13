# HomeCall

Call your home PC from your phone. See its screen, tell it what to do, get files
sent back. A 2-day hackathon project.

- Plan, decisions and why: PLAN.md
- Team rules and the contract between the parts: CLAUDE.md
- Who does what: TASKS.md
- Teammates start here: TEAMMATE-GUIDE.md (login, rules, prompts, testing)
- How we work together: TEAM-SETUP.md, PROMPTS.md

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
phone/           the phone web app: live view, mic, speech           (Phone app)
```
