---
name: status
description: Report where the product pipeline stands without changing anything. Read-only — shows every stage, what passed, what is being revised, what is blocked, and what the next step would be.
---

# Status

Report where the project stands. **Change nothing.** No agents dispatched, no files written,
no work performed. If the owner wants the pipeline to move, that is `/advance`.

## Gather

```bash
python3 scripts/frontier.py .
```

Then read the artifacts the frontier names, so you can report substance rather than
filenames — the current stage's artifact, its critique, and its verdict if they exist.

Where the project uses GitHub as its work queue, add:

```bash
gh issue list --state open --json number,title,labels
```

## Report

Lead with the answer to the question actually being asked: **where are we, and what is
holding it up.** Then, briefly:

- Which stage is live, and whether it is being generated, critiqued, judged, or revised —
  with the round number and budget if it is in revision.
- The last verdict, and the substance of why. "The judge failed it because the persona table
  was scored as settled while the sharing model underneath it was not" is useful. "REVISE"
  is not.
- Anything waiting on the owner, and what would happen if he never answers.
- What the next `/advance` will do.

Keep it short. This is a glance, not a report — if the owner wants the full reasoning it is
already on disk in the artifacts, and you should say where rather than reproducing it.

Do not editorialise about whether the project is going well, and do not propose next steps
beyond naming the mechanical next action. The owner asked where things stand.
