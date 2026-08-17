# Product brief — <product name>

**Two words:** <the two-word description>
**Source:** client conversation on <date> | own idea
**Status:** draft | interview pending | ready for stage 1
**Written:** <date>

Every fact below is tagged `[client]`, `[research]`, `[inferred]`, or `[assumed]`.
`[assumed]` facts also appear under Open questions.

---

## What it is
<One or two sentences. What the thing does, in plain language.>

## Who it is for
<A specific user. Their job, their day, their constraints. Not a market category.>

## The problem
<In the user's terms. What goes wrong for them today and what it costs them.>

## What they do today instead
<The incumbent — a competitor, a spreadsheet, a WhatsApp group, or nothing. How it
actually works for them, including what they like about it. A product that ignores
what the incumbent does well loses to it.>

## Why they would switch
<The wedge. The specific thing that is enough better to justify the cost of change.
If this is weak, say so here rather than downstream.>

## What success looks like
<Stated so it could be measured. For the user, and for the client or owner.>

## Money
<Who pays, for what, roughly how much. Or what justifies the build if not commercial.>

## Constraints
<Platform, timeline, budget, regulation, systems to integrate with, data to migrate.>

## Personas and boundaries

| Persona | Who they are | What they can do | What they must not reach | Conditional on |
|---|---|---|---|---|
| | | | | Unconditional \| `N1` (dormant) |

**The "Conditional on" column is required, and it applies per capability, not only per row.**
QA, the blind tester, the hacker and the security engineer read this table as the contract. A
persona — or a single capability inside one — that exists only if a nice-to-have gets built
reads to them as live work: they go looking for it, cannot produce it, and the natural repair
is to build the missing capability, silently undoing the demotion. Mark a row `Unconditional`
only when **every** capability in it is must-have; where one capability depends on something
unscheduled, name that dependency next to the capability rather than at the end of the row.

<Name every boundary, including the obvious ones. The test and security stages depend
on this table. If the product genuinely has one undifferentiated user, say so explicitly.>

## Must have · nice to have · polish

<Every capability from the conversation, sorted into exactly one bucket, each tagged with
its provenance. Stage 4 turns this into release phases, so a lazy sort here becomes a wrong
roadmap there.>

<**Give every row a stable id — `M1`, `N1`, `L1` — and use it everywhere else in the
document.** This is not decoration. Scope gets restated in several places (the requirements
table, the persona contract, the workflow defaults, Later phases, and prose), and when a
capability is demoted, every one of those has to move with it. Ids are what let
`scripts/check-brief.py` verify that mechanically instead of a reader catching it four
rounds later. A brief written without them is not checkable.>

### Must have — the product is not worth shipping without it

<Test applied to each: if everything else shipped and this did not, would anyone use it?
State the one-sentence defence next to each item. An item that cannot be defended in one
sentence does not belong in this table.>

| Id | Capability | Why it is a must | Motivation | Provenance |
|---|---|---|---|---|
| M1 | | | Product / Fixture | |

### Nice to have — meaningfully better, but the product works without it

| Id | Capability | What it adds | Provenance |
|---|---|---|---|
| N1 | | | |

### Polish — what makes it good rather than merely working

<Does not change what the product does. Onboarding, empty states, error copy, keyboard
access, perceived speed, motion, consistency. Recorded and scheduled, never quietly
discarded — "later" is only honest when later has a trigger.>

| Id | Item | What it is worth | Trigger / phase | Provenance |
|---|---|---|---|---|
| L1 | | | | |

### Precedence — the rule that keeps every other section honest

<State it once, and make it bind **every** place the document expresses scope, not just the
requirements table. On the first real run this rule was written to cover one table; the
demotions were propagated there and nowhere else, and the round after that a fix to one
consumer falsified a sentence in another. Three clauses:>

1. Nothing is scheduled earlier than the bucket of the capability it serves.
2. No must-have depends on a non-must-have.
3. Anything conditional on an unscheduled capability says so **where it is stated**, not
   only in the sort.

**Consumers of scope in this document** — every one has to move when a capability does:
the requirements table's Phase column, the persona contract, the workflow defaults, Later
phases, the non-goals, and any prose that schedules something.

**Sort notes:** <Items whose bucket was contested, who wanted them where, and why the
sort landed as it did. Also record anything demoted out of "must have" during the
interview — that demotion is a finding.>

## Non-goals
<What this is deliberately not. Be specific enough to refuse a future request with it.>

## Requirements nobody asked for
<Things this class of product needs that were never mentioned. Each with the concrete
failure that occurs without it. Anything real but not now goes to Later phases.>

| Requirement | Why it is needed | Failure without it | Phase |
|---|---|---|---|
| | | | |

## Risks
<What would make this fail, technically or commercially. Order by severity.>

## Prior art
<What the researcher found. Who solves this, how, what users complain about, table
stakes, pricing shapes, compliance obligations. Each claim with its source.>

## Later phases
<Real requirements deliberately deferred, so they are not rediscovered as surprises.
**Every entry names the bucket row it corresponds to** — `- Multi-device sync — N19.
Trigger: …`. Deferring a capability is a schedule, not an exemption from the sort, and
the id is what makes that checkable. An entry with no id sat in no bucket for three
rounds on the first real run while the closure claim said otherwise.>

---

## Confidence scoring

| # | Required fact | Present / Partial / Absent |
|---|---|---|
| 1 | What it is | |
| 2 | Who it is for | |
| 3 | The problem | |
| 4 | What they do today | |
| 5 | Why they would switch | |
| 6 | What success looks like | |
| 7 | Money | |
| 8 | Constraints | |
| 9 | Personas and boundaries | |
| 10 | Non-goals | |
| 11 | Risks | |
| 12 | The three-bucket sort | |

**Gate:** 1–6 all present, 12 present, and no more than two of 7–11 absent.
Fact 12 is not satisfied by a sort with everything in the must-have column.
**Verdict:** ready for stage 1 | interview required | idea not viable

## Assumptions this plan rests on
<Every `[assumed]` fact, with the default taken and what breaks if it is wrong.>

| Assumption | Default taken | Cost if wrong |
|---|---|---|
| | | |

## Open questions

| # | Question | Why it matters | Default if unanswered | Cost if default is wrong | For |
|---|---|---|---|---|---|
| | | | | | client / owner |
