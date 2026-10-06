# Constitution

The rules that hold regardless of project, stack, or stage. Everything else in this
template is implementation detail; this is what may not be traded away to ship faster.

Adapted from the Product Factory v1 blueprint, with the additions this team has proven
it needs.

## The operating principle

> The agent is not the process. The workflow is the process. Agents perform bounded work
> inside it.

## Rules

1. Every product is production-bound unless explicitly marked otherwise.
2. The workflow, not any agent, controls the lifecycle.
3. Required gates cannot be skipped — not by an agent that believes them unnecessary, and
   not to save context, tokens, or time.
4. Requirements are traceable through implementation and verification.
5. Important artifacts require independent review.
6. Failed verification triggers remediation, never silent acceptance.
7. The author of important work cannot be its sole judge.
8. Model confidence is not proof of correctness.
9. Human intervention is exceptional and governed by explicit escalation rules.
10. Secrets never appear in prompts, source, logs, screenshots, or generated documentation.
11. Faithful mocks enable development but never substitute for real release-scope
    integrations.
12. Technology is selected for product fit, not popularity.
13. Code prioritises clarity, explicitness, shallow control flow, and maintainability over
    cleverness.
14. Premature optimisation is prohibited unless a measured requirement justifies it.
15. Autonomous writers work in isolated workspaces; approved changes reach trunk through a
    controlled queue.
16. Recoverable failures are remediated autonomously within configured retry budgets.
17. Destructive production actions require explicit permission.
18. Security testing is confined to owned or explicitly authorised targets.
19. Release requires QA, security, integration, and release-readiness gates to pass.
20. The goal is a production-quality product, not a throwaway prototype, unless explicitly
    scoped otherwise.

## The four additions

These are not in the source blueprint. Each exists because this team hit the problem it
solves.

21. **Silence is consent, with an audit trail. Surfacing is not the same as blocking.**
    Every question the pipeline raises ships with why it matters, the default it will take,
    when it will take it, and the cost of that default being wrong. Unanswered questions
    become recorded assumptions and the work continues.

    **Surfacing.** A question must actually reach the owner to have been declined. Questions
    arising after an interview get surfaced in their own right — never folded silently into
    the defaults of questions that were asked, and never left to be discovered by whoever
    reads the artifact closely enough. Surfacing costs the owner a glance, not a decision.

    **Blocking.** Work stops for an irreversible commitment (money, legal, production data,
    a client-facing promise), or for owner-held information **with no defensible default**.

    That second condition has two halves and needs both. Almost every product judgement is
    "information only the owner holds" in some sense — his priorities, his risk appetite,
    what he would cut under pressure — and treating that alone as blocking stalls the
    pipeline permanently. The question that decides it is: **can a defensible default be
    stated and recorded?** An externally-issued API key has no default; you cannot proceed
    without it, so it blocks. Which features the owner would cut if time halved has a
    default — the analyst's own reasoned sort, offered for him to overturn — so it surfaces
    and the work continues.

    Expensive to reverse is **not** the same as irreversible. A costly-but-reversible design
    judgement is the pipeline's to make and the owner's to override later; escalating it
    trades autonomy for a decision the owner would have delegated anyway.

    **Classify per question, never in bulk.** A blanket statement over a table of questions
    ("none of these is irreversible") hides the one row that is, and a set of questions
    grouped for convenience is not a set that shares a classification. Each question carries
    its own.
    _Why: a pipeline that merely interrupts rarely still needs its owner; one that defaults
    and records does not. But a pipeline that defaults on questions nobody ever saw is not
    autonomous, it is unaccountable, and from the outside the two look identical. The fix is
    to surface everything and block on almost nothing — conflating the two in either
    direction is how this rule fails._

22. **A correction is not finished until it exists as a check.** When the owner rejects
    something, the fix is incomplete until the lint rule, test, or checklist item that
    prevents its recurrence exists too. Prose guidance in a skill is advisory context; a
    failing check is a hard stop.
    _Why: taste delivered by eyeballing is a human dependency by definition. Encoded taste
    compounds; spoken taste evaporates._

23. **Someone on the team must be structurally unable to read the code.** The blind tester
    holds no source access, no shell, and no logs — enforced by tool allowlist, not by
    instruction. Confusion, unclear copy, and dead ends are invisible to any agent that
    knows what the button was supposed to do.
    _Why: every other reviewer shares the implementer's knowledge, and therefore its blind
    spots._

24. **Whoever attacks the system may not be whoever fixes it.** Red team proves the hole is
    real; blue team proves it is closed; red team re-attacks. This is rule 7 applied to
    security, where the temptation to grade one's own patch is strongest.
    _Why: a fix nobody failed to break is an unverified fix._

## Enforcement

A rule that lives only here is a wish. Each of these must terminate in one of: a tool
allowlist, a gate a workflow refuses to pass, a schema an artifact must validate against,
or a static check in CI. Where a rule has no such terminus yet, that is a known gap, not a
quiet exception.
