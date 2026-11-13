# Prompts for everyone's AI

Copy, replace the [brackets], paste into Claude Code. The numbers match the
plan in TEAM-SETUP.md (Part 0).

**Why these work:** each one says (1) what you want, (2) what "done" looks like,
(3) what the AI must NOT touch. Vague prompts like "make the start page" make
the AI guess, and guesses are what clash with your teammates' work.

---

## Before you start (once, all together)

**HomeCall: prompts 1-4 are already done.** The idea, MVP, split, contract and
skeleton are in PLAN.md, CLAUDE.md and the code. They stay here for the next
project. Start at prompt 5.

### 1. Find the idea
Use ONE person's AI, with everyone looking at the screen. Any chat works, it
doesn't have to be in the repo.

```
We are [4] people at a [2]-day hackathon. Theme/rules: [paste the theme, judging
criteria, anything required, or "none"]. Skills in the team: [e.g. 2 can code a
bit, 1 designer, 1 loves game logic]. Tools we can use: [e.g. web only, any
language].

Give me 5 ideas that 4 people with AI helpers can really finish in about 16
hours of building. For each:
- one-sentence pitch
- the "wow" moment a judge sees in the first 30 seconds of the demo
- the 3-4 parts it splits into, so each person can work on one part
- the riskiest part (what could stop it from working)
Prefer simple and impressive over big and ambitious.
```

### 2. Cut it down to the smallest version
```
We picked: [idea]. We have [2] days and [4] people. Define the MVP: the smallest
version that still shows the wow moment. List:
1. MUST have (the demo doesn't work without it)
2. NICE to have (only if we have time)
3. CUT (don't build)
Be strict. If the MUST list is more than ~6 items, shrink it.
```

### 3. Split the work and write the contract
```
Idea and MVP: [paste]. Tech: [e.g. Vite + React in the browser]. We are [4]
people. Split this into [4] areas so that people rarely need to edit the same
files. For each area give: a name, a folder, the 3-5 tasks inside it, and what
it needs from other areas.

Then write the "contract": the exact functions, data shapes and file formats
the areas use to talk to each other. Keep it under 30 lines and use concrete
examples. Format it so I can paste it into CLAUDE.md under "How the parts talk
to each other", and the area table under "Who owns what".
```
Paste the result into CLAUDE.md and TASKS.md.

### 4. Lead only: build the skeleton
```
Read CLAUDE.md. Create the project skeleton for [tech]: the folders from the
ownership table, each with a tiny placeholder file, so the app starts and shows
a simple page. Add a README with the exact command to install and run it. Don't
build any real features yet. At the end, run it and tell me it works, then
commit it to main.
```
Everyone else waits until this is pushed.

---

## Everyone, every session

### 5. Kickoff prompt (the most important one: start every session with it)
```
Read CLAUDE.md and TASKS.md first. I'm [name]. I own [area], folder
[src/start-page/]. Today's task: [task from TASKS.md].

Done means: [what I should be able to see or click when it works].

Rules for this session:
- Check you're on the branch feature/[area]-[task]. If not, create it from the
  latest main before editing anything.
- Only edit files inside [my folder]. If you need a change anywhere else (or
  to the contract), STOP and tell me what and why. Don't do it yourself. A
  guard may block edits outside my area: that's intended, don't look for a
  way around it.
- Prefer new files in my folder over editing existing shared files.
- First give me your plan in 3-5 bullets. If it stays inside my folder, start
  right away.
- Work in small steps and tell me how to see each one working.
- Explain changes in plain language.
```

### 6. The task prompt (when you give the AI a new job inside the session)
```
Task: [one specific thing, e.g. "add a Start button that calls startGame()"].
Done when: [what I can see/do].
Edit only: [files/folder].
Don't touch: [everything else, esp. shared files].
Example: [what the result should look like or do, 1-2 lines].
Run it after and tell me if it works.
```
One task per prompt. Five small prompts beat one giant one.

### 7. Sync with the team (start of session, or after a teammate merges)
```
Bring my branch up to date with the latest main (git pull origin main). Then
tell me in plain language what changed that affects my area, and whether
anything of mine broke. Don't fix anything yet, just report.
```

### 8. Don't wait for a teammate: make a fake stand-in
```
My task needs [mechanics' startGame(settings)], which [name] hasn't built yet.
Using the contract in CLAUDE.md, create a FAKE version of it that returns
simple made-up data in the right shape, so I can keep working. Put it in my
own folder, name it clearly (e.g. fakeMechanics.js), and make it easy to
swap for the real one later. List what to change when the real one is merged.
```

### 9. Before you open a Pull Request
```
Check my branch against main before I open a Pull Request:
1. List the files I changed. Are they ALL inside [my folder]? Flag any that aren't.
2. Is there leftover debug code, console.logs, or commented-out junk?
3. Run python check.py and the app: does it start, and does my feature work as described?
4. Did I change the contract in CLAUDE.md? If so, remind me to tell the team.
Then write a short Pull Request description in plain words.
```

### 9b. After merges: do the pieces still fit together?
Whoever merged last (and again every evening) runs this on a fresh `main`.
Each branch can work alone and the combination still fail, and git won't warn you.
```
Pull the latest main. Several people's branches were just merged: [list]. Check
that the pieces fit TOGETHER, using the contract in CLAUDE.md:
1. Do the function names, arguments and data fields that one area calls match
   what the other area really provides?
2. Does any name mean different things in different areas (e.g. two "score"
   fields)? Is the same helper written twice in different places?
3. Run the app along the demo path: [steps]. What breaks?
List every mismatch with file and line, most serious first. Don't fix anything
yet. Tell me which area owner should fix each one.
```

---

## When things go wrong

### Something is broken
```
[Describe what you did and what you saw, paste the error.] Find the cause
BEFORE changing anything and explain it in plain words. Then make the smallest
fix that works. Only edit files inside [my folder]; if the cause is somewhere
else, tell me instead of fixing it.
```

### Merge conflict
```
I have a merge conflict. For each conflicting file: show me what both sides
changed, tell me which you'd keep and why, and wait for my OK before
resolving. After resolving, run the app to check it still works.
```

---

## The end

### 10. Feature freeze and demo
Do it ~3-4 hours before the deadline. Run it on the person who has the most
complete `main`.
```
Feature freeze: no new features from now on. Go through the app as a judge
would, along the happy path of the demo: [steps]. List anything broken,
confusing or ugly, ordered by how much it would hurt the demo. Then write a
2-minute demo script: opening line, the 4-5 clicks that show the wow moment,
and a closing line. Don't fix anything yet, just list.
```
Then split the list between people (one area each, same rules as before).

---

## Tips

- Everyone's AI reads the same CLAUDE.md, so **update it when plans change**
  (area moves, contract change). Outdated rules are worse than none.
- Start each new task in a fresh Claude Code session. Long chats get confused.
- If the AI says "I'll also quickly fix X in another folder": say no. Add it to
  TASKS.md for its owner.
- Run the app after every small step. Don't pile up 2 hours of untested changes.
- Commit when something works, even if it's tiny. That's your undo button.
- Want TWO Claude sessions of your own at once (say UI + a bug)? Don't open the
  same folder twice. Start the second with `claude --worktree <name>`: it gets
  its own copy and branch. (Create `.claude/my-area` in it too.)
- Anything the whole team needs to know goes in CLAUDE.md, through a Pull
  Request. Your own Claude's memory stays on your computer; teammates' AIs
  never see it.
