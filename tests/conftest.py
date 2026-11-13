"""Shared test setup.  Owner: Demo, tests & safety.

pytest loads this file before any test. It makes the tests behave the same on
every laptop, whatever is in that person's own .env:

- The Brain is forced into "echo" mode: no real AI, no API credits, and no
  Claude Code session started by HOMECALL_BRAIN=max (since PR 17 a max Brain
  starts Claude Code as soon as it's created).
- Voice provider keys are hidden, so Voice tests never call a paid API.

This runs BEFORE pc.server is imported. pc.server reads .env with setdefault(),
so values set here win over the .env file.
"""
import os

os.environ["HOMECALL_BRAIN"] = "echo"
for _key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
    os.environ.pop(_key, None)
    os.environ[_key] = ""  # empty, so .env's setdefault() can't fill in a real key
