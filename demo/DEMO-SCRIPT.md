# Demo script (about 90 seconds)

Owner: Demo, tests & safety. Based on the demo in PLAN.md. Practise it twice on
day 2 on the EXACT laptop and phone, with the phone on mobile data.

## Before the judges arrive (10 minutes earlier)
1. Demo laptop: use a clean user account (or a tidy Desktop) so no private
   files show up on the live screen or in search results.
2. Put the fake files on the Desktop:
   `python demo/make_demo_files.py --install`
   This copies `CV_Alex_Demo.pdf`, `Old draft - essay.txt` and `notes.md` (never overwrites).
3. Check Spotify is installed and signed in. If not, use "Open Calculator" in step 4.
4. `.env` has the API key. Start the app: `python -m pc.server`. Note the pairing code.
5. Second terminal: `cloudflared tunnel --url http://localhost:8000`. Note the https address.
6. Phone: Wi-Fi OFF (mobile data), Safari (iPhone) or Chrome (Android), open the
   https address, keep it on the code screen. Volume up. Phone charged.
7. Mac only: Screen Recording + Accessibility are allowed for the terminal (else the
   live view is grey and typing does nothing).
8. Close everything private on the laptop (mail, chats, browser tabs).

## The demo

| # | Who says / does | What the judges should see | If it goes wrong |
|---|---|---|---|
| 0 | Presenter: "I'm away from home and I need something from my PC." | Phone shows the HomeCall code screen. | |
| 1 | Types the pairing code, taps **Call my PC**. | The laptop's screen appears on the phone, live. "Connected to your PC." | Wrong code? Re-read it from the terminal. Grey screen? Mac permissions (step 7). |
| 2 | Says (or types): **"What's on my desktop?"** | Status shows `list_files`; the phone reads out the Desktop: CV, old draft, notes. | No voice? Type it. It's still the same demo. |
| 3 | **"Find my CV and send it to me."** | Status: `find_file` then `send_file_to_phone`. A download card pops up on the phone. Tap it: the CV opens on the phone. **This is the wow: pause here.** | If it asks "which CV?", say "the Alex Demo one". |
| 4 | **"Open Spotify and play something."** | Spotify opens on the live screen (on the phone). | Spotify missing: "Open Calculator". |
| 5 | **"Delete the old draft."** | The phone shows **Yes / No**: "Delete Old draft - essay.txt?". Tap **No**. The phone says "Cancelled." | Explain: "Anything that can't be undone asks first, on the phone." |
| 6 | Presenter: "Files stay in four folders, pairing code, and it always asks before deleting." Hang up. | | |

Bonus if there's time: **"What does my notes file say?"** (needs `read_file_text` from Hands).

## Expected results (check during practice)
- [ ] 1: frames arrive within 2 seconds of the code.
- [ ] 2: reply is 1-2 sentences and names the three demo files.
- [ ] 3: the download card appears in under 10 seconds; the PDF opens on the phone.
- [ ] 4: the app visibly opens on the live view.
- [ ] 5: Yes/No card appears; No leaves the file on the Desktop.
- [ ] Whole demo under 90 seconds.

## After the demo
Put the Desktop back: delete the three demo files yourself if you want them gone.
