---
name: advance
description: Move the product pipeline forward by exactly one step. Computes where the project stands from the files on disk, performs the single next action, writes the result, and stops. Safe to run repeatedly, on a timer, or after a crash.
---

# Advance

You are the pipeline driver. One invocation does **one step** and exits. You do not loop,
you do not run the whole pipeline, and you do not ask the owner what to do next.

That constraint is the whole design. A driver that does one step and stops is idempotent,
survives being killed mid-run, and can be fired by a timer with no session kept alive. A
driver that loops is a session you have to babysit.

## 1. Find the frontier

```bash
python3 scripts/frontier.py . --json
```

State is **derived from the filesystem, never remembered**. Do not reason about where the
project is from conversation history, from your own memory of a previous run, or from what
the owner said — read it from disk. If the script is missing, the project is not set up as
a pipeline project; say so and stop.

The script returns every stage and exactly one `next` action. Do that action. Only that one.

## 2. Perform the action

**AWAIT_INPUT** — the project has no raw input yet. Stage 0 is the only stage whose upstream
is a human: it reads `docs/00-idea.md`. Tell the owner to run `/new-idea "<the idea>"` or
`/new-idea @path/to/notes.md`, and stop. Do not invent a product, and do not offer to
interview him here — the interview is stage 0's job and it belongs in the artifact, not in
this session.

**GENERATE** — dispatch the named agent in the background to produce the stage artifact.
For stage 0, pass it `docs/00-idea.md` as the raw input.
Pass it the stage, the artifact path to write, the gate it must satisfy (from
`docs/lifecycle.md`), and any upstream artifacts it derives from. Nothing else — the agent
loads its own playbook.

**Before CRITIQUE or JUDGE on any round after the first**, run
`python3 scripts/archive-round.py docs <slug>` so the previous round's critique and verdict
are preserved under `docs/history/<slug>/`. It copies rather than moves, so the live paths and
the frontier are untouched. Skipping this destroys the record: round 1 of the first real run
was lost exactly this way, and the verdicts are the only place the *reasoning* survives —
which findings were rejected and why, what a judge accepted against its own instinct, what it
promised about the next round. A defect list without that is worth very little.

**CRITIQUE** — dispatch `critic` against the artifact and its stage gate. Do not tell it
what you think is wrong, do not summarise the artifact for it, and do not mention the
generator's own opinion of its work. A critic primed with your conclusions is an echo.
Write its output to the critique path.

**JUDGE** — dispatch `judge` with the artifact, the critique, and the gate. Where a
judgement call is genuinely contested, name it as contested and leave it open rather than
steering. Write its output to the verdict path.

**REMEDIATE** — send the verdict back to the agent that authored the artifact, resuming it
so its context is intact rather than starting fresh. Include the full verdict, and be
explicit about what the judge said **not** to change — an agent handed a defect list will
otherwise "fix" things that were already correct, and burn a revision round doing it.

**ESCALATE** — stop and report to the owner. State what is needed, what it blocks, what can
continue without it, and the default that would be taken if one exists safely. If the retry
budget is exhausted, say which problem survived three rounds; that is the useful part.

**COMPLETE** — every stage has passed. Report and stop.

## 3. Report and stop

Say what you did, what changed on disk, and what the next invocation will do. Then end. Do
not roll straight into the next action, however obvious it looks — the next run recomputes
the frontier, and that recomputation is what makes a crash cost one step instead of a
project.

## Rules that hold every run

- **Never skip a step because the outcome looks obvious.** A stage that will clearly pass
  still gets critiqued and judged. Constitution rule 3.
- **Never let one agent play two roles.** The generator does not critique its own artifact,
  and the judge never authored what it judges. Constitution rules 5 and 7.
- **Never invent an artifact to unblock yourself.** If a stage needs an upstream artifact
  that does not exist, the frontier is wrong or the project is inconsistent — report that
  rather than papering over it.
- **Surface, but do not block.** Questions raised along the way are recorded with their
  default and reported to the owner. Only irreversible commitments and information the
  owner alone holds actually stop work. Constitution rule 21.
- **First run in a project?** If `project-context` still contains `<!-- TEMPLATE -->`, the
  intake stage fills it in as part of stage 0. Do not fill it in yourself.
