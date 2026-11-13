"""Brain mode "max": thinks with Claude through Claude Code on this PC.  (Owner: Brain)

Uses the Claude Agent SDK, which runs Claude Code in the background with the
Claude login already on this computer (e.g. a Max plan), so no API credits are
needed. Only works on a PC where Claude Code is installed and logged in, and
the login is meant for your own use: fine for building and demoing on your own
laptop, a real product would use an API key instead.

Turn it on with HOMECALL_BRAIN=max in .env (and `pip install claude-agent-sdk`).

The Hands' functions (pc.actions.TOOLS) become tools in an in-process MCP
server, so they run inside this program and can still ask the phone Yes/No.
Claude Code's own tools (shell, file editing, web) are switched off: the AI can
only use the Hands.
"""
import asyncio
import base64
import os
import shutil
import tempfile

import pc.actions as actions

SERVER = "pc"  # tool names become mcp__pc__<function name>
MODEL = os.environ.get("HOMECALL_MAX_MODEL", "sonnet")  # Claude Code alias; "opus" = smarter, slower
MAX_TURNS = int(os.environ.get("HOMECALL_MAX_TURNS", "10"))
_NEUTRAL_DIR = tempfile.mkdtemp(prefix="homecall-brain-")  # no project CLAUDE.md, hooks or settings


def _schema(func) -> dict:
    """JSON schema for a Hands function, built from its type hints and docstring."""
    from anthropic import beta_tool  # already a project dependency
    schema = dict(beta_tool(func).to_dict()["input_schema"])
    schema.pop("additionalProperties", None)
    return schema


def _description(func) -> str:
    from anthropic import beta_tool
    return beta_tool(func).to_dict()["description"]


def _make_tool(func):
    from claude_agent_sdk import tool

    async def handler(args: dict) -> dict:
        try:
            text = await asyncio.to_thread(func, **args)  # Hands may block (e.g. waiting for Yes/No)
        except Exception as e:  # noqa: BLE001 - a broken tool must not crash the call
            text = f"Error: {type(e).__name__}: {e}"
        return {"content": [{"type": "text", "text": str(text)}],
                "is_error": str(text).startswith("Error")}

    return tool(func.__name__, _description(func), _schema(func))(handler)


async def _run(prompt_text: str, screenshot_png: bytes | None, system: str, session) -> str:
    from claude_agent_sdk import (AssistantMessage, ClaudeAgentOptions, ResultMessage,
                                  ToolUseBlock, create_sdk_mcp_server, query)

    server = create_sdk_mcp_server(name=SERVER, version="1.0.0",
                                   tools=[_make_tool(f) for f in actions.TOOLS])
    options = ClaudeAgentOptions(
        system_prompt=system,
        model=MODEL,
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

    content: list[dict] = []
    if screenshot_png:
        content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                     "data": base64.b64encode(screenshot_png).decode()}})
    content.append({"type": "text", "text": prompt_text})

    async def messages():
        yield {"type": "user", "message": {"role": "user", "content": content}}

    reply, said = None, []
    async for msg in query(prompt=messages(), options=options):
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, ToolUseBlock):
                    session.status(block.name.removeprefix(f"mcp__{SERVER}__").replace("_", " "))
                elif getattr(block, "text", None):
                    said.append(block.text)
        elif isinstance(msg, ResultMessage):
            if msg.subtype == "success" and msg.result:
                reply = msg.result
            elif msg.is_error:
                reply = reply or f"Sorry, I couldn't finish that ({msg.subtype})."
    return (reply or (said[-1] if said else "") or "Done.").strip()


def think(text: str, history: list[dict], screenshot_png: bytes | None, system: str, session) -> str:
    """Called from Brain.handle (a worker thread): returns the reply to speak."""
    try:
        import claude_agent_sdk  # noqa: F401
    except ImportError:
        return "The Max brain needs one more install: pip install claude-agent-sdk"
    earlier = "\n".join(f"{'User' if m['role'] == 'user' else 'You'}: {m['content']}" for m in history[-10:])
    prompt_text = (f"Earlier in this call:\n{earlier}\n\nNow the user says: {text}" if earlier else text)
    session.status("Thinking...")
    return asyncio.run(_run(prompt_text, screenshot_png, system, session))
