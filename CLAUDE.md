# Engineers — template repo

This repo IS the portable AI engineering team template. There is no application code
here; the product is the `.claude/` directory (agents + skills) described in README.md.

- Agent stubs in `.claude/agents/*.md` are deliberately thin — the harness requires a
  flat file per agent. Substance belongs in the matching `.claude/skills/<role>/`.
- Craft skills (`react`, `api-calls`, …) are named for their topic and edited over
  time as the owner reviews real project work — they are living docs, not static ones.
- `skills/project-context/` is a per-project template. Keep it generic here; it gets
  filled in inside each target project.
- When changing the workflow, keep `README.md`, `skills/orchestrate/`, and
  `skills/plan-feature/` consistent with each other — they describe the same loop.
