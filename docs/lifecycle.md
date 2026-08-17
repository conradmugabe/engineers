# Lifecycle

Nine stages, numbered 0 through 8, collapsed from the Product Factory blueprint's
twenty-two. A seam gets split
into its own stage when it demonstrably hurts to have them joined — not before. Small
projects drown in ceremony; the point of a stage is that it has a gate worth failing.

This file is runtime-agnostic. Claude Code implements it today via `/advance`; a control
plane could implement it tomorrow by reading the same artifacts.

## Stages

| # | Stage | Owner | Artifacts | Gate |
|---|---|---|---|---|
| 0 | INTAKE | product-analyst | `docs/00-brief.md` | **Context gate.** Objective, users, critical workflows, and material constraints understood. Every capability sorted into must have / nice to have / polish, each with its one-sentence defence. Open questions either non-blocking or escalated. |
| 1 | REQUIREMENTS | product-analyst | `docs/01-requirements/` + `REQ-*` | **Requirements gate.** Every requirement has an ID and provenance; assumptions carry their recorded default; contradictions resolved; out-of-scope explicit; security and privacy requirements present. |
| 2 | FEATURES | product-designer | `docs/02-features/` + `FEAT-*` | **Coverage gate.** Every MUST requirement maps to at least one feature; every feature traces to at least one requirement; goals, non-goals, states, and acceptance criteria present. |
| 3 | SYSTEM | systems-architect | `docs/03-system/` + `ADR-*` | **Architecture gate.** Every feature has a system home; data ownership defined; communication paths coherent; auth boundaries explicit; failure handling and observability considered; every technology choice justified against criteria, not popularity. |
| 4 | SCOPE | product-designer | `docs/04-roadmap.md` | **Scope gate.** The release set is closed under its own dependencies; phases named; nothing in MVP depends on something outside it. |
| 5 | DESIGN | ux-designer | `docs/05-design/`, `tokens.json`, coded prototype | **Design gate.** Every release-scope feature has screen and state coverage including loading, empty, error, and permission-denied; design-system rules consistent; UI does not contradict feature requirements; accessibility represented. |
| 6 | BUILD | tech-lead → engineers | `docs/06-designs/` + `TASK-DESIGN-*`, code on trunk | **Per-feature implementation gate.** Acceptance criteria mapped to tests; implementation design reviewed; build, lint, and types pass; tests pass; code review passes; security checks pass for the affected surface; visual comparison passes for UI. |
| 7 | VERIFY | qa-engineer, blind-tester, hacker, security-engineer | Test evidence, blind-test reports, attack report, security verdict | **Verification gate.** QA suite passes; every persona whose experience changed has a blind-test run in both browsers; security verdict is clear with no open critical or high finding. |
| 8 | RELEASE | integration + release | `.factory/human-actions/`, real adapters, release checklist | **Release gate.** Release-scope requirements satisfied; every port has a verified real adapter; no release-blocking security findings; migration and rollback defined; monitoring available; required human actions complete. |

### Exception states

- **HUMAN_ACTION_REQUIRED** — an escalation condition fired. Carries a `HACT-*` artifact
  naming what is needed, whether it blocks everything or one dependency, the exact steps,
  and the signal that resumes the work. Independent work continues unless genuinely blocked.
- **BLOCKED** — no route forward and no human action would unblock it. Requires a written
  diagnosis on the artifact.
- **REMEDIATION** — a gate failed. Never DONE, never silent acceptance.

## Transition rules

1. A stage advances only when its artifacts exist **and** its gate returns PASS from a
   judge that did not author them.
2. A failed gate goes to REMEDIATION, not to the next stage.
3. Remediation identifies the **earliest affected artifact** and invalidates only what
   depends on it. Unrelated work is never regenerated.
4. Transient execution failures retry automatically within the task's budget.
5. The same semantic failure exceeding its retry budget escalates — to a stronger model
   first, then to HUMAN_ACTION_REQUIRED.
6. Backtracking is normal, not exceptional. Discovering at stage 6 that a requirement was
   wrong is a stage-1 regression with downstream staleness, and the machinery for it is the
   same as for forward progress. This is what makes the pipeline agile rather than
   waterfall.

## The generator / critic / judge loop

Every stage artifact passes through three distinct roles, and no two of them may be the
same agent instance:

```
generator → critic(s) → generator remediation → judge → PASS | REVISE | HUMAN_REQUIRED
```

- **Generator** produces the artifact. It is the stage owner in the table above.
- **Critic** attacks the artifact against the stage gate. It finds defects; it does not
  decide the outcome and it does not rewrite the work.
- **Judge** reads the artifact and the critique and decides. It never authors the thing it
  is judging.

The split between critic and judge is not ceremony. A critic that also decides has an
incentive to shade its findings toward the outcome it prefers — under-reporting to pass the
stage, or over-reporting to look rigorous. Separating "what is wrong with this" from "does
this advance" removes that incentive from both roles.

Debate is bounded. Where alternatives are called for, generate two to four practical
options, score them against explicit criteria, select one, and move on. REVISE has a retry
budget; exceeding it escalates rather than looping.

## Computing the frontier

State is **derived, never remembered**. A runtime determines where the project stands by
reading the filesystem: which stage artifacts exist, which validate against their schemas,
which carry a PASS from a judge, and which are marked STALE.

This is the property that makes the pipeline survivable. Any session, any process, any
future control plane can pick up a half-finished project with no handover, and walking away
for a month costs nothing.
