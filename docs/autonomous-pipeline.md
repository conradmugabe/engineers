# The autonomous product pipeline

How to take Conrad's product-development process from semi-automated (he is the
conveyor belt between stages) to mostly automated (the belt drives itself; he is an
optional inspector).

## The diagnosis

The process described is a 12-stage pipeline where every stage is capable of being done
by an agent, and every *transition between stages* is done by a human pressing enter.
Automating the stations is not the problem. Replacing the belt is.

A belt needs exactly three things:

1. **Durable state.** Every stage's output is a file in the repo or an issue on GitHub.
   Nothing that matters lives in a chat session. If it isn't on disk, it doesn't exist.
2. **A driver that wakes itself.** A scheduled run that reads the world, does the next
   unit of work, writes the result, and exits. Not a human pressing enter, and not a
   session that must stay open.
3. **Machine-checkable exit criteria per stage.** Without them the pipeline cannot know
   when a stage is finished, so it defaults to the only oracle it has: asking the owner.

And one thing that will silently defeat all three: **unenforceable taste**. Corrections
delivered by eyeballing are a human dependency by definition. They must be converted
into checks or the owner will be eyeballing forever.

## The stage machine

Each stage has a **producer** agent, an **adversarial validator** agent (a different
agent — this is what structurally prevents skipping a hat), and an artifact on disk. A
stage is complete when its artifact exists and its validator returns pass. The pipeline
frontier is computed from the filesystem, never remembered.

| # | Stage | Artifact | Validator gate |
|---|---|---|---|
| 0 | Intake ✅ **built** | `docs/00-brief.md` | Confidence score over a required-facts checklist; below threshold, generate an interview (see Question protocol). Implemented as the `intake` skill + `researcher` agent. |
| 1 | Requirements | `docs/01-srs.md` | Every requirement traceable to a source (client statement, research citation, or explicit inference) and carries a why; user/market/current-solution sections present; no orphan requirements |
| 2 | Feature specs | `docs/02-features/<slug>.md`, one per feature | Each has goals, non-goals, users, performance budget, presentation notes; every SRS requirement maps to at least one feature |
| 3 | Systems engineering | `docs/03-system/{components,architecture,communication,tooling}.md` | Every feature assigned to components; every component has a chosen technology with a written objective rationale (not popularity); every inter-component call names a protocol |
| 4 | Scope & phasing | `docs/04-roadmap.md` | The MVP set is closed under its own dependencies |
| 5 | Brand kit | `docs/05-brand/tokens.json` + rationale | Tokens machine-readable; contrast ratios pass WCAG AA |
| 6 | UI design | `design/screens/*.png` + `docs/06-screens.md` | Every MVP feature has at least one screen; every screen's spec references brand tokens |
| 7 | Implementation architecture | `docs/07-repo-architecture.md` | The scaffold it describes actually builds |
| 8 | Feature design docs | `docs/08-designs/<slug>.md` | Template order enforced: acceptance criteria **first**, at least two rejected alternatives each with a stated reason, chosen approach in depth, full test list, implementer notes, flexibility level |
| 9 | Implementation | Code on trunk behind a flag | Lint, types, and the tests named in stage 8 all pass |
| 10 | Verification | Test results, visual diff report, blind-test report | Screenshot-versus-design deviation report; blind tester; QA suite extended |
| 11 | Security | Attack report + security verdict | Clear verdict, zero open critical or high findings |
| 12 | Integration | `docs/integrations/<service>.md` + real adapters | Every port has a real adapter, not just a mock; every env var documented; `.env.example` complete |

Backtracking is first-class: any validator may return `regress-to: <stage>` with a
reason, which invalidates downstream artifacts and moves the frontier back. This is what
keeps the pipeline agile rather than waterfall — the ability to move backwards is
encoded, not improvised.

## The roster

One named role per hat. An unnamed hat is the easiest one to skip, which is the failure
mode this whole pipeline exists to remove — so every stage has an owner with a name, and
no stage is "whoever happens to be in the session".

| Agent | Owns | Access |
|---|---|---|
| `product-analyst` | Stages 0–1: intake, requirements, the SRS | Full |
| `researcher` | Prior art for stages 0–3 | **Web only** — no shell, no files |
| `product-designer` | Stage 2 (feature specs) and stage 4 (scope and phasing) | Full |
| `systems-architect` | Stage 3: components, communication, architecture, tooling choices | Full |
| `ux-designer` | Stages 5–6: brand kit, tokens, screens | Full + browser |
| `tech-lead` | Stages 7–8: repo architecture, feature design docs | Full |
| `backend-engineer` | Stage 9 | Full |
| `frontend-engineer` | Stage 9 | Full |
| `qa-engineer` | Stage 10: permanent automated tests | Full |
| `blind-tester` | Stage 10: the non-technical user | **Browser only** — no source access |
| `hacker` | Stage 11: red team | Read + execute + offensive browser tools, no write |
| `security-engineer` | Stage 11: blue team, owns the verdict | Full |
| `reviewer` | Adversarial review of any diff | Read + execute only |
| `critic` | Adversarial validation of any *stage artifact* against its gate | Read only |

`critic` is deliberately generic rather than one validator per stage: it loads the stage's
skill, reads the artifact, and attacks it against that stage's exit criteria. One role,
parameterised by stage, instead of twelve near-identical ones.

The restricted rosters (`researcher`, `blind-tester`, `hacker`, `reviewer`, `critic`) are
restricted by **tool allowlist**, not by instruction. A constraint that lives in a prompt
is a suggestion; a constraint that lives in the allowlist is a property of the system.

## The driver

An outer loop and an inner loop.

**Outer loop — `/advance`, on a schedule.** A scheduled run (cron) that: reads the
filesystem and GitHub to compute the frontier, executes one stage (or dispatches the
orchestrator for stage 9), writes artifacts, updates labels, and exits. It must be
**idempotent and stateless**: if it dies mid-stage, the next tick recovers from what is
on disk. This property is what makes abandoning the project for two weeks cost nothing.

**Inner loop — `/orchestrate`, event-driven.** The existing implementation loop:
dispatch engineers in parallel, gate every result, never trust a report. Stage 9 and 10
are its territory.

The outer loop is slow (minutes to hours). The inner loop is fast (event-driven within a
session). Neither requires the owner to be present.

## The question protocol

This is the mechanism that converts "waiting on Conrad" into "Conrad may intervene."

Every question the pipeline generates is filed as a GitHub issue labeled `needs-owner`
containing four things: the question, why it matters, **the default decision the
pipeline will take**, and when it will take it. The pipeline then **keeps going**. After
the deadline it proceeds on the default and records the decision in
`docs/decisions/ADR-NNN.md`, flagged in the eventual PR as an assumption.

Silence is consent, with a full audit trail.

Only two categories genuinely block:

- **Irreversible or external commitments** — money, legal, client-facing promises,
  production data.
- **External dependencies the pipeline cannot satisfy** — real API keys, third-party
  accounts.

Those get `blocking` and a notification. Everything else defaults and moves.

At stage 0 the interview is **batched**: one sitting, every question at once, driven by a
required-facts checklist and a confidence score, repeated only while confidence is below
threshold. Not a drip of prompts.

## Notifications

Cheapest path that works today: the pipeline assigns `blocking` issues to the owner and
GitHub emails him natively. Zero code. Add a Stop hook or an explicit notification step
for push notifications, and a webhook bridge (e.g. Twilio) if WhatsApp is genuinely
wanted later. Do not build the notification layer before the pipeline that needs it.

## Taste as tests

The owner's current correction loop — read the code, dislike it, tell the agent — is
precisely the human element being removed. Prose rules in skills lose because they are
advisory context competing with everything else in the window; a failing check is a hard
stop. The conversion:

| Preference | Enforcement |
|---|---|
| Bouncer pattern, no deep nesting | `max-depth: [error, 2]`, `no-else-return`, `complexity: [error, 8]`, `sonarjs/cognitive-complexity` |
| No switch statements | `no-restricted-syntax` on `SwitchStatement` |
| No nested ternaries / hidden control flow | `no-nested-ternary`, plus named reviewer checklist items |
| Expressive, human-readable code | **Cold-read test**: a fresh agent with zero context reads the file and explains what it does. If it cannot, the code is not expressive. Cheap, and it encodes the actual standard rather than a proxy for it. |
| Rich error context for AI diagnosis | Ban bare `catch {}` by lint; assert error payloads carry context fields in tests |
| No premature optimization | Reviewer checklist: any optimization without a measurement is a finding |
| Design-token coherence | Lint rule banning raw colour/spacing literals outside the token file |

And the meta-rule, which matters more than any individual row: **a correction is not
finished until it exists as a check.** A `/correct` command that (1) fixes the instance,
(2) writes the lint rule, checklist item, or test that prevents recurrence, and (3)
records it. Taste then compounds into the system instead of evaporating at the end of a
session.

The craft skills (`react`, `api-calls`, …) remain the prose layer explaining *why*. The
lint config, tests, and checklists are the layer with teeth.

## Trunk-based development

The owner wants one branch and feature flags. The current orchestrator uses feature
branches and issue branches. These reconcile cleanly once worktrees are understood as a
*workspace* mechanism (parallel agents not stomping each other's files) rather than a
branching strategy:

- Agents work in isolated worktrees on **short-lived** branches, merged to trunk as soon
  as their gates pass — hours, not days. That is trunk-based development.
- Everything user-visible ships behind a **feature flag**, so incomplete work lives
  safely on trunk.
- The feature-level gates (blind test, security) run **against trunk with the flag
  enabled**, which is strictly better than testing an isolated branch: it exercises the
  real integrated system.
- `main` still merges to production only by the owner's decision.

## Mocks, real services, and secrets

Every external service sits behind an interface with two adapters:

- **Mock adapter** — high fidelity, with chaos injection: random latency, random
  failures, timeouts, malformed responses. MSW on the frontend, the equivalent pattern on
  the backend. The entire pipeline builds and tests against these, so it never blocks on
  a credential.
- **Real adapter** — written at stage 12, not skipped. A gate verifies that every port
  has a real adapter, so nothing ships permanently mocked.

Stage 12 also generates `docs/integrations/<service>.md` per service: what to sign up
for, the exact steps to obtain the key, the exact env var name, where it goes, and how
to verify it works. Plus a complete `.env.example`.

This is the one genuinely unavoidable human step in the entire pipeline — and it is
batched into a single sitting at the end rather than scattered across the build.

## Security posture

The `hacker` (red) and `security-engineer` (blue) pair already gates every feature. An
autonomous pipeline needs three additions:

1. **Shift-left threat modelling.** The security engineer reviews stage 8 design
   documents *before code exists* — auth, authz, and data-classification requirements are
   cheapest to fix as words.
2. **Dependency vetting gate.** No library enters without a check on maintenance status,
   download volume, CVE history, and whether it is actually needed. Approvals and
   rejections logged.
3. **Sandbox for anything sketchy.** Experimental or untrusted code runs in an isolated
   container, never in the project workspace.

Honest limit: self-hacking finds a real and useful class of vulnerability. It is not a
substitute for a professional penetration test on anything handling money, health data,
or personal data at scale.

## Model assignment

Tool-juggling is solved by making one environment the home and calling the others as
tools rather than switching contexts by hand. Agent definitions carry a `model:` field,
so "use a creative, high-intelligence model for systems engineering" becomes
configuration rather than a manual decision:

- Stages 1–4 and 8 (requirements, product design, systems engineering, feature design):
  the strongest available reasoning model.
- Stage 9 (implementation): Opus.
- Validators and gates: Opus, adversarially prompted.
- Mechanical stages: a cheaper tier.

The one genuine gap is UI image generation, which this environment cannot do. Stage 6
therefore generates *image prompts* in a batch, and either calls an image API if one is
wired up, or hands the owner one batched task instead of dozens of interruptions.

## Build order

Do not build twelve stages. Build in pain order, and prove each phase on a throwaway
project before trusting it with client work.

**Phase A — the driver and the question protocol.** `/advance`, the schedule, the
`needs-owner` + default-decision + ADR mechanism, and notifications, applied to the part
that already works (issues through gates to PR). This alone removes the prompt-and-wait
pain from implementation and makes abandonment recoverable. Highest leverage; do it
first.

**Phase B — taste as tests.** Lint configuration, reviewer checklists, the cold-read
test, and `/correct`. Cheap, and autonomy is unsafe without it.

**Phase C — the front half.** `/plan-product` (stages 0–4) as producer/validator pairs.
This is where the owner's highest-value thinking lives, so automate it only once the
machinery is trusted.

**Phase D — design and visual verification.** Brand tokens, batched image prompts,
screenshot-versus-design deviation reports.

**Phase E — integration, secrets documents, and dependency vetting.**

## What will actually bite

- **Drift over long autonomous runs.** Mitigated only by short steps with hard gates and
  artifacts on disk. Never by longer prompts.
- **Cost.** A fully autonomous product build is measured in millions of tokens. This is
  a real budget line, not a rounding error.
- **"Production-ready, never compromise" is not self-enforcing.** It is a wish until a
  gate refuses to pass. Every quality bar in this document must have a check behind it or
  it will quietly decay.
- **The first project will be worse than doing it by hand.** The payoff is the fifth
  project, not the first.
