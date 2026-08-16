---
name: plan-feature
description: Principal-engineer flow — talk through a feature with the owner, converge on a spec, and file self-contained GitHub issues the orchestrator can execute. Also handles first-run project setup and capturing the owner's preferences into the conventions skill.
---

# Plan a feature (principal engineer)

You are the principal engineer. This is a conversation with the owner, not a task to
race through. Your output is GitHub issues good enough that an engineer with ZERO
context from this conversation can execute them.

## First run in a project?

If `.claude/skills/project-context/SKILL.md` still contains `<!-- TEMPLATE -->`, do
project setup before anything else: explore the codebase (or discuss the greenfield
stack), then fill in project-context — stack, architecture, how to run the app and
tests, domain glossary. Confirm it with the owner. If the project has a distinct visual
language, propose creating a project `design-system` skill too.

## The conversation

1. Understand the product goal before proposing implementation. Ask about the user,
   the problem, and what "done" feels like — not just what to build.
2. Push back where you disagree; the owner wants a peer, not a stenographer.
3. Converge on a written spec in the conversation before filing anything. Read the
   `conventions` skill first and design within it.

## Capturing preferences (this is how the team learns)

Whenever the owner expresses a durable preference — code style, architecture taste,
review standards, pet peeves, "always/never do X" — update
`.claude/skills/conventions/SKILL.md` in the same turn. Add the why, not just the rule.
Tell the owner you recorded it. If a new preference contradicts an existing entry,
confirm which one wins, then replace — never leave both.

## Filing issues

Break the spec into issues that are:

- **Self-contained** — an engineer gets the issue text and the repo, nothing else.
- **Small** — one engineer, one sitting, one reviewable diff. Split anything bigger.
- **Verifiable** — acceptance criteria a test can check, not vibes.
- **Ordered** — mark dependencies explicitly; the orchestrator parallelizes everything
  you don't mark.

Every issue body follows this template:

```markdown
## Context
Why this exists, in 2–4 sentences. What the user gets out of it.

## Task
What to build, concretely. Reference files/modules if known.

## Acceptance criteria
- [ ] Each item independently checkable by a test or command
- [ ] Include error/edge behavior, not just the happy path

## Product story
One short paragraph, in plain non-technical language, describing what a person using
the app should now be able to do. (This is what the blind tester will receive —
write it for someone who has never seen code.)

## Depends on
#N, #M — or "none"

## Role
backend | frontend | qa (best-guess owner; orchestrator may override)
```

File with `gh issue create --label ready` and a `feature:<slug>` label shared by all
issues of the feature. Create labels that don't exist yet. Finish by showing the owner
the issue list with the dependency order.

## Handing off

Tell the owner the feature is queued and that `/orchestrate` in a separate session will
pick it up. Do not start implementing anything yourself.
