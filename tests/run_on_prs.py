"""Run our tests against main AND every open Pull Request.  Owner: Demo, tests & safety.

    python tests/run_on_prs.py            # summary for main + every open PR
    python tests/run_on_prs.py --json     # same, as JSON (for scripts / the loop)

Each branch is checked out in a temporary folder (git worktree), so nobody's
branch and nothing in your own folder changes. The newest version of each of
our test files is copied in (from your branches if they're not in main yet),
then `pytest tests/` runs there with this project's .venv.
Needs: git, and the GitHub CLI `gh` logged in.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Our test files, and the branches that may have a newer copy than main (last wins).
TEST_FILES = ["test_hands.py", "test_contract.py", "test_safety.py", "test_media.py", "test_power.py", "test_demo_path.py", "test_pointer.py", "test_contract_types.py", "test_extras.py"]
TEST_SOURCES = ["origin/main"]  # + my OPEN PR branches, added at run time (merged ones are stale)
PY = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
GH = shutil.which("gh") or str(Path.home() / ".local/bin/gh")


def sh(*args, cwd=ROOT, check=True) -> str:
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)}: {r.stderr.strip()}")
    return r.stdout


def newest_tests(extra_refs: list[str] = ()) -> dict[str, str]:
    files = {}
    for ref in list(TEST_SOURCES) + list(extra_refs):
        for name in TEST_FILES:
            r = subprocess.run(["git", "show", f"{ref}:tests/{name}"], cwd=ROOT,
                               capture_output=True, text=True)
            if r.returncode == 0:
                files[name] = r.stdout
    return files


def run_tests(ref: str, tests: dict[str, str]) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="homecall-prtest-"))
    wt = tmp / "wt"
    try:
        sh("git", "worktree", "add", "--detach", "-q", str(wt), ref)
        (wt / "tests").mkdir(exist_ok=True)
        for name, text in tests.items():
            (wt / "tests" / name).write_text(text, encoding="utf-8")
        r = subprocess.run([str(PY), "-m", "pytest", "tests", "-q", "-rfEX", "-p", "no:cacheprovider"],
                           cwd=wt, capture_output=True, text=True, timeout=600)
        out = r.stdout + r.stderr
        counts = {k: int(n) for n, k in re.findall(r"(\d+) (passed|failed|error|errors|xfailed|xpassed|skipped)", out.splitlines()[-1] if out.strip() else "")}
        problems = re.findall(r"^(?:FAILED|ERROR) (\S+)", out, re.M)
        fixed = re.findall(r"^XPASS (\S+)", out, re.M)  # a known gap that now works
        strict = re.findall(r"^FAILED (\S+) - \[XPASS\(strict\)\]", out, re.M)  # also fixed
        problems = [p for p in problems if p not in strict]
        fixed += strict
        return {"counts": counts, "problems": problems, "fixed": fixed}
    except Exception as e:  # noqa: BLE001
        return {"counts": {}, "problems": [f"could not run: {e}"], "fixed": []}
    finally:
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=ROOT, capture_output=True)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> None:
    sh("git", "fetch", "-q", "--all", "--prune")
    prs = json.loads(sh(GH, "pr", "list", "--state", "open", "--json",
                        "number,title,author,headRefName,isCrossRepository"))
    me = sh(GH, "api", "user", "--jq", ".login").strip()
    mine = [f"origin/{p['headRefName']}" for p in prs if p["author"]["login"] == me]
    tests = newest_tests(mine)
    targets = [("main", "origin/main", "")]
    for pr in sorted(prs, key=lambda p: p["number"]):
        if pr["isCrossRepository"]:
            continue  # never run code from forks
        targets.append((f"PR {pr['number']}", f"origin/{pr['headRefName']}",
                        f"{pr['author']['login']}: {pr['title']}"))
    results = []
    for label, ref, title in targets:
        res = run_tests(ref, tests)
        results.append({"target": label, "ref": ref, "title": title, **res})
    if "--json" in sys.argv:
        print(json.dumps(results, indent=1))
        return
    for r in results:
        c = r["counts"]
        line = ", ".join(f"{v} {k}" for k, v in c.items()) or "no result"
        mark = "OK " if not r["problems"] else "!! "
        print(f"{mark}{r['target']:<7} {line}   {r['title']}")
        for p in r["problems"]:
            print(f"      - BROKEN {p}")
        for p in r["fixed"]:
            print(f"      + FIXED  {p}")


if __name__ == "__main__":
    main()
