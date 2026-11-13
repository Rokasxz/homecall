#!/usr/bin/env python3
"""Connect THIS computer: one command starts HomeCall, makes it reachable from a
phone, and (if the ElevenLabs key is in .env) points YOUR voice agent at it.

    python start.py              start everything; Ctrl+C stops everything
    python start.py --local      only on this computer (http://localhost:8000), no tunnel
    python start.py --no-window  don't open the PC window (http://localhost:8000/pc) in the browser

On a Mac it first asks for every permission HomeCall needs (see pc/permissions.py),
so nothing pops up in the middle of a call. Then it opens the PC window with a QR
code: scan it with your phone's camera.

It gets the team's keys (Claude for the AI, ElevenLabs for voice) by itself from the
private repo Rokasxz/homecall-keys, with your GitHub login, into .env. It never asks.

Then call this computer from your own phone with the address and code it prints.
Everyone on the team can do this with their own PC, to test and find bugs.
(Owner: lead.)
"""
import base64
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
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


# ---------------------------------------------------------------- team keys ---

TEAM_KEYS_REPO = "Rokasxz/homecall-keys"   # PRIVATE: only invited teammates can read it
TEAM_KEYS = ("ANTHROPIC_API_KEY", "ELEVENLABS_API_KEY")
INVITE = f"https://github.com/{TEAM_KEYS_REPO}/invitations"


def team_keys_text() -> str | None:
    """team.env from the private repo, with this person's GitHub login. None if not allowed (yet)."""
    gh = shutil.which("gh")
    if gh:  # the GitHub app's login
        try:
            r = subprocess.run([gh, "api", f"repos/{TEAM_KEYS_REPO}/contents/team.env", "--jq", ".content"],
                               capture_output=True, text=True, timeout=20)
            if r.returncode == 0 and r.stdout.strip():
                return base64.b64decode(r.stdout).decode("utf-8")
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
    # No gh: the same git login used for this repo. Never let git ask for a password.
    try:
        origin = subprocess.run(["git", "remote", "get-url", "origin"], cwd=ROOT,
                                capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None
    host = re.match(r"(https://(?:[^@/]+@)?github\.com/|git@github\.com:)", origin)
    if not host:
        return None
    url = f"{host.group(1)}{TEAM_KEYS_REPO}.git"   # same login style as this repo (https or ssh)
    quiet = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="never",
                 GIT_SSH_COMMAND="ssh -o BatchMode=yes")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        try:
            r = subprocess.run(["git", "clone", "-q", "--depth", "1", url, str(Path(tmp) / "keys")],
                               env=quiet, capture_output=True, text=True, timeout=40)
            if r.returncode == 0:
                return (Path(tmp) / "keys" / "team.env").read_text(encoding="utf-8")
        except (OSError, subprocess.SubprocessError):
            pass
    return None


def get_team_keys() -> str:
    """Fill in missing team keys from the private repo (no questions). Returns a line for the summary."""
    env = read_env()
    missing = [k for k in TEAM_KEYS if not env.get(k)]
    if not missing:
        return ""
    text = team_keys_text()
    if text is None:
        return (f"no team keys yet: accept the GitHub invite ({INVITE}), "
                "be logged in to GitHub on this computer, then start again")
    got = []
    for line in text.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = (x.strip() for x in line.split("=", 1))
            if k in missing and v:
                set_env(k, v)
                got.append(k)
    return f"got {len(got)} team key(s) from {TEAM_KEYS_REPO}" if got else ""


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
    return ("echo (no AI: repeats what you say). For real AI: accept the GitHub invite "
            f"({INVITE}) and start again")


# -------------------------------------------------------------- permissions ---

def permissions_step() -> str:
    """Mac: ask for every permission NOW, while you're at the PC, so nothing pops up mid-call."""
    if sys.platform != "darwin":
        return "nothing to allow on this system"
    sys.path.insert(0, str(ROOT))
    from pc import permissions  # noqa: E402

    if all(i["ok"] for i in permissions.check(ask=False)):
        return "all allowed"
    app = permissions.starter_app()
    say(f"\nmacOS must allow {app} (it runs HomeCall) to see and control this Mac. Only once.")
    say("Windows will pop up now: click OK / Allow on each one.")
    missing = [i for i in permissions.check(ask=True) if not i["ok"]]
    if missing and sys.stdin.isatty():
        say(f"\nAlmost: in System Settings (opening now), switch ON \"{app}\" under:")
        for i in missing:
            say(f"  - {i['name']}")
        say("If macOS says \"Quit & Reopen\", click it, then start HomeCall again.")
        say("Waiting until they're on... (press Enter to start anyway)")
        missing = wait_for_permissions(permissions, missing)
    if missing:
        names = ", ".join(i["name"].split(" (")[0] for i in missing)
        return f"MISSING: {names}. Fix it in the PC window (http://localhost:{PORT}/pc)"
    return "all allowed"


def wait_for_permissions(permissions, missing: list[dict], limit: float = 600) -> list[dict]:
    """Re-check every few seconds; open the next Settings page as each one is switched on."""
    import select
    shown = None
    t0 = time.time()
    while missing and time.time() - t0 < limit:
        if missing[0]["key"] != shown:
            shown = missing[0]["key"]
            permissions.open_settings(shown)
        ready, _, _ = select.select([sys.stdin], [], [], 3)
        if ready:
            sys.stdin.readline()
            break
        now = {i["key"]: i for i in permissions.check(ask=False, apps=True)}
        for i in missing:
            if now[i["key"]]["ok"]:
                say(f"  OK  {i['name']}")
        missing = [i for i in missing if not now[i["key"]]["ok"]]
    return missing


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
        return None, None, ("This Wi-Fi blocks the tunnel (port 7844). Connect this computer to your "
                            "phone's hotspot (turn off Auto-Join for this Wi-Fi), then start HomeCall again.")
    return None, None, "The tunnel didn't start in 40 s. Check the internet, then start HomeCall again."


# -------------------------------------------------------------------- voice ---

def setup_voice(url: str) -> str:
    """Create or update THIS computer's own ElevenLabs agent so it calls this PC."""
    env = read_env()
    if not env.get("ELEVENLABS_API_KEY"):
        return f"off (no ElevenLabs key yet: accept the GitHub invite {INVITE} and start again)"
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

def start_server(url: str | None, tunnel_note: str = "") -> tuple[subprocess.Popen, str | None]:
    # UTF-8 both ways: Windows' own encoding can't print e.g. "ž" and the server would crash.
    env = dict(os.environ, PYTHONUNBUFFERED="1", PYTHONIOENCODING="utf-8",
               HOMECALL_LOG_LEVEL="info",          # each visit -> homecall.log
               HOMECALL_PUBLIC_URL=url or "",      # for the QR code in the PC window
               HOMECALL_TUNNEL_NOTE=tunnel_note)   # why there's no address, for the PC window
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
    keys_note = get_team_keys()
    env = read_env()
    allowed = permissions_step()

    tunnel, url, tunnel_note = (None, None, "local only (--local)") if local_only else start_tunnel()
    voice = setup_voice(url) if url else "off (needs the tunnel)"
    server, code = start_server(url, tunnel_note)
    if not code:
        say("\nThe app didn't start. Run `python check.py` to see why.")
        if tunnel:
            tunnel.terminate()
        sys.exit(1)

    say("\n" + "=" * 64)
    say("  HomeCall is connected. Keep this window open; Ctrl+C stops it.")
    say("=" * 64)
    if url:
        say(f"  Phone:                      {url}")
        say( "                              (type the code, then choose Voice call or Type)")
    else:
        say(f"  Phone: not reachable. {tunnel_note}")
    say(f"  PC window (QR code):        http://localhost:{PORT}/pc")
    say(f"  Pairing code:               {code}")
    say(f"  Allowed on this PC:         {allowed}")
    say(f"  Brain:  {brain_line(env)}")
    say(f"  Voice:  {voice}")
    if keys_note:
        say(f"  Keys:   {keys_note}")
    say("  Log:    homecall.log (each phone visit; private: never post it)")
    say("  Found a bug? GitHub -> Issues -> New issue -> Bug. Never post the address or code.")
    say("=" * 64 + "\n")
    if "--no-window" not in sys.argv:
        webbrowser.open(f"http://localhost:{PORT}/pc")  # the QR code to scan with the phone

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
