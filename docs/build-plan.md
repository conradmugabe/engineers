# Build plan

What we are building, in what order, and why that order. Updated as phases land.

## The organising principle

> **Contracts are portable. Runtimes are not.**

Everything durable — the constitution, the artifact schemas, the stable IDs and their
traceability graph, the stage definitions and their gates, the human-action contract, the
project directory layout — is written as **files a program could read**, not as behaviour
baked into a Claude Code skill. Claude Code is the *first* runtime for those contracts. The
Product Factory control plane from the v1 blueprint is a *second* runtime that reads the
same `.factory/` directory, validates against the same `schemas/`, and drives the same
state machine.

This is why the platform is deferred rather than dismissed. Deferring it costs nothing
provided we never encode a contract *only* inside a skill prompt. Every phase below is
built to that rule, so P7 is a runtime swap rather than a rewrite.

The test for any new piece of work: **if the control plane existed tomorrow, would this
have to be rebuilt?** If yes, it is in the wrong layer.

---

## P0 — Contracts

The layer both runtimes share. Nothing here mentions Claude Code.

- [x] `docs/constitution.md` — the 20 blueprint rules plus our four additions, each with a
      required enforcement terminus.

      **Rule 21 has been revised three times in one session**, each revision forced by a
      concrete failure the gate loop surfaced rather than by reflection. First it said
      unanswered questions default and work continues — the critic found it never required
      the question to actually *reach* the owner. Then it said a STRUCTURAL cost escalates —
      the judge found that conflated expensive-to-reverse with irreversible, which would
      escalate reversible design judgements for nothing. Now it requires **both** halves for
      blocking: owner-held information *with no defensible default*, classified per question
      rather than in bulk. That churn is a signal, not noise: rule 21 is the rule the whole
      autonomy claim rests on, and it is subtler than it looks. Treat further revisions to it
      as expected rather than alarming — but watch for a revision made to reach an outcome
      rather than on principle, and put that question to the judge explicitly when the rule
      changes mid-judgement.
- [x] `schemas/` — requirement, feature, ADR, implementation-design, test, human-action,
      adopted from the blueprint.
- [x] `schemas/requirement.schema.json` extended: `ASSUMED` provenance, a conditionally
      required `assumption` object, `upstream`/`downstream`. Conditionals verified — an
      `ASSUMED` requirement without its recorded default fails validation, `RESEARCHED`
      without evidence fails, `INFERRED` without rationale fails.
- [ ] Extend the remaining schemas with `upstream`/`downstream` for the traceability graph.
- [x] `docs/lifecycle.md` — the 8 stages, their artifacts, their gates, and the transition
      rules. Collapsed from the blueprint's 22; split a seam only when it hurts.
- [ ] `docs/traceability.md` — ID prefixes, the dependency graph, and the `STALE`
      propagation rule (change an upstream artifact, dependents go stale, unrelated work is
      untouched).
- [ ] `docs/escalation.md` — the twelve escalation conditions, the human-action contract,
      and the silence-is-consent default protocol.
- [ ] Project directory contract — `.factory/` (project.yml, status.json, traceability.json,
      decisions/, human-actions/, evidence/, runs/) alongside `docs/NN-stage/`.
- [x] `scripts/validate-artifacts.py` — schema validation any runtime shells out to, exit
      code 1 on failure. Selects the schema from the artifact's ID prefix. Verified to catch
      an `ASSUMED` requirement with no recorded default and a feature with no requirement
      traceability. This is what turns the gates from advisory into real.

- [x] `scripts/check-template.py` — integrity checks on the template *itself*, the gap an
      outside evaluation named as our sharpest: every artifact we produce is adversarially
      reviewed, and the machinery doing the reviewing was reviewed by nobody. Checks that every
      agent the frontier can dispatch exists, that declared names match locations, that
      restricted roles still carry their restrictions, and that load-bearing sentences are
      still where the rules say they are. **Currently fails on four missing stage owners.**
- [x] Prose invariants pinned as string assertions — the missing fourth enforcement terminus
      for rules that are irreducibly prose. Does not stop a rule changing; stops it changing
      *quietly*, since the edit now fails a check and revising becomes a deliberate act.
      Found a real gap on its first run: the judge's authorship rule lived only in the agent
      stub, not in the playbook it follows for the whole run.
- [x] Content hashes replace mtime for staleness. **`git clone` used to invalidate every
      passed stage** — checkout writes alphabetically, so a critique lands microseconds before
      the artifact it reviewed. Proven by cloning a fixture; the fix is proven the same way.
- [x] An unreadable verdict escalates instead of looping. A REVISE with no round line meant
      never exhausted, never escalated, `REMEDIATE` on every tick — unbounded spend on a timer.
- [x] A check that ran over nothing no longer reports green (`validate-artifacts.py`).

## P1 — The thinking pipeline (stages 0–4)

Get an idea to an implementation-ready plan with no manual prompting between stages.

- [x] `intake` skill + `product-analyst` + `researcher` (web-only). Proven on a real run:
      refused a thin brief, produced a batched interview with defaults, and found a
      correctness defect in an existing issue.
- [x] `critic` and `judge` agents + playbooks — the generator/critic/judge loop. The critic
      finds defects; the judge decides PASS / REVISE / HUMAN_REQUIRED. Both read-only, and
      neither may author what it judges.
- [ ] Requirements stage — `product-analyst` emits schema-valid `REQ-*` artifacts with
      provenance. Prose SRS for the reasoning, JSON for the facts the pipeline depends on.
- [ ] Feature decomposition + specs — `product-designer`, `FEAT-*`.
- [ ] System engineering + technology selection — `systems-architect`, `ADR-*`.
- [ ] Release scoping — MVP closed under its own dependencies.
- [x] `scripts/frontier.py` — computes the frontier from disk and names the single next
      action. Detects staleness by mtime, so a revised artifact automatically re-enters the
      critique/judge loop. Verified against a live project mid-revision.
- [x] `/advance` — does exactly one step and exits. Idempotent; a crash costs one step.
- [x] `/status` — read-only glance, changes nothing.
- [x] `docs/00-idea.md` as stage 0's input. The pipeline's single human input is a **file**,
      not a prompt, which is what lets a timer start a project with nobody present.
- [x] `/new-idea "<text>"` or `/new-idea @path` — the front door. Records the input verbatim
      (never tidied — it is the only `[client]` material the pipeline will ever have),
      settles client-sourced versus own-idea mode, and starts stage 0.
- [x] The interview is an interrogation, not a survey: never accept the first "why", demand
      the specific instance, treat solution-shaped answers to problem questions as
      non-answers, require a source for every number, ask what the product may be *bad* at,
      ask what goes if the time halves. Batched still, but no longer one-and-done.
- [x] **Must have / nice to have / polish** as required fact 12 and a hard gate criterion,
      each item carrying a one-sentence defence. Mirrored in `requirement.schema.json` as
      `MUST_HAVE | NICE_TO_HAVE | POLISH` (replacing MoSCoW). Polish is scheduled, never
      silently dropped; anything that changes what the product can *do* is a capability, not
      polish. A sort with everything in the must column does not satisfy the gate.
- [x] `docs/owner-log.md` — the durable record of what has actually been put to the owner,
      through what medium, with the default taken and the answer if one came. **Rule 21 is
      unenforceable without it:** the rule distinguishes a question the owner declined by
      silence from one he never saw, and nothing could tell those apart while questions were
      being relayed in conversation. Found the hard way — an analyst correctly refused to
      claim its questions had been delivered, because it had no way to check. Contract: an
      entry is written at the moment a question is put, never afterwards; no entry means it
      was not asked.
- [ ] Human-action files (`SECRETS_REQUIRED.md` and friends) + notification on `blocking`.

**Exit:** one real product goes idea → implementation plan with the owner touched only
through formal human-action requests.

## P2 — The driver

- [ ] systemd timer on the VPS running `claude -p "/advance"` headless. The timer is the
      spine; a session is never load-bearing.
- [ ] Crash/restart test — kill mid-stage, confirm the next tick resumes from artifacts.
- [ ] herdr for attach-and-watch, explicitly *not* for reliability.
- [ ] VPS hardening: non-root, containerised agents, no production credentials on the box,
      narrow egress, SSH keys only.
- [ ] Prompt-injection containment — research and any web-reading role stays tool-restricted;
      its output is written to file by the caller, never executed as instruction.

## P3 — Taste as tests

Autonomy is unsafe before this lands, because it is what stops the owner being the linter.

- [ ] ESLint config encoding the code philosophy: `max-depth`, `complexity`,
      `no-else-return`, `no-nested-ternary`, no `SwitchStatement`, no bare `catch {}`.
- [ ] The cold-read test — a fresh agent with zero context reads a file and explains it. If
      it cannot, the code is not expressive.
- [ ] Reviewer checklist items for the semantic rules static tools cannot judge.
- [ ] `/correct` — fixes the instance, writes the check that prevents recurrence, records
      it. Constitution rule 22 gets its enforcement terminus here.

## P4 — Implementation automation

Most of this exists; it needs reconciling with the blueprint's integration model.

- [ ] Reconcile `orchestrate` with trunk-based development: ephemeral worktrees, an
      integration queue that rebases and merges one approved change at a time, feature flags
      for incomplete work on trunk.
- [ ] Implementation-design stage — `tech-lead` emits schema-valid `TASK-DESIGN-*`:
      acceptance criteria first, 2–4 alternatives, rejected reasons, test plan.
- [ ] Per-feature execution loop wired to the gates already built.
- [ ] `TEST-*` artifacts traced to acceptance criteria, so coverage is measured against
      requirements rather than lines.

## P5 — Design

- [ ] Brand kit as `tokens.json` with contrast validation.
- [ ] Claude Design handoff bundle (component tree + tokens + spec) committed into the repo
      as a coded prototype. The one batched human step; everything after it is code.
- [ ] Screenshot-versus-prototype deviation report — same renderer both sides, so the
      pixel-perfection check stops being a judgement call.

## P6 — Integration, secrets, release

- [ ] Ports and adapters for every external service; mocks covering the blueprint's eleven
      failure modes (success, validation error, timeout, connection failure, malformed,
      partial, rate limit, duplicate callback, delayed callback, auth expiry, upstream down).
- [ ] Gate: every port has a real adapter, so nothing ships permanently mocked.
- [ ] `.factory/human-actions/SECRETS_REQUIRED.md` and friends — secret *names* and
      locations, never values.
- [ ] Release gate and post-deploy verification.

## P7 — The control plane (deferred, not dismissed)

Build when the methodology has driven two or three products end to end and the friction is
in *operating* the pipeline rather than defining it.

What it buys that Claude Code alone does not: a dashboard over many concurrent projects,
cost and token accounting per stage, an eval harness that benchmarks a model against known
good and bad outputs before it becomes default for a critical role, durable timers and
human-resume signals independent of any session, and the freedom to run non-Claude runtimes
for specific roles.

Why it will be cheap by then: the contracts, schemas, state machine, and directory layout
already exist and are already being exercised. The control plane implements the driver and
the store; it does not invent the methodology.

**Trigger to start:** when two of these are true — more than two products running at once,
cost per product is unknown and needs measuring, or a stage needs a model Claude Code
cannot dispatch.

---

## Immediate queue

1. ~~`docs/lifecycle.md`~~ — done.
2. ~~`critic` and `judge`~~ — done.
3. **Run the critic and judge against `00-brief.md`** — the first real test of the gate
   loop, on an artifact we already know has substance. If the judge waves through a brief
   whose own scoring says four load-bearing facts are Absent, the loop is theatre and we
   find that out now rather than at stage 6.
4. Stage 1 (requirements) as the first schema-backed artifact set — `REQ-*` files validating
   against `requirement.schema.json`, with accounts and sharing in scope.
5. Traceability rules + `.factory/` layout + the schema validation command.
6. `/advance` — the frontier computation and the stage runner.
