# HomeCall demo: one page

## 10 minutes before
1. **Demo laptop on the phone's hotspot.** The venue Wi-Fi blocks the tunnel and Telegram calls.
   Turn off "Auto-Join" for the venue Wi-Fi, or the laptop jumps back to it.
2. **Demo mode on:** put `HOMECALL_DEMO=1` in `.env` (or run `python start.py --demo`). The AI then
   only sees a copy of `demo/desktop` (a fake CV, an old draft, notes), never your real files.
3. Tidy the screen: close private chats and windows, turn on Do Not Disturb.
4. **Double-click `HomeCall.command`** (Mac) or **`HomeCall.bat`** (Windows). Allow what macOS asks.
   The **PC window** opens: QR code, and every dot green. The summary says `Files: DEMO`.
5. Practice call: scan the QR with the phone, tap **Voice call**, **Call my PC**, allow the microphone,
   say "What's on my desktop?". Hang up.
6. Optional self-test (13 checks, ~30 s): `python team/demo_check.py <address> <code>`.

## The demo (about 90 seconds)
1. "This is my laptop at home. I'm away, so I call it." Scan the QR, **Voice call**, **Call my PC**.
2. **"What's on my desktop?"** It lists the CV, the notes and the old draft.
3. **"Find my CV and send it to me."** A download card appears on the phone.
4. **"Open Calculator."** Everyone sees it open on the live screen.
5. **"Delete the old draft."** A **Yes/No** card appears first. Tap **No**: "cancelled". (Safety: risky things always ask.)
6. Bonus, Telegram: write to the Home PC account "what's on my desktop", then **call**. If the phone
   shows the call as missed, tap the camera icon on the call message to join.

## If something goes wrong
| You see | Do this |
|---|---|
| "Can't reach your PC" on the phone | Laptop off the hotspot? Close HomeCall, double-click again, scan the NEW QR (address and code change every start) |
| PC window: "This Wi-Fi blocks the tunnel" | Switch the laptop to the hotspot, start HomeCall again |
| Voice: no microphone / silence | Tap **Type instead** and type the same sentences |
| "On it, one moment." then a pause | Normal for longer tasks: it speaks the result when done |
| Live screen frozen | Close the HomeCall window, double-click again |
| Telegram call shows "missed" | Tap the camera icon on the call message |

## What we can honestly say
- Only you can connect (one-time code, 5 wrong codes = locked out), and risky actions need your Yes.
- Everything travels encrypted; the Telegram call is end-to-end encrypted.
- The AI runs in the cloud (Claude for thinking, ElevenLabs for voice): they process what it sees and hears.
