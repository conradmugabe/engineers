# 0001 — Judge behavior and interfaces; let the product be in any language

**Status:** accepted, not yet implemented. **Date:** 2026-10-06. Amended the same day: audit
structure as well as behavior; see 0002.

## Context

The goal is the whole path from a vague idea to a shipped product, with the owner working at
the level of ideas and user journeys while agents choose the technology and build it.

Two wants pull against each other:

- **Performance.** Agents do not carry the coordination costs that pushed the industry onto
  heavy, human-friendly stacks (Electron, React everywhere). Products should be fast and lean —
  an idle desktop app in tens of megabytes, not one gigabyte; one request where one is needed.
  That often means Swift, Kotlin or Rust rather than the stack the owner reads most easily.
- **Not a black box.** The owner must be able to see that the system does what it claims. An
  agent that writes both the code and its tests can make the tests pass while the product
  fails — the stub-out pattern `work-issue` already forbids.

The assumption behind the tension is that auditing an agent means reading all of its code.
Drop that assumption and most of the tension goes with it — but not all of it. Behavior alone
says nothing about whether the product is built from good parts that others can build on, and
the owner is an engineer as well as a product owner: implementations are worth studying, not
just tolerating. So the audit has two levels, and implementations stay open.

## Decisions

### 1. The user journey is the spec

A journey is a path a person takes through the product, in product terms. The owner or the
agents propose journeys; the owner approves or modifies them; the approved set is the spec.
Spec and prototype are produced together, not in sequence.

One journey feeds four things:

```
            ┌─→ prototype      the owner clicks through it, approves or modifies
journey  ───┼─→ issues         acceptance criteria are derived from it
            ├─→ journey test   a machine walks it on the real app, every build
            └─→ blind tester   a "first-time user" walks it and reports confusion
```

Nothing is built that does not trace to a journey. Nothing is done until its journeys pass on
the real app.

### 2. Audit at two levels; implementations stay open

```
behavior    journeys + budgets          does it do the right thing, fast enough?
structure   module map + interfaces     is it built from parts, and are the parts good?
            ───────────────────────
            implementations             any language; studied, not required reading
```

**Behavior** is checked by **the judge**: the approved journeys, the budgets attached to them,
and the harness that measures both. It is small and written in TypeScript.

**Structure** is the module map and the interface of every module — what it takes, what it
promises, what it costs. Interfaces are small and readable even when the implementation is in
a language the owner does not yet read; that is what makes the product both auditable and
composable. How the product is decomposed is governed by 0002.

**Implementations** may be in whatever the platform and the budgets call for. They are not
required reading for every change, but they are never a black box: they must be readable, and
when one is unusually good — fast, small, elegantly shaped — the team says so and points the
owner at it (0002). The owner reading a Rust module two years from now is an expected outcome,
not an edge case.

### 3. Measure at the boundary

Every check observes the product from outside: drive the UI, record network traffic, read
process memory, time cold start and frame rate. These are language-agnostic and hard to fake
from inside, unlike a unit test, which the builder controls.

Journeys carry **budgets** alongside steps — e.g. "autosave: exactly one request per edit
burst", "idle memory ≤ 10 MB", "cold start ≤ 400 ms on the low-end device profile". A budget is
a measured requirement, which is what constitution rule 14 asks for before optimising.

Budgets are measured on named **target profiles**, not the development machine: a low-end
phone, a 4 GB dev box running the whole stack at once, a 2 GB Raspberry Pi serving the backend
under concurrent load. A profile is part of the spec, so "can this run on a Pi?" is a question
the judge answers, not a guess.

### 4. The builder cannot touch the judge

Journeys, budgets and the harness are written in the spec stage, approved by the owner, and
are read-only to the build stage. A builder diff that modifies them fails a check, the same way
`check-template` fails a blind tester that gains a shell. This is rule 7 — the author of
important work cannot be its sole judge — applied to tests.

### 5. Every feature ships a proof packet

The owner reviews evidence, not diffs:

- a recording of each journey walked on the real app
- the network log
- measured numbers against every budget, pass or fail
- the blind tester's report
- security findings and what closed them
- the module map, with every interface that changed
- anything worth studying: a module that is unusually fast, small or well shaped, and why

The owner can still click around the app directly; the packet makes that optional, not
required.

### 6. A small default stack per platform; departures need a measured reason

| Platform | Default                                 |
| -------- | --------------------------------------- |
| iOS      | Swift / SwiftUI                         |
| Android  | Kotlin / Compose                        |
| Web      | TypeScript, lean (not React by default) |
| Desktop  | Rust core                               |
| Backend  | TypeScript or Rust, by the budgets      |

An agent may depart from a default only with a recorded decision that cites a budget: "budget
is 10 MB idle; the default measured 140 MB; the alternative measured 9 MB". Shared code lives
in the backend and the API contract, not the UI — native experience wins over UI code reuse.

_Why defaults at all:_ skills, templates and lessons compound only when stacks repeat. Agents
are also not equally strong everywhere, and frameworks encode correctness (accessibility, text
input, internationalisation) that "lowest level everywhere" would re-implement badly. Why only
defaults: rule 12 selects technology for product fit, and the budgets are how fit is shown.

### 7. Skills are layered: role × craft × project

```
role      backend-engineer, ios-engineer, …   how to work        few, stable
craft     swift, rust, web, …                 how to write it    grows per stack
project   project-context                     what is true here  per product
```

Craft skills are where taste and performance knowledge accumulate, and corrections land as
checks (rule 22). Keeping the default stack small keeps the craft skills curatable.

## Consequences

- A spec stage must exist that produces journeys, budgets and a prototype together. It does
  not exist yet; the swarm currently starts from hand-written issues.
- Journeys need a format that a prototype tool, an issue generator, a test harness and the blind
  tester can all consume. Designing it is the next piece of work.
- The roster grows platform engineers (`ios-engineer`, `android-engineer`, …) and a harness
  owner that is not a builder.
- `work-issue` must stop treating "tests pass" as sufficient; the journey tests and budgets
  become its gates, and it must not edit them.

## Risks accepted

- **Code the owner cannot yet read can still hurt** — security and long-term maintainability
  are not fully covered by behavior or interfaces. The reviewer, hacker and security-engineer
  roles exist for this; residual risk remains and is stated rather than hidden. It shrinks as
  the owner learns the languages the products are written in.
- **"Feels nice" does not fit in a budget.** It stays with the blind tester and the owner.
- **A judge can be wrong.** A bad journey or a loose budget passes a bad product. The judge is
  kept small precisely so the owner can review it.

## Open questions

- Do ideation and prototyping live in this repo, or in a separate tool that hands journeys to
  this one? Commit `9d4400b` moved planning out; this decision assumes the spec stage meets the
  swarm at the journey format, wherever it lives.
- Which tool renders the clickable prototype, and can it consume the journey format directly?
