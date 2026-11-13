#!/usr/bin/env python3
"""Team status facts for the coordinator.  (Owner: lead)

    python team/status.py            markdown report: PRs, branches, people, main health
    python team/status.py --json     the same facts as JSON (for scripts)

Read-only: uses `gh` and `git`, changes nothing. Run from the project root.
"""
import json
import re
import subprocess
import sys
from datetime import datetime, timezone

REPO = "Rokasxz/homecall"
MARKER = "homecall-coordinator"  # hidden tag in the coordinator's own PR comments

# login -> (display name, area, path prefixes). "." = everything (the lead).
# Keep in sync with "Who owns what" in CLAUDE.md.
PEOPLE = {
    "Rokasxz": ("Rokas", "Lead + Brain + Server & connection", ["."]),
    "mantas1001": ("Mantas", "Hands", ["pc/actions/"]),
    "Matuuunej": ("Matuuunej", "Phone app", ["phone/"]),
    "Nexurent": ("Nexurent", "Voice", ["pc/voice/"]),
    "nojuzaid-spec": ("nojuzaid-spec", "Demo, tests & safety", ["tests/", "demo/"]),
}
# The first word of each person's "## ..." heading in TASKS.md.
TASKS_HEADING = {"Rokas": "Rokasxz", "Mantas": "mantas1001", "Matuuunej": "Matuuunej",
                 "Nexurent": "Nexurent", "nojuzaid-spec": "nojuzaid-spec"}


def run(*cmd: str, check: bool = True) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f"{' '.join(cmd)} failed: {r.stderr.strip()[:300]}")
    return r.stdout


def gh_json(*args: str):
    return json.loads(run("gh", *args) or "null")


def ago(iso: str | None) -> str:
    if not iso:
        return "never"
    t = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    mins = int((datetime.now(timezone.utc) - t).total_seconds() // 60)
    return f"{mins} min ago" if mins < 90 else f"{mins // 60} h {mins % 60} min ago"


def section_owner_by_line(text: str) -> list[str | None]:
    """For each line of TASKS.md (1-based index -> owner login or None)."""
    owners, current = [None], None
    for line in text.splitlines():
        if line.startswith("## "):
            first = line[3:].split(":")[0].split(",")[0].strip()
            current = TASKS_HEADING.get(first)
        owners.append(current)
    return owners


def tasks_md_edits_ok(author: str, base: str, head: str) -> tuple[bool, str]:
    """Did the author only change their own section of TASKS.md?"""
    diff = run("git", "diff", "-U0", f"{base}...{head}", "--", "TASKS.md", check=False)
    head_txt = run("git", "show", f"{head}:TASKS.md", check=False)
    base_txt = run("git", "show", f"{base}:TASKS.md", check=False)
    new_owner, old_owner = section_owner_by_line(head_txt), section_owner_by_line(base_txt)
    bad = set()
    for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", diff, re.M):
        o_start, o_len, n_start, n_len = (int(m.group(1)), int(m.group(2) or 1),
                                          int(m.group(3)), int(m.group(4) or 1))
        for i in range(n_start, n_start + n_len):
            if n_len and i < len(new_owner) and new_owner[i] != author:
                bad.add(new_owner[i] or "shared part")
        for i in range(o_start, o_start + o_len):
            if o_len and i < len(old_owner) and old_owner[i] != author:
                bad.add(old_owner[i] or "shared part")
    if not bad:
        return True, ""
    return False, "TASKS.md: also edits the section(s) of " + ", ".join(sorted(bad))


def in_area(author: str, path: str) -> bool:
    prefixes = PEOPLE.get(author, ("", "", []))[2]
    return "." in prefixes or any(path == p.rstrip("/") or path.startswith(p) for p in prefixes)


def collect() -> dict:
    run("git", "fetch", "-q", "--prune", "origin")
    collaborators = {c["login"] for c in gh_json("api", f"repos/{REPO}/collaborators")}
    prs = gh_json("pr", "list", "--repo", REPO, "--state", "open", "--json",
                  "number,title,author,headRefName,headRefOid,isCrossRepository,mergeable,"
                  "files,statusCheckRollup,updatedAt,url")
    out_prs = []
    for pr in prs:
        author = pr["author"]["login"]
        head = f"origin/{pr['headRefName']}"
        files = [f["path"] for f in pr["files"]]
        outside = [f for f in files if f != "TASKS.md" and not in_area(author, f)]
        tasks_ok, tasks_note = (True, "")
        if "TASKS.md" in files and "." not in PEOPLE.get(author, ("", "", []))[2] and not pr["isCrossRepository"]:
            tasks_ok, tasks_note = tasks_md_edits_ok(author, "origin/main", head)
        checks = pr.get("statusCheckRollup") or []
        if not checks:
            ci = "no checks yet"
        elif any(c.get("status") not in (None, "COMPLETED") for c in checks):
            ci = "running"
        elif all(c.get("conclusion") in ("SUCCESS", "SKIPPED", "NEUTRAL") for c in checks):
            ci = "passed"
        else:
            ci = "FAILED"
        reviewed_sha = None
        for c in gh_json("api", f"repos/{REPO}/issues/{pr['number']}/comments"):
            m = re.search(MARKER + r" sha=([0-9a-f]{7,40})", c.get("body", ""))
            if m:
                reviewed_sha = m.group(1)
        out_prs.append({
            "number": pr["number"], "title": pr["title"], "url": pr["url"], "author": author,
            "branch": pr["headRefName"], "head_sha": pr["headRefOid"],
            "safe_to_test": (not pr["isCrossRepository"]) and author in collaborators,
            "files": files, "outside_area": outside, "tasks_md_ok": tasks_ok, "tasks_md_note": tasks_note,
            "contract_changed": "CLAUDE.md" in files, "requirements_changed": "requirements.txt" in files,
            "ci": ci, "mergeable": pr["mergeable"], "updated": pr["updatedAt"],
            "needs_review": reviewed_sha is None or not pr["headRefOid"].startswith(reviewed_sha),
        })

    seen: dict[str, list[int]] = {}
    for p in out_prs:
        for f in p["files"]:
            if f != "TASKS.md":
                seen.setdefault(f, []).append(p["number"])
    for p in out_prs:
        p["overlaps"] = sorted({n for f in p["files"] for n in seen.get(f, []) if n != p["number"]})

    pr_branches = {p["branch"] for p in out_prs}
    branches = []
    refs = run("git", "for-each-ref", "refs/remotes/origin", "--format=%(refname:short)|%(objectname)|%(committerdate:iso-strict)")
    for line in refs.splitlines():
        ref, sha, date = line.split("|")
        name = ref.removeprefix("origin/")
        if name in ("main", "HEAD", "origin") or name in pr_branches:
            continue
        login = (gh_json("api", f"repos/{REPO}/commits/{sha}").get("author") or {}).get("login")
        branches.append({"branch": name, "author": login, "date": date})

    tasks = run("git", "show", "origin/main:TASKS.md")
    owners = section_owner_by_line(tasks)
    people = {login: {"name": n, "area": a, "done": 0, "total": 0, "needs": [], "last_activity": None,
                      "open_prs": [], "branches_without_pr": []} for login, (n, a, _) in PEOPLE.items()}
    for i, line in enumerate(tasks.splitlines(), start=1):
        who = owners[i]
        if who not in people:
            continue
        if re.match(r"\s*- \[[ xX]\]", line):
            people[who]["total"] += 1
            people[who]["done"] += line.strip().startswith(("- [x]", "- [X]"))
        if line.startswith("Needs from others:") or line.startswith("- ") and "(Mantas)" in line:
            people[who]["needs"].append(line.strip())
    for p in out_prs:
        if p["author"] in people:
            people[p["author"]]["open_prs"].append(p["number"])
            last = people[p["author"]]["last_activity"]
            people[p["author"]]["last_activity"] = max(filter(None, [last, p["updated"]]))
    for b in branches:
        if b["author"] in people:
            people[b["author"]]["branches_without_pr"].append(b["branch"])
            last = people[b["author"]]["last_activity"]
            people[b["author"]]["last_activity"] = max(filter(None, [last, b["date"]]))
    merged = gh_json("pr", "list", "--repo", REPO, "--state", "merged", "--limit", "100", "--json", "number,title,author,mergedAt")
    for m in merged:
        login = m["author"]["login"]
        if login in people:
            people[login].setdefault("merged", []).append(f"#{m['number']} {m['title']}")
            last = people[login]["last_activity"]
            people[login]["last_activity"] = max(filter(None, [last, m["mergedAt"]]))

    runs = gh_json("run", "list", "--repo", REPO, "--branch", "main", "--limit", "1",
                   "--json", "conclusion,status,headSha,url") or []
    main_ci = runs[0] if runs else None
    return {"prs": out_prs, "branches_without_pr": branches, "people": people, "main_ci": main_ci,
            "generated": datetime.now(timezone.utc).isoformat(timespec="minutes")}


def markdown(f: dict) -> str:
    L = [f"# Team facts ({f['generated']} UTC)", ""]
    mc = f["main_ci"]
    L.append(f"**main:** " + (f"checks {mc['conclusion'] or mc['status']} ({mc['url']})" if mc else "no checks run yet"))
    L += ["", "## Open Pull Requests"]
    if not f["prs"]:
        L.append("none")
    for p in f["prs"]:
        flags = []
        if not p["safe_to_test"]:
            flags.append("DO NOT RUN (fork or non-collaborator)")
        if p["outside_area"]:
            flags.append("files outside area: " + ", ".join(p["outside_area"]))
        if not p["tasks_md_ok"]:
            flags.append(p["tasks_md_note"])
        if p["contract_changed"]:
            flags.append("changes the contract (CLAUDE.md)")
        if p["requirements_changed"]:
            flags.append("changes requirements.txt (needs lead OK)")
        if p.get("overlaps"):
            flags.append("same files as " + ", ".join(f"#{n}" for n in p["overlaps"]))
        L.append(f"- #{p['number']} {p['title']} by {p['author']} ({p['branch']}): CI {p['ci']}, "
                 f"{p['mergeable'].lower()}, updated {ago(p['updated'])}, "
                 f"{'NEEDS REVIEW' if p['needs_review'] else 'reviewed at this commit'}"
                 + ("; " + "; ".join(flags) if flags else "; files OK"))
    L += ["", "## Branches pushed without a Pull Request"]
    L += [f"- {b['branch']} by {b['author']} ({ago(b['date'])})" for b in f["branches_without_pr"]] or ["none"]
    L += ["", "## People", "| Who | Area | Tasks done | Open PRs | Merged | Last activity | Needs from others |", "|---|---|---|---|---|---|---|"]
    for login, p in f["people"].items():
        needs = " / ".join(n.replace("|", "/") for n in p["needs"])[:160]
        L.append(f"| {p['name']} ({login}) | {p['area']} | {p['done']}/{p['total']} | "
                 f"{', '.join('#' + str(n) for n in p['open_prs']) or '-'} | {len(p.get('merged', []))} | "
                 f"{ago(p['last_activity'])} | {needs or '-'} |")
    return "\n".join(L)


if __name__ == "__main__":
    facts = collect()
    print(json.dumps(facts, indent=2) if "--json" in sys.argv else markdown(facts))
