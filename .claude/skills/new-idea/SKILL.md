---
name: new-idea
description: Start a new product from a raw idea or a client conversation. Takes text inline or a file path, records it verbatim as the project's primary source, and kicks off stage 0 — research, a drafted brief, and the questions that come back to the owner.
---

# New idea

The front door. Everything the pipeline eventually builds traces back to what this command
captures, so capture it faithfully and then get out of the way.

Usage the owner will type:

```
/new-idea "a tool that lets physiotherapists bill per session"
/new-idea @notes/client-call-2026-08-17.md
/new-idea @transcript.txt
```

## 1. Resolve the input

The argument is either literal text or a path to a file. Some clients paste a whole
transcript; some give you a sentence.

- Strip a leading `@` if present, then check whether what remains is a readable path. If it
  is, read the file. If it is not, treat the argument as literal text.
- If the argument is empty, ask the owner for the idea in one line and stop. Do not invent
  a product to get started.

## 2. Record it verbatim

Write `docs/00-idea.md`. Create `docs/` if the project does not have it yet.

**Do not edit, summarise, tidy, expand, or "clarify" the input.** This file is the only
`[client]` material the entire pipeline will ever have; every downstream stage tags its
provenance against it, and a sentence you smoothed out becomes an owner statement nobody
made. Messy input is data — a client who contradicts themselves twice in a transcript has
told you something, and cleaning it up destroys it.

```markdown
# Raw input

**Source:** own idea | client conversation — <who, if named>
**Captured:** <date>
**Origin:** typed inline | file `<path>`

---

<the input, exactly as supplied>
```

If `docs/00-idea.md` already exists, do not overwrite it. Either the client has sent more
material — in which case append it under a dated `## Additional input` heading, since later
context is as primary as the first — or this is a second product, which needs its own
directory. Ask which, in one line.

## 3. Establish the entry mode

Stage 0 behaves differently depending on where the idea came from, so settle this before
dispatching:

- **Client-sourced** — the analyst triages what the client *said* from what we *inferred*,
  and keeps a running list of questions to take back to them. That list is often the most
  valuable thing the stage produces.
- **Own idea** — nobody in the room will push back, so the analyst must. It argues against
  the idea on its merits before writing anything down.

Usually the input makes this obvious. When it genuinely does not, ask — it is one question
and it changes how the whole stage runs.

## 4. Check the project is set up

The pipeline needs `scripts/frontier.py`, `schemas/`, and the stage docs. If they are
missing, copy them from the template this project was installed from and say so. If
`project-context` still contains `<!-- TEMPLATE -->`, leave it — stage 0 fills it in.

## 5. Start stage 0

Dispatch `product-analyst` in the background with the entry mode, the path to
`docs/00-idea.md`, and the instruction to write `docs/00-brief.md`. It loads its own
playbook; do not restate the intake process to it or tell it what you think the product is.

Then tell the owner what happens next, and be accurate about the shape of it: the analyst
researches prior art first, drafts the brief, and comes back with a **batched set of
questions** — each carrying why it matters, the default that will be taken if he says
nothing, and what that default costs if it is wrong. That conversation is where he shapes
the product. It is deliberately informed rather than immediate: questions asked after the
research are worth more than questions asked before it, and it means he answers once
instead of being drip-fed.

Then stop. Do not run the gates in this invocation — `/advance` drives the loop from here,
and `/status` shows where it stands.

## What not to do

- **Do not interview him yourself in this session.** The interview belongs to stage 0 and
  belongs in the artifact. A conversation held here evaporates when the session ends, which
  is the failure this whole design exists to prevent.
- **Do not form a view on the product.** You are the front door, not the analyst. Whether
  the idea is any good is stage 0's finding to make, with research behind it.
- **Do not skip to implementation** however obvious the build looks.
