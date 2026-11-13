# HomeCall: the plan

**One sentence:** an app on your home PC that you can "call" from your phone
when you're away: you see the PC's screen live, say what you want, and the AI
on the PC does it (finds and opens files, sends them to your phone, opens apps,
types) and answers out loud.

Written 2026-11-13 for a 2-day hackathon with 4 people building at the same time.

## The demo (what the judges see, about 90 seconds)
1. Phone: "Call my PC", type the pairing code. The PC's screen appears, live.
2. "What's on my desktop?" The AI reads the folder and answers out loud.
3. "Find my CV and send it to me." On the screen you see the status change
   ("find_file", "send_file_to_phone"), then a download card pops up on the
   phone. Tap, it opens.
4. "Open Spotify and play something." Spotify opens on the live screen.
5. "Delete the old draft." The phone shows Yes / No. Tap No: "Cancelled."
   (Shows judges we thought about safety.)

The wow is step 3: watching your own PC do things while you talk to it from a
phone, anywhere.

## Is it possible? Yes. All the pieces exist
- **OpenClaw (earlier "Clawdbot")** is the big one: an open-source assistant
  that runs on your Mac/PC, which you message from WhatsApp/Telegram/Discord.
  It sorts files, closes apps, runs commands. It needs an Anthropic or OpenAI
  key. It has NO live screen or voice call, and it was criticised for security
  (broad permissions, prompt injection, instances exposed to the internet).
  Our difference: a live call with the screen and voice, and simple pairing.
- **nanoMuse** and **OSIA** are early open-source projects doing "say it on the
  phone, it happens on the PC", including screen-based control. Early stage.
- **Anthropic's computer-use toolset**: the model can look at screenshots and
  click/type by itself. That's our stretch goal, not the MVP.
- **Free tunnels** (Cloudflare quick tunnels) give a home PC a public https
  address with one command and no account.

The hard parts, and how we handle each:
| Hard part | What we do |
|---|---|
| Reaching the PC from outside home Wi-Fi (routers block incoming connections) | `cloudflared tunnel --url http://localhost:8000`: a free https address that forwards to the PC. One command, no account. |
| The phone's microphone only works on https pages | Same tunnel solves it (it's https). On the dev laptop, `localhost` also counts as secure. |
| Speech recognition in mobile browsers is patchy (iOS: only in Safari itself, not "add to home screen") | Use the browser's built-in recognizer where it exists; the text box always works. The demo can type if voice misbehaves. |
| Live video is hard (WebRTC) | We don't do video. The PC sends a small JPEG screenshot 2x per second over the websocket. Looks live enough, 1 hour of work instead of a day. |
| Safety: an AI with your PC in its hands | Pairing code, files only inside Desktop/Documents/Downloads/Pictures, Yes/No on the phone before anything destructive, reply in plain words when a tool fails. Honest limits below. |

## Architecture
```
      PHONE (web page in the browser)                 HOME PC (Python)
  ┌──────────────────────────┐                 ┌──────────────────────────────┐
  │ live screen (JPEG frames)│◀───────────────│ pc/screen.py  screenshots    │
  │ mic -> text  ("say")     │───────────────▶│ pc/server.py  websocket hub  │
  │ speaker <- text ("reply")│◀───────────────│      │                       │
  │ Yes/No      ("confirm")  │◀──────────────▶│      ▼                       │
  │ download card ("file")   │◀───────────────│ pc/brain/   Claude API loop  │
  └──────────────────────────┘                 │      │ calls tools           │
              ▲  one websocket, https          │      ▼                       │
              │  through a cloudflared tunnel  │ pc/actions/  the Hands:      │
              └────────────────────────────────│   files, apps, keyboard      │
                                               └──────────────────────────────┘
```
Everything on the PC is one Python program. The phone is a web page that the PC
itself serves, so there's nothing to install on the phone.

## Tech choices and why
| Choice | Why |
|---|---|
| Python + FastAPI on the PC | Everyone's AI writes Python well; FastAPI gives websockets and file downloads in a few lines. |
| Plain HTML/JS for the phone, no framework, no build step | Four vibecoders, two days: nothing to configure, nothing to break. Open the page, it works. |
| Screenshots over websocket instead of WebRTC video | Simple and good enough for a demo. Upgrade later if ever. |
| Browser speech recognition + speech synthesis | Zero cost, zero setup. Fallback: typing. |
| Claude API with tool use for the brain | The Hands write plain Python functions; the SDK turns them into tools automatically. Model: `claude-opus-5-5`; switch to `claude-sonnet-5-5` with one env var if replies feel slow. |
| cloudflared quick tunnel | Free https address, no account. Meant for testing only (no uptime promise), which is exactly a hackathon. |

## MVP
MUST (the demo doesn't work without it):
1. Pair phone and PC with a code, over the tunnel, from mobile data.
2. Live view of the screen on the phone.
3. Say or type a request; the AI replies, and the phone reads it aloud.
4. Tools: list files, find file, open file, open app, send file to phone.
5. Confirmation on the phone before deleting.

NICE (if there's time):
- Call-like polish: "Calling..." animation, big mic button, vibration on reply.
- Read a file's text ("what does my notes file say?").
- Click on things on the screen (pyautogui, or the computer-use toolset).
- Only send a frame when the screen changed (less mobile data).
- Reconnect automatically; remember the code on the phone.

CUT (don't build these in 2 days):
- Real video / WebRTC. - Native iOS/Android app. - Accounts, multiple users.
- Installer. - Running shell commands by voice (too dangerous for a demo).

## Four areas, four people, at the same time
| Area | Folder | What "done" looks like on day 2 |
|---|---|---|
| Server & connection (lead) | `pc/server.py`, `pc/screen.py`, `pc/session.py`, shared files | Phone on mobile data connects through the tunnel, screen streams smoothly, files download. Runs the integration check after each merge. |
| Hands | `pc/actions/` | Each tool works on the demo PC; 2-3 extra tools (read file text, click, media keys). |
| Brain | `pc/brain/` | Real Claude replies; multi-step requests ("find X and send it") work in one go; short spoken answers. |
| Phone app | `phone/` | Looks like a call; mic and speaker work on a real phone; confirm and file cards look good. |

The skeleton already runs end to end (in "echo mode" without an API key), so
all four start at once; nobody waits for anybody. The exact messages and
function shapes the areas share are in CLAUDE.md ("the contract").

## The two days
**Day 1, hour 0-1 (everyone together)**
- Read this file. Agree who takes which area. Lead fills the names into
  CLAUDE.md and TASKS.md and pushes.
- Everyone: clone, run `python -m pc.server`, open http://localhost:8000 on the
  laptop, enter the code, type "what's on my desktop". Works in echo mode.
- Brain owner: get an API key into `.env`. Lead: start cloudflared, everyone
  opens the https address on their phone once.

**Day 1, hour 1 to evening (parallel)**
- Everyone builds in their own area on their own branch. Merge every 1-2 hours.
- Evening: the lead pulls `main`, runs the full demo path from a phone on mobile
  data (not the Wi-Fi). Prompt 9b in PROMPTS.md finds the pieces that don't fit.

**Day 2, morning**: finish MUST items, then NICE items, biggest wow first.
**Day 2, [3-4 hours before the deadline]: FEATURE FREEZE.** Only bug fixes.
Practice the demo twice on the exact laptop and phone you'll use. Write the
demo script (prompt 10). Charge the phone.

## Risks and the fallback for each
| Risk | Fallback |
|---|---|
| Venue Wi-Fi blocks the tunnel | Run the PC on a phone hotspot; or Tailscale (`tailscale serve`, also gives https). Test the tunnel on day 1, not at the demo. |
| Speech recognition fails on the demo phone | Type the requests. It's still impressive. Test on the exact phone on day 1. |
| Mac asks for Screen Recording / Accessibility permission | Grant it on day 1. Or demo on a Windows laptop. |
| AI replies slowly | `HOMECALL_MODEL=claude-sonnet-5-5`, `HOMECALL_EFFORT=low` in `.env`. |
| The AI does something unexpected on the demo PC | Demo with a throwaway user account and a prepared Desktop (a fake CV, a draft to "delete"). Tools only touch Desktop/Documents/Downloads/Pictures. |
| Two people's changes don't fit together | The contract in CLAUDE.md, merges every 1-2 hours, prompt 9b after merges. |

## Security, honestly
What's there: pairing code, https through the tunnel, file access limited to
four folders, Yes/No before deleting, downloads behind random tokens, the API
key stays on the PC.

What's NOT there (say so if a judge asks; it's a hackathon): no limit on code
guesses (6 digits, add a lockout after 5 tries if time allows), the tunnel
address is public so anyone with the address AND the code gets in, no
protection against prompt injection (a file or web page on the PC could contain
text that tricks the AI), one phone at a time only. A real product would need
accounts, end-to-end encryption, per-action permissions and an audit log.

## Sources
Read:
- [Cloudflare quick tunnels (no account, https)](https://flaviocopes.com/cloudflare-quick-tunnels/) and [Cloudflare docs](https://developers.cloudflare.com/tunnel/get-started/index.md)
- [OpenClaw / Clawdbot hands-on (Android Authority)](https://www.androidauthority.com/openclaw-clawdbot-hands-on-3636283/)
- [Anthropic computer use tool docs](https://platform.claude.com/docs/en/agents-and-tools/tool-use/computer-use-tool.md)
- [Codex CLI hooks](https://learn.chatgpt.com/docs/hooks) (for the guard that works with ChatGPT's coding tool)
Seen in search results only:
- [nanoMuse](https://zeli.app/story/49987765), [OSIA](https://osia-site.pages.dev/), [PCWorld: personal AI with a mini PC and a phone](https://www.pcworld.com/article/3221159/we-built-our-own-personal-ai-with-a-mini-pc-server-and-phone.html)
- [iOS Safari speech recognition limits](https://www.technetexperts.com/ios-safari-speechrecognition-not-working/), [WebKit: getUserMedia needs a secure context](https://bugs.webkit.org/show_bug.cgi?id=180551)
