#!/usr/bin/env python3
"""CI check: does a Pull Request only change files in its author's area?  (Owner: lead)

    python team/check_area.py --author mantas1001 --base <sha> --head <sha>

Runs on GitHub for every PR (see .github/workflows/check.yml), so it also
catches edits made by hand, by Codex, or by shell commands, and works while
the lead's laptop is asleep. A person may also edit their own TASKS.md section.
Exit code 1 = a file is outside the area. Uses only git (no gh, no network).
"""
import argparse
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import status  # noqa: E402  (areas and the TASKS.md section check live there)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--author", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--head", required=True)
    a = ap.parse_args()

    if a.author not in status.PEOPLE:
        print(f"{a.author} is not in the team list (team/status.py PEOPLE); the lead reviews this PR by hand.")
        sys.exit(1)
    name, area, prefixes = status.PEOPLE[a.author]
    # -z: names end with a zero byte, so "Meeting notes - READ ME.txt" or "ąčę.txt" stay one name each.
    files = [f for f in subprocess.run(["git", "diff", "--name-only", "-z", f"{a.base}...{a.head}"],
                                       capture_output=True, text=True, check=True).stdout.split("\0") if f]
    outside = [f for f in files if f != "TASKS.md" and not status.in_area(a.author, f)]
    tasks_ok, note = True, ""
    if "TASKS.md" in files and "." not in prefixes:
        tasks_ok, note = status.tasks_md_edits_ok(a.author, a.base, a.head)

    print(f"{name} ({a.author}), area {area}: {', '.join(prefixes)}")
    print(f"Changed files: {len(files)}")
    if not outside and tasks_ok:
        print("OK: every change is inside the area.")
        return
    for f in outside:
        print(f"OUTSIDE YOUR AREA: {f}")
    if note:
        print(note)
    print("\nWhat to do: undo those changes on your branch (ask your AI: \"undo my changes to <file>\"),"
          " or, if the owner agreed, ask them to make the change. Then push again.")
    sys.exit(1)


if __name__ == "__main__":
    main()
