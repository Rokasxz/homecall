"""Check the voice setup and print exactly what to paste into ElevenLabs.  (Owner: Voice)

    python -m pc.voice.check                                   # key + agent check
    python -m pc.voice.check https://xxxx.trycloudflare.com    # also prints the Custom LLM URL

Never prints your API key. Prints the agent secret only inside the URL you paste
into ElevenLabs (that URL is the secret: don't share it outside ElevenLabs).
"""
import sys

from pc.voice import eleven


def main() -> None:
    key = eleven.setting("ELEVENLABS_API_KEY")
    secret = eleven.setting("HOMECALL_AGENT_SECRET")
    agent = eleven.setting("ELEVENLABS_AGENT_ID")
    print("Voice setup check")
    print(f"  ELEVENLABS_API_KEY     {'set' if key else 'MISSING: paste it into .env'}")
    print(f"  HOMECALL_AGENT_SECRET  {'set' if secret else 'MISSING: add a random value to .env'}")
    print(f"  ELEVENLABS_AGENT_ID    {'set' if agent else 'missing: create the agent (pc/voice/DUPLEX.md), then paste its id'}")
    if key:
        try:
            audio = eleven.text_to_speech("Hello from HomeCall.")
            print(f"  speak test             OK ({len(audio) // 1024} KB of MP3)")
        except Exception as e:  # noqa: BLE001
            print(f"  speak test             FAILED: {e}")
    if key and agent:
        try:
            eleven.signed_url()
            print("  agent test             OK (a private call can start)")
        except Exception as e:  # noqa: BLE001
            print(f"  agent test             FAILED: {e}")
    if len(sys.argv) > 1 and secret:
        base = sys.argv[1].rstrip("/")
        print("\nIn ElevenLabs -> your agent -> LLM -> Custom LLM, paste:")
        print(f"  Server URL:  {base}/voice/llm/{secret}/v1")
        print("  Model ID:    homecall")
        print(f"\nThen open on the phone (Safari): {base}/voice/call")


if __name__ == "__main__":
    main()
