#!/usr/bin/env python3
"""Team roster from GitHub.  (Owner: lead)

Teammates comment on the "Join the team" issue with a line like
    AREA: 3 (2nd choice: 2) | AI: Codex | PHONE: Android | PC: Windows
This script reads those comments and:

    python team/invite.py             show who joined and which area each one gets
    python team/invite.py --invite    also add them as collaborators (push access)
    python team/invite.py --assign    also write their names into CLAUDE.md and TASKS.md

Needs the GitHub CLI logged in (gh auth status). Run from the project root.
"""
import json
import pathlib
import re
import subprocess
import sys

REPO = "Rokasxz/homecall"
ISSUE = 1
AREAS = {1: ("Server & connection", "pc/server.py, pc/screen.py, pc/session.py"),
         2: ("Hands", "pc/actions/"), 3: ("Brain", "pc/brain/"),
         4: ("Phone app", "phone/"), 5: ("Voice", "pc/voice/"),
         6: ("Demo, tests & safety", "tests/, demo/")}
ROOT = pathlib.Path(__file__).resolve().parent.parent


def gh(*args: str) -> str:
    r = subprocess.run(["gh", *args], capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"gh {' '.join(args)} failed:\n{r.stderr.strip()}\nIs the GitHub CLI logged in? (gh auth status)")
    return r.stdout


def api(path: str, *extra: str):
    return json.loads(gh("api", path, *extra))


def grab(pattern: str, text: str) -> str | None:
    m = re.search(pattern, text, re.I)
    return m.group(1).strip() if m else None


def main() -> None:
    do_invite, do_assign = "--invite" in sys.argv, "--assign" in sys.argv
    owner = api("user")
    owner_login, owner_name = owner["login"], owner.get("name") or owner["login"]

    people: dict[str, dict] = {}  # login -> info, in order of first comment
    for c in api(f"repos/{REPO}/issues/{ISSUE}/comments"):
        login, body = c["user"]["login"], c["body"]
        if login == owner_login:
            continue
        first = grab(r"AREA:\s*(\d)", body)
        if not first:
            continue  # not a join line
        info = people.setdefault(login, {"login": login})
        info.update({
            "first": int(first),
            "second": int(grab(r"2nd[^0-9]*(\d)", body) or 0) or None,
            "ai": grab(r"AI(?: TOOL)?:\s*([^|\n]+)", body),
            "phone": grab(r"PHONE:\s*([^|\n]+)", body),
            "pc": grab(r"PC:\s*([^|\n]+)", body),
        })

    if not people:
        print(f"No join comments yet on https://github.com/{REPO}/issues/{ISSUE}")
        return

    taken = {1: owner_login}
    for info in people.values():
        info["name"] = api(f"users/{info['login']}").get("name") or info["login"]
        choice = None
        for want in (info["first"], info["second"]):
            if want in AREAS and want != 1 and want not in taken:
                choice = want
                break
        info["area"] = choice
        if choice:
            taken[choice] = info["login"]

    print(f"{'GitHub':18} {'Name':22} {'Area':24} {'AI':12} {'Phone':9} PC")
    print(f"{owner_login:18} {owner_name:22} {'1 Server & connection':24} {'':12} {'':9} (lead)")
    for info in people.values():
        area = f"{info['area']} {AREAS[info['area']][0]}" if info["area"] else f"NONE (wanted {info['first']}, {info['second']})"
        print(f"{info['login']:18} {info['name'][:22]:22} {area:24} {(info['ai'] or '?')[:12]:12} {(info['phone'] or '?')[:9]:9} {info['pc'] or '?'}")
    free = [f"{n} {AREAS[n][0]}" for n in AREAS if n not in taken]
    if free:
        print("Still free:", ", ".join(free))

    if do_invite:
        print("\nInviting as collaborators (push access):")
        for login in people:
            r = subprocess.run(["gh", "api", "-X", "PUT", f"repos/{REPO}/collaborators/{login}",
                                "-f", "permission=push"], capture_output=True, text=True)
            print(f"  {login}: {'invited (they must accept the email)' if r.returncode == 0 else 'failed: ' + r.stderr.strip()[:120]}")

    if do_assign:
        print("\nWriting names into CLAUDE.md and TASKS.md:")
        names = {1: owner_name}
        names.update({info["area"]: info["name"] for info in people.values() if info["area"]})
        for fname in ("CLAUDE.md", "TASKS.md"):
            path = ROOT / fname
            text = path.read_text()
            for n, name in names.items():
                text = text.replace(f"[Name {n}]", name)
            path.write_text(text)
            print(f"  {fname}: {', '.join(f'[Name {n}] -> {name}' for n, name in names.items())}")
        print("Now: git add CLAUDE.md TASKS.md && git commit -m 'Add team names' && git push")
        print("Then send each person their area, e.g.:")
        for info in people.values():
            if info["area"]:
                print(f"  {info['name']}: {AREAS[info['area']][0]} -> {AREAS[info['area']][1]}")


if __name__ == "__main__":
    main()
