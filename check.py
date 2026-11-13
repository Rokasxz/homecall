"""Does my setup work?  Run from the project root:   python check.py

Checks Python, the libraries, the screen capture, every tool's format, the API
key, the phone files, and finally starts the server and makes a fake phone call.
Read the FAIL lines: fix the ones in your own area, tell the owner about the rest.
"""
import asyncio
import importlib
import inspect
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))
RESULTS = []


def report(status, name, detail=""):
    RESULTS.append(status)
    print(f"  {status:4}  {name}" + (f"  ->  {detail}" if detail else ""))


def ok(name, detail=""): report("PASS", name, detail)
def fail(name, detail=""): report("FAIL", name, detail)
def warn(name, detail=""): report("WARN", name, detail)


def section(title):
    print(f"\n{title}")


def load_dotenv():
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


# ------------------------------------------------------------------ checks ---

def check_python():
    section("Python")
    v = sys.version_info
    (ok if v >= (3, 11) else fail)("Python 3.11 or newer", f"you have {v.major}.{v.minor}")
    inside_venv = sys.prefix != sys.base_prefix
    (ok if inside_venv else warn)("running inside the project's virtual environment",
                                  "" if inside_venv else "activate .venv first (README.md)")


def check_libraries():
    section("Libraries (pip install -r requirements.txt)")
    for mod, pkg in [("fastapi", "fastapi"), ("uvicorn", "uvicorn"), ("mss", "mss"),
                     ("PIL", "pillow"), ("pyautogui", "pyautogui"), ("anthropic", "anthropic"),
                     ("websockets", "uvicorn[standard]")]:
        try:
            importlib.import_module(mod)
            ok(pkg)
        except Exception as e:  # noqa: BLE001
            fail(pkg, f"{type(e).__name__}: {e}")


def check_env():
    section("Settings (.env)")
    load_dotenv()
    mode = os.environ.get("HOMECALL_BRAIN", "").strip().lower() or (
        "api" if os.environ.get("ANTHROPIC_API_KEY") else "echo")
    if mode == "echo":
        warn("Brain mode: echo (no AI)", "fine for Server/Hands/Phone/Voice work")
    else:
        ok(f"Brain mode in your .env: {mode}", "the app uses the real AI; check.py itself tests in echo mode "
           "(fast, free); test the real Brain with team/demo_check.py")
    # Everything below runs the Brain in echo mode: a real AI makes check.py slow,
    # costs credits or Max usage, and can't be judged by a script anyway.
    os.environ["HOMECALL_BRAIN"] = "echo"


def check_screen():
    section("Screen capture (Server & connection)")
    try:
        from pc import screen
        jpg = screen.capture_jpeg()
        if jpg[:2] != b"\xff\xd8":
            fail("capture_jpeg returns a JPEG")
        elif screen.LAST_ERROR:
            warn("screen capture works", f"placeholder image instead: {screen.LAST_ERROR[:80]} (Mac: allow Screen Recording for your terminal)")
        else:
            ok("screen capture works", f"{len(jpg)//1024} KB per frame")
    except Exception as e:  # noqa: BLE001
        fail("pc/screen.py imports and captures", f"{type(e).__name__}: {e}")


def check_tools():
    section("Tools (Hands)")
    try:
        from pc.actions import TOOLS
    except Exception as e:  # noqa: BLE001
        fail("pc/actions imports", f"{type(e).__name__}: {e}")
        return
    if not TOOLS:
        fail("TOOLS list has tools")
        return
    try:
        from anthropic import beta_tool
    except Exception:  # noqa: BLE001
        beta_tool = None
    for f in TOOLS:
        name = f.__name__
        problems = []
        doc = inspect.getdoc(f) or ""
        if not doc:
            problems.append("no docstring")
        sig = inspect.signature(f)
        for p in sig.parameters.values():
            if p.annotation is inspect.Parameter.empty:
                problems.append(f"argument '{p.name}' has no type hint")
            if doc and f"{p.name}:" not in doc:
                problems.append(f"argument '{p.name}' not described under Args:")
        if sig.return_annotation is not str:
            problems.append("should be declared '-> str'")
        if beta_tool and not problems:
            try:
                schema = beta_tool(f).to_dict()
                for p in sig.parameters:
                    if not schema["input_schema"]["properties"].get(p, {}).get("description"):
                        problems.append(f"the AI gets no description for '{p}' (check the Args: line)")
            except Exception as e:  # noqa: BLE001
                problems.append(f"cannot become an AI tool: {type(e).__name__}: {e}")
        (ok if not problems else fail)(f"tool {name}", "; ".join(problems))


def check_brain():
    section("Brain")
    try:
        from pc.brain.agent import Brain
        b = Brain()
        if not callable(getattr(b, "handle", None)):
            fail("Brain has a handle() method")
        else:
            ok("Brain() builds", f"{b.mode} mode")
    except Exception as e:  # noqa: BLE001
        fail("pc/brain/agent.py imports", f"{type(e).__name__}: {e}")


def check_voice():
    section("Voice")
    try:
        from pc.voice import engine, routes  # noqa: F401
        ok("pc/voice imports", "endpoints answer 501 until engine.py is implemented")
    except Exception as e:  # noqa: BLE001
        fail("pc/voice imports", f"{type(e).__name__}: {e}")


def check_phone():
    section("Phone app")
    for f in ["index.html", "app.js", "style.css"]:
        p = ROOT / "phone" / f
        (ok if p.exists() else fail)(f"phone/{f} exists")


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


async def fake_call(port, code):
    import urllib.request
    import websockets

    base = f"http://127.0.0.1:{port}"
    html = urllib.request.urlopen(base + "/").read().decode()
    (ok if "<html" in html.lower() else fail)("phone page is served")
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        await ws.send(json.dumps({"type": "hello", "code": "000000"}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
        (ok if msg.get("type") == "error" else fail)("wrong pairing code is refused")
    async with websockets.connect(f"ws://127.0.0.1:{port}/ws") as ws:
        await ws.send(json.dumps({"type": "hello", "code": code}))
        msg = json.loads(await asyncio.wait_for(ws.recv(), 5))
        (ok if msg.get("type") == "welcome" else fail)("right pairing code is accepted")
        await ws.send(json.dumps({"type": "say", "text": "Say hello in three words."}))
        got_frame = reply = None
        deadline = time.time() + 60
        while time.time() < deadline and (not got_frame or reply is None):
            m = await asyncio.wait_for(ws.recv(), 60)
            if isinstance(m, bytes):
                got_frame = True
            else:
                d = json.loads(m)
                if d.get("type") == "reply":
                    reply = d.get("text", "")
        (ok if got_frame else fail)("live screen frames arrive")
        (ok if reply else fail)("a reply comes back", (reply or "")[:70])
        await ws.send(json.dumps({"type": "hangup"}))


def check_end_to_end():
    section("End to end: start the server and make a fake phone call")
    port, code = free_port(), "424242"
    env = dict(os.environ, HOMECALL_PORT=str(port), HOMECALL_CODE=code)
    proc = subprocess.Popen([sys.executable, "-m", "pc.server"], env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    try:
        import urllib.request
        for _ in range(40):
            if proc.poll() is not None:
                break
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=1)
                break
            except Exception:  # noqa: BLE001
                time.sleep(0.5)
        else:
            fail("server starts", "no answer on /health after 20 s")
            return
        if proc.poll() is not None:
            fail("server starts", (proc.stdout.read() or "")[-400:])
            return
        ok("server starts")
        asyncio.run(fake_call(port, code))
    except Exception as e:  # noqa: BLE001
        fail("fake phone call", f"{type(e).__name__}: {e}")
    finally:
        proc.kill()


def main():
    print("HomeCall setup check")
    check_python()
    check_libraries()
    check_env()
    check_screen()
    check_tools()
    check_brain()
    check_voice()
    check_phone()
    if "FAIL" in RESULTS:
        print("\nSkipping the end-to-end call until the FAILs above are fixed.")
    else:
        check_end_to_end()
    passed, failed, warned = (RESULTS.count(s) for s in ("PASS", "FAIL", "WARN"))
    print(f"\n{passed} passed, {failed} failed, {warned} warnings.")
    print("All good: you can start building." if not failed else
          "Fix the FAIL lines in your area; tell the owner about the others.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
