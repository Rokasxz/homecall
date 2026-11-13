#!/usr/bin/env python3
"""Test one Pull Request in a temporary copy and write the coordinator's comment.  (Owner: lead)

    python team/review_pr.py 3                   run the checks, print the draft comment
    python team/review_pr.py 3 --post            ... and post it on the PR (updates its own earlier comment)
    python team/review_pr.py 3 --post --note "Plain-words advice to add at the top"

Never runs code from a fork or from someone who isn't a collaborator.
Never merges. Your own checkout is not touched (it uses a temporary git worktree).
"""
import argparse
import json
import pathlib
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import status  # noqa: E402  (team/status.py)

REPO = status.REPO
ROOT = pathlib.Path(__file__).resolve().parent.parent


def sh(cmd: list[str], cwd=None, timeout=600) -> tuple[int, str]:
    r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr)


def tail(text: str, n: int = 25) -> str:
    lines = [l for l in text.splitlines() if "DeprecationWarning" not in l]
    return "\n".join(lines[-n:])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("number", type=int)
    ap.add_argument("--post", action="store_true")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    pr = status.gh_json("pr", "view", str(a.number), "--repo", REPO, "--json",
                        "number,title,author,headRefName,headRefOid,isCrossRepository,files,state")
    author, sha, branch = pr["author"]["login"], pr["headRefOid"], pr["headRefName"]
    collaborators = {c["login"] for c in status.gh_json("api", f"repos/{REPO}/collaborators")}
    if pr["isCrossRepository"] or author not in collaborators:
        sys.exit(f"PR #{a.number} is from a fork or a non-collaborator ({author}). Not running its code.")
    if pr["state"] != "OPEN":
        sys.exit(f"PR #{a.number} is {pr['state'].lower()}.")

    files = [f["path"] for f in pr["files"]]
    outside = [f for f in files if f != "TASKS.md" and not status.in_area(author, f)]
    tasks_ok, tasks_note = True, ""
    sh(["git", "fetch", "-q", "origin", branch, "main"], cwd=ROOT)
    if "TASKS.md" in files and "." not in status.PEOPLE.get(author, ("", "", []))[2]:
        tasks_ok, tasks_note = status.tasks_md_edits_ok(author, "origin/main", f"origin/{branch}")

    tmp = pathlib.Path(tempfile.mkdtemp(prefix=f"homecall-pr{a.number}-"))
    wt = tmp / "wt"
    code, out = sh(["git", "worktree", "add", "-q", "--detach", str(wt), sha], cwd=ROOT)
    if code:
        sys.exit("Could not make a temporary copy: " + out)
    try:
        # Test the branch COMBINED with the latest main: two pieces that each work
        # can still break together (research: CooperBench).
        m_code, m_out = sh(["git", "-c", "user.name=coordinator", "-c", "user.email=coordinator@localhost",
                            "merge", "--no-edit", "-q", "origin/main"], cwd=wt)
        conflict_files = []
        if m_code:
            _, names = sh(["git", "diff", "--name-only", "--diff-filter=U"], cwd=wt)
            conflict_files = [n for n in names.splitlines() if n.strip()]
            sh(["git", "merge", "--abort"], cwd=wt)
        python = sys.executable
        if "requirements.txt" in files:  # their branch needs other packages: fresh venv
            sh(["uv", "venv", "-q", str(wt / ".venv")], cwd=wt)
            sh(["uv", "pip", "install", "-q", "--python", str(wt / ".venv/bin/python"), "-r", "requirements.txt"], cwd=wt)
            python = str(wt / ".venv/bin/python")
        c_code, c_out = sh([python, "check.py"], cwd=wt)
        t_code, t_out = sh([python, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider"], cwd=wt)
    finally:
        sh(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT)
        shutil.rmtree(tmp, ignore_errors=True)

    c_last = next((l for l in reversed(c_out.splitlines()) if "passed" in l and "failed" in l), "no summary")
    t_last = next((l for l in reversed(t_out.splitlines()) if l.strip()), "no output")
    tests_ok = t_code in (0, 5)
    area_ok = not outside and tasks_ok
    others = [p for p in status.gh_json("pr", "list", "--repo", REPO, "--state", "open", "--json", "number,author,files")
              if p["number"] != a.number]
    overlaps = sorted({f"#{p['number']} ({p['author']['login']}): `{f['path']}`" for p in others
                       for f in p["files"] if f["path"] in files and f["path"] != "TASKS.md"})
    contract = "CLAUDE.md" in files
    reqs = "requirements.txt" in files
    ok = c_code == 0 and tests_ok and area_ok and not conflict_files

    area_txt = "OK" if area_ok else "PROBLEM: " + "; ".join(filter(None, [
        ("outside your area: " + ", ".join(f"`{f}`" for f in outside)) if outside else "", tasks_note]))
    prefixes = ", ".join(f"`{p}`" for p in status.PEOPLE.get(author, ("", "", ["?"]))[2])
    rows = [
        f"| Combines cleanly with the latest `main` | "
        + ("OK (all checks below ran on your branch + latest main)" if not conflict_files else
           "CONFLICT in " + ", ".join(f"`{f}`" for f in conflict_files)
           + ": tell your AI \"bring my branch up to date with main and resolve the conflict\" (PROMPT I), then push") + " |",
        f"| Files stay in your area ({prefixes}) | {area_txt} |",
        f"| `python check.py` | {'OK' if c_code == 0 else 'FAILED'}: {c_last.strip()} |",
        f"| Tests (`pytest`) | {'OK' if tests_ok else 'FAILED'}: {'no tests yet' if t_code == 5 else t_last.strip()} |",
        f"| Changes the contract (`CLAUDE.md`) | {'YES: the whole team must agree, tell them in the chat' if contract else 'no'} |",
    ]
    if reqs:
        rows.append("| Adds or changes libraries (`requirements.txt`) | YES: needs Rokas's OK |")
    if overlaps:
        rows.append("| Other open PRs change the same files | " + "; ".join(overlaps)
                    + ": merge one first, then the other must update from main |")
    verdict = ("**Safe to merge:** Rokas can press Merge." if ok and not contract and not reqs else
               "**Almost:** checks pass, but Rokas must OK the contract/library change first." if ok else
               "**Fix first:** see the FAILED/PROBLEM lines above. Paste them into your AI with "
               "PROMPT J (\"something is broken\") from TEAMMATE-GUIDE.md, then push again: I re-check automatically.")
    details = ""
    if c_code:
        details += f"\n<details><summary>check.py output (last lines)</summary>\n\n```\n{tail(c_out)}\n```\n</details>\n"
    if not tests_ok:
        details += f"\n<details><summary>pytest output (last lines)</summary>\n\n```\n{tail(t_out)}\n```\n</details>\n"
    body = (f"<!-- {status.MARKER} sha={sha[:12]} -->\n"
            f"**Coordinator check** for commit `{sha[:7]}` (automatic; runs again when you push)\n\n"
            + (a.note.strip() + "\n\n" if a.note.strip() else "")
            + "| Check | Result |\n|---|---|\n" + "\n".join(rows) + "\n\n" + verdict + "\n" + details)
    print(body)
    print(json.dumps({"pr": a.number, "ok": ok, "check_py": c_code, "pytest": t_code,
                      "outside_area": outside, "tasks_md_ok": tasks_ok}), file=sys.stderr)

    if a.post:
        me = status.gh_json("api", "user")["login"]
        existing = [c for c in status.gh_json("api", f"repos/{REPO}/issues/{a.number}/comments")
                    if c["user"]["login"] == me and status.MARKER in c["body"]]
        if existing:
            status.run("gh", "api", "-X", "PATCH", f"repos/{REPO}/issues/comments/{existing[-1]['id']}", "-f", f"body={body}")
            print(f"Updated the coordinator comment on PR #{a.number}.", file=sys.stderr)
        else:
            status.run("gh", "api", f"repos/{REPO}/issues/{a.number}/comments", "-f", f"body={body}")
            print(f"Posted a coordinator comment on PR #{a.number}.", file=sys.stderr)


if __name__ == "__main__":
    main()
