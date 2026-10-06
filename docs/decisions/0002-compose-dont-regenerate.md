# 0002 — Compose, don't regenerate

**Status:** accepted, not yet implemented. **Date:** 2026-10-06.

## Context

Agents make writing code cheap. The tempting conclusion is that every product should be
generated from scratch, shaped exactly to its need. That conclusion throws away the thing that
made modern software possible: parts with clear interfaces that anyone can build on, improved
over years by people who studied one problem for a long time. Everything is built on that pool
of parts — agents included.

A product regenerated from scratch is a dead end. Nothing in it can be lifted out, nobody else
can build on it, and the next product starts from zero again. Its internals also tend to miss
the long tail a mature part has already handled.

Frameworks are not only crutches for human limits. They do exist partly because humans
coordinate slowly, but they also hold accumulated correctness, and an agent that rebuilds one
each time rebuilds it worse. What agents genuinely change is the **cost of a rewrite**, so a
part can be rewritten when its creators learn something — "this should have been Rust" — instead
of living with it forever.

## Decisions

### 1. The reuse ladder

Before writing anything that is not specific to the product, climb the ladder:

1. **Use what exists.** A well-established part from the wider ecosystem.
2. **Use what we have.** A module the team already extracted, from the catalog (3).
3. **Write it new** — and if it is not specific to this product, write it as a module (2).

Skipping a rung needs a recorded reason that cites something measured or verifiable: "the
existing logger idles at 40 MB; our budget is 5", or "the existing library has no maintained
release in three years". "I could write a better one" is not a reason until it is a number.

The reviewer gets a new attack: **did this diff re-invent something that exists?**

### 2. Generic code is built as a module, not buried in a product

Code that is not specific to the product — a sync engine, a torrent engine, a comment service,
an HTTP server, a logger — is built as a module from the start, or extracted the moment it is
recognised as one. A module has:

- **an interface** — what it takes, what it promises, what it costs — readable by agents and
  humans alike
- **its own tests and budgets**, so it can be judged without the product around it
- **documentation written for both readers**: an agent that must use it correctly on the first
  try, and a human who wants to understand why it is built the way it is

The interface is the Lego stud. A module that honours its interface can be swapped, rewritten
in another language, or used by another product without the rest noticing — and because the
module carries its own judge, a rewrite is safe to attempt.

### 3. The team keeps a catalog

Extracted modules are recorded in a catalog: what each one does, its interface, its measured
budgets, and where it is used. The catalog is the team's memory — knowledge kept as working
parts rather than as notes — and it is what rung 2 of the ladder reads.

### 4. A craft role that is not a builder

Builders are rewarded for finishing the issue in front of them; nobody on the current roster
looks across issues or products. The team gains a role whose whole job is the craft:

- watch what is being built for parts worth extracting — "this server is faster than the one
  we use everywhere else", "three products have written the same sync logic"
- extract them into modules and keep the catalog current
- flag what is **worth studying** — a module that is unusually fast, small or well shaped — and
  explain why it works, in teaching terms, so the owner can learn from it
- flag what is **worth releasing** — a part good enough to publish, open-source, or sell as its
  own product — and leave that call to the owner

It does not change product behavior and does not judge its own extractions: a module it pulls
out goes through the same review and gates as anything else.

## Consequences

- The roster grows a craft role (name to be settled: architect, librarian). Its playbook and
  agent stub follow the existing pattern — a thin stub in `agents/`, substance in a skill.
- A catalog needs a home and a format: per project, across projects, or both.
- The proof packet (0001) carries the module map and anything flagged worth studying or
  releasing.
- `work-issue` and the reviewer playbook gain the reuse ladder and its attack question.

## Risks accepted

- **Premature extraction.** A part pulled out before its second use guesses at an interface
  and is often wrong. The default is to extract on recognition of genuine generality, and to
  accept that some interfaces will be revised.
- **Dependency risk.** Rung 1 imports other people's code, with its bugs and supply-chain
  exposure. The security roles cover what enters, not just what is written.

## Open questions

- The craft role is one of several perspectives the team needs — product, user experience,
  craft, performance, security — each owning its concern and none subordinate to the others.
  How they balance, and who settles a conflict between them, is a decision of its own.
