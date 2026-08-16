---
name: conventions
description: The owner's accumulated preferences and standards as a developer. Loaded by every agent before working. Updated by the principal engineer whenever the owner expresses a durable preference — this file is how the team learns.
---

# Conrad's conventions

This file grows over time. Every entry has a rule AND the why — a rule without its
reason gets misapplied. The principal engineer adds entries during `/plan-feature`
conversations; agents treat everything here as non-negotiable unless
`project-context` explicitly overrides it for a specific project.

Format for entries:

```
### <short rule>
**Why:** <the reason, in the owner's terms>
**Applies to:** all | backend | frontend | qa | review
```

---

## Process

### Issues are the only source of truth for work state
**Why:** Sessions die and contexts get summarized; GitHub survives. Anything not
written to an issue effectively didn't happen.
**Applies to:** all

### Reports show their work
**Why:** "Tests pass" is a claim. The command and its output is evidence. The
orchestrator gates on evidence only.
**Applies to:** all

### The owner's suggestions are proposals, not directives
**Why:** Conrad thinks by discussing. When he suggests something, he wants it engaged
with — sharpened, extended, or argued against — not folded in verbatim. Blind
agreement wastes the review he's offering. Push back where an idea is weak, say where
you'd change it, THEN implement the version you both landed on.
**Applies to:** all

## Code

<!-- Entries accumulate here as Conrad expresses preferences.
     Examples of what belongs: naming taste, error-handling style, comment policy,
     dependency philosophy, testing style, PR/commit format preferences. -->

*(none recorded yet — this file has just been created)*

## Review standards

*(none recorded yet)*

## Product

*(none recorded yet)*
