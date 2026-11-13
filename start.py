#!/usr/bin/env python3
"""Connect THIS computer: one command starts HomeCall, makes it reachable from a
phone, and (if the ElevenLabs key is in .env) points YOUR voice agent at it.

    python start.py              start everything; Ctrl+C stops everything
    python start.py --local      only on this computer (http://localhost:8000), no tunnel

The first time, it asks for the team's keys (Claude for the AI, ElevenLabs for voice)
and keeps them in .env on this computer only.

Then call this computer from your own phone with the address and code it prints.
Everyone on the team can do this with their own PC, to test and find bugs.
(Owner: lead.)
"""
import getpass
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ENV = ROOT / ".env"
PORT = int(os.environ.get("HOMECALL_PORT", "8000"))


# ------------------------------------------------------------------ helpers ---

def read_env() -> dict:
    out = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def set_env(key: str, value: str) -> None:
    """Add or replace KEY=value in .env (private, gitignored)."""
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    lines = [l for l in lines if not l.startswith(key + "=")] + [f"{key}={value}"]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def say(text: str = "") -> None:
    print(text, flush=True)


def port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


# ---------------------------------------------------------------- first run ---

def claude_key_problem(key: str) -> str:
    """'' if the Claude key works (a free check: list the models), else what's wrong."""
    try:
        import anthropic
        anthropic.Anthropic(api_key=key, max_retries=0, timeout=20).models.list(limit=1)
        return ""
    except ImportError:
        return ""  # can't check without the library; the app will say if it's wrong
    except Exception as e:  # noqa: BLE001
        name = type(e).__name__
        if name in ("AuthenticationError", "PermissionDeniedError"):
            return "Claude didn't accept it: copy the whole key again"
        if name in ("APIConnectionError", "APITimeoutError"):
            return "couldn't reach Claude: check the internet"
        return f"{name}: {str(e)[:80]}"


def ask_keys(local_only: bool) -> None:
    """First run: ask for the team's keys and keep them in .env. Only in a real terminal."""
    if not sys.stdin.isatty():
        return
    env = read_env()
    mode = (env.get("HOMECALL_BRAIN") or "").lower()
    if not env.get("ANTHROPIC_API_KEY") and mode not in ("max", "echo"):
        say("\nFirst time here? Paste the team's Claude API key (ask Rokas privately) and press Enter.")
        say("It stays on this computer only (in .env). Typing is hidden. Just Enter = no AI for now.")
        for _ in range(2):
            key = getpass.getpass("  Claude API key: ").strip()
            if not key:
                break
            problem = claude_key_problem(key)
            if not problem:
                set_env("ANTHROPIC_API_KEY", key)
                say("  Saved. The AI is on.")
                break
            say(f"  That key didn't work ({problem}). Try again, or just press Enter.")
    if not local_only and not env.get("ELEVENLABS_API_KEY"):
        say("\nVoice calls: paste the team's ElevenLabs key (ask Rokas privately). Just Enter = no voice.")
        key = getpass.getpass("  ElevenLabs key: ").strip()
        if key:
            set_env("ELEVENLABS_API_KEY", key)
            say("  Saved. Your own voice agent is set up in a moment.")


# -------------------------------------------------------------------- brain ---

def brain_line(env: dict) -> str:
    mode = (env.get("HOMECALL_BRAIN") or os.environ.get("HOMECALL_BRAIN") or "").lower()
    if not mode:
        mode = "api" if env.get("ANTHROPIC_API_KEY") else "echo"
    if mode == "max":
        ok = False
        claude = shutil.which("claude")
        if claude:
            try:
                r = subprocess.run([claude, "auth", "status"], capture_output=True, text=True, timeout=20)
                ok = '"loggedIn": true' in r.stdout
            except Exception:  # noqa: BLE001
                pass
        if not ok:
            return ("max, but Claude Code is NOT logged in here: run `claude auth login` once in a "
                    "terminal (needs your own Claude subscription), then start again")
        return "max (real Claude, through your own Claude login)"
    if mode == "api":
        return "api (real Claude, through ANTHROPIC_API_KEY)"
    return ("echo (no AI: repeats what you say). For real AI: ask Rokas privately for the team's "
            "Claude API key, run start.py again and paste it when asked")


# ------------------------------------------------------------------- tunnel ---

def find_cloudflared() -> str | None:
    """cloudflared on PATH, or where winget/Homebrew put it (a new install isn't on PATH until a new window)."""
    found = shutil.which("cloudflared")
    if found:
        return found
    places = [Path("/opt/homebrew/bin/cloudflared"), Path("/usr/local/bin/cloudflared")]
    for var in ("ProgramFiles(x86)", "ProgramFiles"):
        if os.environ.get(var):
            places.append(Path(os.environ[var]) / "cloudflared" / "cloudflared.exe")
    if os.environ.get("LOCALAPPDATA"):
        places.append(Path(os.environ["LOCALAPPDATA"]) / "Microsoft" / "WinGet" / "Links" / "cloudflared.exe")
    return next((str(p) for p in places if p.exists()), None)


def start_tunnel() -> tuple[subprocess.Popen | None, str | None, str]:
    exe = find_cloudflared()
    if not exe:
        hint = ("cloudflared is not installed, so only this computer can open the app. Install it: "
                "Mac `brew install cloudflared`, Windows `winget install Cloudflare.cloudflared`.")
        return None, None, hint
    proc = subprocess.Popen([exe, "tunnel", "--no-autoupdate", "--url", f"http://localhost:{PORT}"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
                            text=True, encoding="utf-8", errors="replace")
    found = {"url": None, "ready": False, "blocked": False}

    def read() -> None:
        for line in proc.stderr:
            m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
            if m and not found["url"]:
                found["url"] = m.group(0)
            if "Registered tunnel connection" in line:
                found["ready"] = True
            if "7844" in line or "failed to dial to edge" in line:
                found["blocked"] = True

    threading.Thread(target=read, daemon=True).start()
    t0 = time.time()
    while time.time() - t0 < 40 and not (found["url"] and found["ready"]):
        if found["blocked"] and time.time() - t0 > 15:
            break
        time.sleep(0.5)
    if found["url"] and found["ready"]:
        return proc, found["url"], ""
    proc.terminate()
    if found["blocked"]:
        return None, None, ("This network blocks the tunnel (port 7844). Connect this computer to your "
                            "phone's hotspot and run start.py again. Meanwhile it works on this computer only.")
    return None, None, "The tunnel didn't start in 40 s. Check your internet and run start.py again."


# -------------------------------------------------------------------- voice ---

def setup_voice(url: str) -> str:
    """Create or update THIS computer's own ElevenLabs agent so it calls this PC."""
    env = read_env()
    if not env.get("ELEVENLABS_API_KEY"):
        return "off (no ELEVENLABS_API_KEY in .env; ask Rokas for it privately to test voice)"
    for k, v in env.items():
        os.environ.setdefault(k, v)
    if not env.get("HOMECALL_AGENT_SECRET"):
        set_env("HOMECALL_AGENT_SECRET", secrets.token_urlsafe(24))
    sys.path.insert(0, str(ROOT))
    from pc.voice import eleven  # noqa: E402  (Voice area: talks to ElevenLabs)

    llm_url = f"{url}/voice/llm/{os.environ['HOMECALL_AGENT_SECRET']}"
    prompt = {"llm": "custom-llm", "custom_llm": {"url": llm_url, "model_id": "homecall"}}
    agent = env.get("ELEVENLABS_AGENT_ID")
    try:
        if agent:
            raw, _ = eleven._request("PATCH", f"/v1/convai/agents/{agent}",
                                     json.dumps({"conversation_config": {"agent": {"prompt": prompt}}}).encode(),
                                     {"Content-Type": "application/json"})
            got = json.loads(raw or b"{}")
            now = (((got.get("conversation_config") or {}).get("agent") or {}).get("prompt") or {})
            if (now.get("custom_llm") or {}).get("url") != llm_url:
                return "problem: the agent didn't take the new address (check pc/voice/DUPLEX.md)"
            return "on (your voice agent now calls this computer)"
        body = {
            "name": f"HomeCall - {socket.gethostname()}",
            "conversation_config": {
                "agent": {"first_message": "Hi, it's your PC. What do you need?", "language": "en", "prompt": prompt},
                "tts": {"voice_id": "cjVigY5qzO86Huf0OWal"},
            },
            "platform_settings": {"auth": {"enable_auth": True}},
        }
        raw, _ = eleven._request("POST", "/v1/convai/agents/create", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
        new_id = json.loads(raw or b"{}").get("agent_id")
        if not new_id:
            return "problem: ElevenLabs didn't create the agent"
        set_env("ELEVENLABS_AGENT_ID", new_id)
        return "on (created your own voice agent; it calls this computer)"
    except Exception as e:  # noqa: BLE001
        return f"problem: {e}"


SECRET_IN_URL = re.compile(r"(/voice/llm/)[^/\s]+")
LOG = ROOT / "homecall.log"  # the server's log (gitignored: it holds the pairing code)

# ------------------------------------------------------------------- server ---

def start_server() -> tuple[subprocess.Popen, str | None]:
    # UTF-8 both ways: Windows' own encoding can't print e.g. "ž" and the server would crash.
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
               HOMECALL_LOG_LEVEL="info")  # each visit -> homecall.log
    proc = subprocess.Popen([sys.executable, "-m", "pc.server"], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True, encoding="utf-8", errors="replace")
    log = open(LOG, "w", encoding="utf-8", buffering=1)  # every phone visit, for finding bugs
    code = None
    t0 = time.time()
    while time.time() - t0 < 30 and proc.poll() is None:
        line = proc.stdout.readline()
        log.write(line)
        m = re.search(r"Pairing code: (\d{6})", line or "")
        if m:
            code = m.group(1)
            break

    def keep_logging():  # also keeps the pipe drained, or the server would freeze
        for line in proc.stdout:
            line = SECRET_IN_URL.sub(r"\1<secret>", line)  # the voice agent's password is in its URL
            log.write(time.strftime("%H:%M:%S ") + line)

    threading.Thread(target=keep_logging, daemon=True).start()
    return proc, code


# --------------------------------------------------------------------- main ---

def main() -> None:
    local_only = "--local" in sys.argv
    env = read_env()
    say("\nHomeCall: connecting this computer...")
    if not port_free(PORT):
        say(f"\nPort {PORT} is busy: HomeCall (or something else) is already running. Close it first,")
        say("or set HOMECALL_PORT=8001 in .env.")
        sys.exit(1)
    ask_keys(local_only)
    env = read_env()

    tunnel, url, tunnel_note = (None, None, "local only (--local)") if local_only else start_tunnel()
    voice = setup_voice(url) if url else "off (needs the tunnel)"
    server, code = start_server()
    if not code:
        say("\nThe app didn't start. Run `python check.py` to see why.")
        if tunnel:
            tunnel.terminate()
        sys.exit(1)

    say("\n" + "=" * 64)
    say("  HomeCall is connected. Keep this window open; Ctrl+C stops it.")
    say("=" * 64)
    if url:
        say(f"  Phone (type + live screen): {url}")
        say(f"  Phone (voice call, Safari): {url}/voice/call")
    else:
        say(f"  Phone: not reachable. {tunnel_note}")
    say(f"  On this computer:           http://localhost:{PORT}")
    say(f"  Pairing code:               {code}")
    say(f"  Brain:  {brain_line(env)}")
    say(f"  Voice:  {voice}")
    say("  Log:    homecall.log (each phone visit; private: never post it)")
    say("  Found a bug? GitHub -> Issues -> New issue -> Bug. Never post the address or code.")
    say("=" * 64 + "\n")

    try:
        while server.poll() is None and (tunnel is None or tunnel.poll() is None):
            time.sleep(1)
        say("\nThe app or the tunnel stopped. Run `python start.py` again.")
    except KeyboardInterrupt:
        say("\nStopping...")
    finally:
        for p in (server, tunnel):
            if p and p.poll() is None:
                p.terminate()


if __name__ == "__main__":
    main()
