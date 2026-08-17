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

| Persona | Who they are | What they can do | What they must not reach |
|---|---|---|---|
| | | | |

<Name every boundary, including the obvious ones. The test and security stages depend
on this table. If the product genuinely has one undifferentiated user, say so explicitly.>

## Must have · nice to have · polish

<Every capability from the conversation, sorted into exactly one bucket, each tagged with
its provenance. Stage 4 turns this into release phases, so a lazy sort here becomes a wrong
roadmap there.>

### Must have — the product is not worth shipping without it

<Test applied to each: if everything else shipped and this did not, would anyone use it?
State the one-sentence defence next to each item. An item that cannot be defended in one
sentence does not belong in this table.>

| Capability | Why it is a must | Provenance |
|---|---|---|
| | | |

### Nice to have — meaningfully better, but the product works without it

| Capability | What it adds | Provenance |
|---|---|---|
| | | |

### Polish — what makes it good rather than merely working

<Does not change what the product does. Onboarding, empty states, error copy, keyboard
access, perceived speed, motion, consistency. Recorded and scheduled, never quietly
discarded — "later" is only honest when later has a trigger.>

| Item | What it is worth | Trigger / phase | Provenance |
|---|---|---|---|
| | | | |

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
<Real requirements deliberately deferred, so they are not rediscovered as surprises.>

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
