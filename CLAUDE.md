# Engineers — the mors plugin

This repo IS the `mors` Claude Code plugin. There is no application code here; the
product is `agents/` + `skills/` with the manifests in `.claude-plugin/`, described in
README.md. To use it while developing, start Claude with `claude --plugin-dir .`.

- Agent stubs in `agents/*.md` are deliberately thin — the harness requires a flat file
  per agent. Substance belongs in the matching `skills/<role>/`.
- Inside the plugin, agents and skills are only reachable as `mors:<name>`. A bare name
  resolves to nothing; `bun run check` fails on one.
- Craft skills (`react`, `api-calls`, …) are named for their topic and edited over
  time as the owner reviews real project work — they are living docs, not static ones.
- `templates/project-context/` is a per-project template, deliberately not a plugin skill.
  Keep it generic here; it is copied into each target project's `.claude/skills/` and
  filled in there, where agents load it unprefixed as `project-context`.
- When changing the workflow, keep `README.md`, `skills/orchestrate/`, and
  `skills/plan-feature/` consistent with each other — they describe the same loop.
