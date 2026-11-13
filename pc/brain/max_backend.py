"""Brain mode "max": thinks with Claude through Claude Code on this PC.  (Owner: Brain)

Uses the Claude Agent SDK, which runs Claude Code with the Claude login already
on this computer (e.g. a Max plan), so no API credits are needed. Only works on
a PC where Claude Code is installed and logged in (`claude auth login`), and the
login is meant for your own use: fine for building and demoing on your own
laptop; a real product would use an API key instead.

Turn it on with HOMECALL_BRAIN=max in .env (and `pip install claude-agent-sdk`).

Speed: ONE Claude Code process stays open for the whole call (started the
moment the phone connects), so each request skips the ~2 s startup and Claude
remembers the conversation itself.

Safety: the Hands' functions (pc.actions.TOOLS) are the ONLY tools (an
in-process MCP server, so they can still ask the phone Yes/No). Claude Code's
own shell, file-editing and web tools, settings, hooks and CLAUDE.md are off.
"""
import asyncio
import base64
import os
import shutil
import tempfile
import threading

import pc.actions as actions

SERVER = "pc"  # tool names become mcp__pc__<function name>
MODEL = os.environ.get("HOMECALL_MAX_MODEL", "sonnet")   # Claude Code alias; "opus" = smarter, slower
EFFORT = os.environ.get("HOMECALL_MAX_EFFORT", "low")    # low = snappy voice replies; medium/high = more careful
MAX_TURNS = int(os.environ.get("HOMECALL_MAX_TURNS", "10"))
_NEUTRAL_DIR = tempfile.mkdtemp(prefix="homecall-brain-")  # no project CLAUDE.md, hooks or settings
LOGIN_HELP = "On this PC, run `claude auth login` once in a Terminal window, then call again."


def _tool_info(func) -> tuple[str, dict]:
    """Description and JSON schema for a Hands function (from its type hints + docstring)."""
    from anthropic import beta_tool  # already a project dependency
    d = beta_tool(func).to_dict()
    schema = dict(d["input_schema"])
    schema.pop("additionalProperties", None)
    return d["description"], schema


def _make_tool(func):
    from claude_agent_sdk import tool

    async def handler(args: dict) -> dict:
        try:
            text = await asyncio.to_thread(func, **args)  # Hands may block (e.g. waiting for Yes/No)
        except Exception as e:  # noqa: BLE001 - a broken tool must not crash the call
            text = f"Error: {type(e).__name__}: {e}"
        return {"content": [{"type": "text", "text": str(text)}],
                "is_error": str(text).startswith("Error")}

    description, schema = _tool_info(func)
    return tool(func.__name__, description, schema)(handler)


def _options(system: str):
    from claude_agent_sdk import ClaudeAgentOptions, create_sdk_mcp_server

    server = create_sdk_mcp_server(name=SERVER, version="1.0.0",
                                   tools=[_make_tool(f) for f in actions.TOOLS])
    return ClaudeAgentOptions(
        system_prompt=system,
        model=MODEL,
        effort=EFFORT,
        max_turns=MAX_TURNS,
        tools=[],                                  # no shell, no file editing, no web
        mcp_servers={SERVER: server},
        allowed_tools=[f"mcp__{SERVER}__*"],      # the Hands are pre-approved
        permission_mode="dontAsk",                # anything else is refused, never asked
        setting_sources=[],                       # ignore user/project CLAUDE.md, settings, hooks
        cwd=_NEUTRAL_DIR,
        cli_path=shutil.which("claude"),          # the logged-in Claude Code; None = bundled copy
        env={"ENABLE_TOOL_SEARCH": "false"},      # few tools: load them up front, saves a round-trip
    )


class MaxBrain:
    """One Claude Code conversation for the whole phone call."""

    def __init__(self, system: str) -> None:
        self.system = system
        self.session = None          # the current phone session, for status updates
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True, name="max-brain")
        self.thread.start()
        self._ready = self._submit(self._connect())  # warm up now, while the user is still looking

    def _submit(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    async def _connect(self) -> None:
        from claude_agent_sdk import ClaudeSDKClient
        self.client = ClaudeSDKClient(options=_options(self.system))
        await self.client.connect()

    def ask(self, text: str, screenshot_png: bytes | None, session, timeout: float = 180) -> str:
        """Called from Brain.handle (a worker thread). Returns the reply to speak."""
        self.session = session
        session.status("Thinking...")
        for attempt in (1, 2):
            try:
                self._ready.result(timeout=60)
                return self._submit(self._ask(text, screenshot_png)).result(timeout=timeout)
            except Exception as e:  # noqa: BLE001
                msg = str(e)
                if "authenticate" in msg.lower() or "login" in msg.lower():
                    return "I can't reach Claude: the Claude Code login on this PC has expired. " + LOGIN_HELP
                if attempt == 2:
                    return f"Sorry, the brain stopped working ({type(e).__name__}). Please try again."
                self._ready = self._submit(self._connect())  # the process died: start a fresh one
        return "Sorry, something went wrong."

    async def _ask(self, text: str, screenshot_png: bytes | None) -> str:
        from claude_agent_sdk import AssistantMessage, ResultMessage, ToolUseBlock

        content: list[dict] = []
        if screenshot_png:
            content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                         "data": base64.b64encode(screenshot_png).decode()}})
        content.append({"type": "text", "text": text})

        async def messages():
            yield {"type": "user", "message": {"role": "user", "content": content},
                   "parent_tool_use_id": None, "session_id": "default"}

        await self.client.query(messages())
        reply, said = None, []
        async for msg in self.client.receive_response():
            if isinstance(msg, AssistantMessage):
                for block in msg.content:
                    if isinstance(block, ToolUseBlock):
                        self.session.status(block.name.removeprefix(f"mcp__{SERVER}__").replace("_", " "))
                    elif getattr(block, "text", None):
                        said.append(block.text)
            elif isinstance(msg, ResultMessage):
                if msg.subtype == "success" and msg.result:
                    reply = msg.result
                elif msg.is_error and not reply:
                    errors = " ".join(str(x) for x in (getattr(msg, "errors", None) or []))
                    raise RuntimeError(f"{msg.subtype} {msg.result or ''} {errors}".strip())
        return (reply or (said[-1] if said else "") or "Done.").strip()

    def close(self) -> None:
        """Called when the call ends: stop the Claude Code process."""
        try:
            if self.client:
                self._submit(self.client.disconnect()).result(timeout=10)
        except Exception:  # noqa: BLE001
            pass
        self.loop.call_soon_threadsafe(self.loop.stop)
