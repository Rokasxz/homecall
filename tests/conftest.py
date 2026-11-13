"""Shared test setup.  Owner: Demo, tests & safety.

pytest loads this file before any test. It makes the tests behave the same on
every laptop, whatever is in that person's own .env:

- The Brain is forced into "echo" mode: no real AI, no API credits, and no
  Claude Code session started by HOMECALL_BRAIN=max (since PR 17 a max Brain
  starts Claude Code as soon as it's created).
- Voice provider keys are hidden (also the ones Voice reads from .env itself),
  so tests never call a paid API.

This runs BEFORE pc.server is imported. pc.server reads .env with setdefault(),
so values set here win over the .env file.
"""
import os

os.environ["HOMECALL_BRAIN"] = "echo"
# Voice reads .env itself (so a pasted key works without a restart): point it at a
# file that doesn't exist, so tests never use a real ElevenLabs key or agent.
os.environ["HOMECALL_ENV_FILE"] = os.path.join(os.path.dirname(__file__), "no-such.env")
for _key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID",
             "HOMECALL_AGENT_SECRET"):
    os.environ.pop(_key, None)
    os.environ[_key] = ""  # empty, so .env's setdefault() can't fill in a real key
