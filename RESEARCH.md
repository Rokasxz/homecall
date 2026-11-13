# Why this setup: what existing teams and guides say

Short version of the research behind CLAUDE.md, the guard and the prompts.
Most sources are practitioner blogs and community guides, not controlled
studies, so read the claims as "what people who tried it report".

## What nearly every source agrees on
1. **Give each person/AI its own copy of the code** (its own clone, or a git
   worktree) on its own branch. This stops silent overwriting. It does NOT stop
   real conflicts: if two people change the same lines they still clash at
   merge time, just visibly.
2. **Decide who owns which files BEFORE anyone starts.** This is the most
   repeated advice. Split along natural lines (start page, mechanics, UI,
   data). Two owners for the same area is the worst setup.
3. **Write the rules into the repo** (CLAUDE.md), so every AI reads the same
   rules. Official docs add two warnings: CLAUDE.md is guidance, not
   enforcement, and long files get followed less well (aim for under 200 lines).
4. **Keep branches short-lived and merge often.** Long-lived branches drift
   away from `main` and cause most conflicts. Pull `main` into your branch
   before you open a Pull Request.

## The part people miss: "semantic conflicts"
Git only sees text. One write-up of multi-agent coordination lists what git
does NOT catch: two AIs adding same-named fields with different meanings,
competing patterns that both compile, duplicated helpers with different
signatures, and lockfile/migration collisions. Its fixes, which we adopted:
- **Contract first**: agree on the shared functions and data shapes before
  anyone builds (CLAUDE.md "contract", prompt 3).
- **Additive only**: new things go in new files; dependency changes only by one
  person (CLAUDE.md rules).
- **Merge order**: first finished merges first; the others pull `main` early.
- **Check the combination**, not only each branch (prompt 9b).
- **Human coordinator** beats AIs negotiating with each other: that's the
  project lead plus TASKS.md.

## Real examples found
- **12 AI instances, one author** (dev.to): fixed worktree names, each instance
  owns specific paths, `git pull --rebase origin main` before every push. Even
  so they still hit rebase conflicts 1-2 times a month, and lost work once when
  auto-named worktrees were cleaned up. Lesson: ownership reduces clashes, it
  doesn't remove them; use stable names.
- **Several humans, each with Claude Code** (community team guide): one person
  advances a given work unit at a time, coordinate through git (not by sharing
  sessions), CLAUDE.md changes go through Pull Requests, personal preferences
  go in a gitignored CLAUDE.local.md, and anything the team needs must be in
  CLAUDE.md because each person's AI memory is private.
- **Tools that enforce single-writer ownership** exist (e.g. "Claude Burst");
  we do the same cheaply with the guard hook.

## What we turned into rules or files here
| Finding | Where it lives |
|---|---|
| One owner per area | CLAUDE.md table, TASKS.md |
| Rules are only suggestions to the AI | `.claude/hooks/stay-in-my-area.sh` blocks edits outside your area |
| Contract before building | PROMPTS.md prompt 3, CLAUDE.md contract |
| New files over editing shared ones | CLAUDE.md rules |
| Short branches, merge every 1-2 hours | CLAUDE.md workflow, TEAM-SETUP Part 0 |
| Pieces can pass alone and fail together | PROMPTS.md prompt 9b, evening check |
| Team knowledge must be in the repo | CLAUDE.md workflow |
| Parallel sessions of one person | `claude --worktree <name>` (PROMPTS.md tips) |

## Honest limits
- The guard only watches Claude's Edit/Write tools. A shell command like
  `sed -i` can still change a file, and a person can edit `.claude/my-area`.
  It catches accidents, not sabotage.
- Nothing here removes the need to talk to each other. Keep a call or chat open.

## Sources
Opened and read:
- Claude Code docs: [worktrees / common workflows](https://code.claude.com/docs/en/common-workflows),
  [memory and CLAUDE.md](https://code.claude.com/docs/en/memory),
  [hooks guide](https://code.claude.com/docs/en/hooks-guide)
- [Multi-agent coordination problem: concurrent agents and semantic conflicts](https://codex.danielvaughan.com/2026/06/06/multi-agent-coordination-problem-concurrent-agents-semantic-conflicts-codex-cli/)
- [Claude Code Team Collaboration Guide](https://claude-collab-guide.pages.dev/)
- [12 AI instances, zero file conflicts](https://dev.to/kanta13jp1/12-ai-instances-zero-file-conflicts-how-git-worktrees-make-it-work-c8b)

Only seen as search results (not opened):
- [Avoid merge conflicts (Mergify)](https://blog.mergify.com/avoid-merge-conflicts)
- [Git for hackathon hackers](https://lpan.io/git-for-hackathon-hackers/)
- [Git worktrees for parallel AI coding agents (MindStudio)](https://www.mindstudio.ai/blog/git-worktrees-parallel-ai-coding-agents)
- [How to keep multiple coding agents from overwriting each other](https://davidloor.com/en/blog/how-to-keep-multiple-coding-agents-from-overwriting-each-other)
