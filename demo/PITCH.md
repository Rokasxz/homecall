# Pitch (1 minute) — DRAFT

Owner: Demo, tests & safety. Read it out loud and time it; cut words until it fits.

## The pitch
**Problem (10 s).** You're on the train and you need a file that's on your home
PC. Remote-desktop apps are fiddly on a phone, and you can't really use a mouse
on a 6-inch screen.

**What we built (15 s).** HomeCall: you *call* your home PC from your phone.
You see its screen live, you just say what you want — "find my CV and send it
to me" — and an AI on the PC does it and answers out loud.

**Demo (the 90 seconds in DEMO-SCRIPT.md).**

**How it works (15 s).** A small Python app on the PC streams the screen to a
web page on your phone over a secure tunnel. What you say goes to Claude, which
uses a handful of safe tools: find, open, send, type. Nothing to install on
the phone.

**What's next (10 s).** Click on things on the screen, read your documents
out loud, and accounts with end-to-end encryption so anyone can use it safely.

**Close (5 s).** Your PC, one phone call away.

## The honest security answer (if a judge asks)
What's there:
- A 6-digit pairing code for every call; https through the tunnel.
- The AI can only touch Desktop, Documents, Downloads and Pictures.
- Anything that can't be undone (deleting) asks Yes/No on the phone first.
- Downloads use long random links; the API key never leaves the PC.
- Automated tests check these rules (tests/).

What's not there yet (it's a 2-day hackathon):
- No limit on wrong code guesses yet (planned: lock out after 5 tries).
- The tunnel address is public: address + code = access.
- No protection against prompt injection (a file could contain text that tricks the AI).
- One phone at a time; no accounts, no audit log.

A real product would add accounts, end-to-end encryption, per-action
permissions and an audit log.
