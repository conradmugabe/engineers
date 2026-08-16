# Engineers — template repo

This repo IS the portable AI engineering team template. There is no application code
here; the product is the `.claude/` directory (agents + skills) described in README.md.

- Agent stubs in `.claude/agents/*.md` are deliberately thin — the harness requires a
  flat file per agent. Substance belongs in the matching `.claude/skills/<role>/`.
- `skills/conventions/` holds the owner's developer preferences and is expected to be
  edited over time — that is the learning mechanism, not a static doc.
- `skills/project-context/` is a per-project template. Keep it generic here; it gets
  filled in inside each target project.
- When changing the workflow, keep `README.md`, `skills/orchestrate/`, and
  `skills/plan-feature/` consistent with each other — they describe the same loop.
