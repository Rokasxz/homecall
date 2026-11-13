# Device test log

Owner: Demo, tests & safety. Every evening (and before the demo), try every
feature on a REAL phone over the tunnel on MOBILE DATA (Wi-Fi off), and note
what broke and whose area it is. Tests can't catch these: real mic, real
speaker, real network, real Safari.

How: the lead starts `python -m pc.server` + `cloudflared tunnel --url http://localhost:8000`
on the demo PC and shares the https address. Open it on the phone.

## Checklist (copy one block per device per evening)

### Day 1 evening — iPhone (Safari) → demo PC (Mac / Windows?)
Tester: nojuzaid-spec · Network: mobile data · main at commit: ______

| # | Feature | Works? | Notes / whose area |
|---|---|---|---|
| 1 | Page opens over https (tunnel) | | Server |
| 2 | Pairing code accepted, "Connected" | | Server |
| 3 | Live screen appears, updates every ~0.5 s | | Server |
| 4 | Screen readable / not too much data | | Server / Phone |
| 5 | Typing a request works ("what's on my desktop") | | Phone / Brain |
| 6 | Hold-to-talk mic: words recognised | | Phone / Voice |
| 7 | Reply is read out loud | | Phone / Voice |
| 8 | Status line shows what the AI is doing | | Phone |
| 9 | "Find my CV and send it to me": download card, PDF opens | | Hands / Phone |
| 10 | "Open Spotify and play something": opens and plays | | Hands |
| 11 | "Delete the old draft": Yes/No card, No = Cancelled, file stays | | Hands / Phone |
| 12 | Lock the phone 30 s, unlock: call reconnects? | | Phone |
| 13 | Wrong code is refused | | Server |
| 14 | Whole demo under 90 seconds | | everyone |

Broke / for whom:
-

### Day 2 morning — repeat on the exact demo phone + PC
(same table)

## Live test #1 — Rokas's laptop, real AI (Max brain), day 1 evening
Tester: Nojus · Phone: iPhone, Safari, mobile data (Wi-Fi OFF) · Address/code: from the chat (never on GitHub)
Rules: it's Rokas's real PC: always tap **No** on delete questions.

| Step (DEMO-SCRIPT.md) | Time (s) | Worked? | What happened / whose area |
|---|---|---|---|
| 1 Pair + live screen | | | |
| 2 "What's on my desktop?" | | | |
| 3 "Find my CV and send it to me" (download opens?) | | | |
| 4 "Open Spotify and play something" | | | |
| 5 "Delete the old draft" → tap No | | | |
| Mic (hold to talk) | | | |
| Reply read aloud | | | |
| Prompt injection (demo/safety-tests/) | | | |
