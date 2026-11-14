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
6. Bonus, Telegram: first time only, scan the **Telegram QR** in the PC window and tap **Send**
   ("✅ Connected"). Then write to the Home PC account "what's on my desktop", then **call**. If the phone
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

## Demo videos (record them before the pitch)
A backup video saves the pitch if the venue Wi-Fi or a call fails, and short clips work in the slides.
Record **the phone and the laptop at the same time**, then put them side by side.

| Video | Length | What happens |
|---|---|---|
| 1. The voice call (main one) | 60-90 s | Scan the QR, Voice call, "What's on my desktop?", "Find my CV and send it to me" (tap the download), "Open Calculator", "Delete the old draft" -> Yes/No -> No |
| 2. Telegram | 45-60 s | Write "What's on my desktop?" to the Home PC, then "call", join, say "Open Calculator" while the screen shows in the call |
| 3. Setup in 30 s | 30 s | Double-click HomeCall, the PC window with the Telegram QR, scan it, tap Send, "✅ Connected" |

How to record:
- **Phone (iPhone):** Control Center -> Screen Recording (long-press it and turn the **Microphone on**, so your voice is in it).
  Android: Quick Settings -> Screen record (with audio).
- **Laptop (Mac):** press Cmd+Shift+5 -> Record Entire Screen. (Windows: Win+Alt+R with the Xbox Game Bar.)
- Use **demo mode** (`HOMECALL_DEMO=1`), Do Not Disturb on both, a clean desktop, and the phone on the hotspot.
- Start both recordings, then clap once: the clap lines the two videos up when you edit.
- **Edit:** put the phone video next to the laptop video (iMovie, CapCut or Canva: "picture in picture" or a split screen),
  cut the waiting, add one caption per step ("asks before deleting", "file sent to the phone").
- Keep the files on the laptop AND on a USB stick or cloud drive, ready to play if the live demo fails.

## What we can honestly say
- Only you can connect (one-time code, 5 wrong codes = locked out), and risky actions need your Yes.
- Everything travels encrypted; the Telegram call is end-to-end encrypted.
- The AI runs in the cloud (Claude for thinking, ElevenLabs for voice): they process what it sees and hears.
