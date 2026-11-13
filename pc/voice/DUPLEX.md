# Duplex voice call: setup (Owner: Voice)

Talk to the PC like a phone call: it listens while it talks, you can interrupt
it, and it chats like a person. **The Brain and the Hands don't change**:
ElevenLabs only does the *call*; every turn comes to this PC
(`/voice/llm/...`), goes to the team's Brain, and the reply is spoken back.

```
phone  /voice/call  <-- audio -->  ElevenLabs agent ("Custom LLM" = this PC)
                                        | each turn
                                        v
                    pc/voice/duplex.py -> Brain().handle() -> Hands
```

- **Yes/No by voice:** when a tool asks ("Delete old draft?"), the agent says it;
  answer "yes" or "no" (also "taip"/"ne"). Unclear = it asks again. No answer in
  60 s = No.
- **Interrupting:** talk over it and it stops speaking (ElevenLabs). Saying
  **"stop"** while the PC is still working makes every further Yes/No a No.
- **Files:** a file the AI sends shows as a download link on the call page.
- **Safety:** the call page needs the pairing code (5 wrong = locked 60 s); the
  agent is private (signed URL); the Brain endpoint needs a long secret in its URL.
- **No key:** `/voice/speak` and `/voice/transcribe` answer 501 (the phone uses
  its own voice), and `/voice/call` says what is missing.

## One-time setup (about 10 minutes)

1. **Key.** elevenlabs.io → profile → **API Keys** → create, copy. Open `.env` in
   the project folder and paste it after `ELEVENLABS_API_KEY=`. Save. (No restart
   needed: Voice reads `.env` each time.) `HOMECALL_AGENT_SECRET` is already there.
2. **Check:** `python -m pc.voice.check` → "speak test OK".
3. **Public address for the PC.** Start the app and the tunnel (README):
   `python -m pc.server` and `cloudflared tunnel --url http://localhost:8000`.
   Then `python -m pc.voice.check https://<your-tunnel>.trycloudflare.com`
   prints the **Server URL** to paste in step 4.
4. **Agent** (ElevenLabs dashboard → Agents → create a blank agent):
   - **First message:** "Hi, it's your PC. What do you need?"
   - **LLM:** choose **Custom LLM**. Server URL and Model ID: from step 3.
     API key: create any secret (e.g. `unused`); our URL secret protects it.
   - **Voice / language:** pick a voice you like; language English (or Lithuanian).
   - **Security:** turn **authentication ON** (private agent), so only our call
     page can start calls.
   - Copy the **agent ID** into `.env` as `ELEVENLABS_AGENT_ID=...`.
5. **Check again:** `python -m pc.voice.check` → "agent test OK".
6. **Call:** on the phone, open `https://<your-tunnel>/voice/call` in **Safari**
   (not inside Instagram/WhatsApp), enter the pairing code, allow the mic, talk.

The tunnel address changes each time cloudflared restarts: run step 3 again and
update the Server URL in the agent.

## Test without a phone
`python -m pytest tests/test_voice.py -q` (no key, no network, fake Brain).

## Tested live (2026-11-13)
Agent created through the API (`llm: "custom-llm"`, `custom_llm.url` = the Server
URL above without `/v1`, `platform_settings.auth.enable_auth: true`); all settings
read back correctly. A turn sent through ElevenLabs reached this PC through the
tunnel, went to the team Brain (echo mode on this laptop), used `list_files`, and
came back as speech (~6 s with the "..." buffer). An incoming turn interrupted the
greeting, as it should.
