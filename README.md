# Engineers

A portable AI engineering team for Claude Code. Drop the `.claude/` directory into any
project and you get a full team: a principal engineer to plan with, an orchestrator to
run the work, and specialist engineers that implement, review, and test — coordinated
through GitHub Issues, non-blocking, verified at every gate.

## The team

| Role | Runs as | Model | Access |
|---|---|---|---|
| Principal engineer | Interactive session + `/plan-feature` | Fable | Full |
| Orchestrator | Interactive session + `/orchestrate` | Fable/Opus | Full |
| Backend engineer | Subagent | Opus | Full tools |
| Frontend engineer | Subagent | Opus | Full tools |
| QA engineer | Subagent | Opus | Full tools |
| Reviewer | Subagent | Opus | Read + execute only — cannot edit files |
| Blind tester | Subagent | Opus | Browser only — **cannot open a single source file** |

Each subagent is a thin stub in `.claude/agents/*.md` (the harness needs a flat file to
register it). The real definition — playbook, templates, standards — lives in a matching
directory under `.claude/skills/<role>/`, which the agent loads as its first action.

## The flow

```
1. PLAN      You + /plan-feature (Fable): talk through the product, produce a spec,
             file self-contained GitHub issues labeled `ready`, dependencies marked.

2. WORK      A second session runs /orchestrate. Per issue, it:
             dispatch engineer (background, isolated worktree)
               → engineer reports done
               → orchestrator runs the tests ITSELF (never trusts the report)
               → reviewer attacks the diff (adversarial, read-only)
               → QA engineer attacks the behavior (writes/extends automated tests)
               → merge to the feature branch
             Issues run in parallel when independent. The orchestrator is idle
             between events, not blocked.

3. FEEL      Once a feature's issues are merged: orchestrator starts the app and
             dispatches the blind tester — a non-technical user persona with browser
             tools only. It gets a URL and the product story, never the code. Its
             confusion is data. Findings come back as new GitHub issues.

4. LOOP      Until the `ready` queue is dry. State lives in issue labels
             (`ready → in-progress → in-review → blocked/done`), so any new
             orchestrator session recovers the full picture from `gh`.
```

## Two-layer skills

**Core layer** (portable, improves over time, travels to every project):

- `plan-feature`, `orchestrate` — the two workflow playbooks
- `backend-engineer`, `frontend-engineer`, `qa-engineer`, `reviewer`, `blind-tester` — role playbooks
- `conventions` — **the owner's accumulated preferences as a developer.** Every agent
  loads it. The principal engineer updates it whenever the owner expresses a preference.
  This is how the team learns.

**Project layer** (created per project, never copied back):

- `project-context` — stack, architecture, domain glossary, how to run the app.
  Ships as a template; `/plan-feature` fills it in during project setup.
- Any project-specific skills the project needs (e.g. `design-system` for its visual
  language). Role playbooks check for these and load them when present.

On conflict, the project layer wins — `conventions` says how the owner likes software
built anywhere; `project-context` says what is true here.

## Installing into a project

```bash
cp -r .claude/ /path/to/project/.claude/
cd /path/to/project
gh label create ready && gh label create in-progress && gh label create in-review && gh label create blocked
claude   # then: /plan-feature — first run fills in project-context
```

## Ground rules

- The orchestrator **verifies, never trusts**. Reports are claims; tests and reviews are facts.
- Nothing auto-merges to `main`. Feature branches yes; `main` is the owner's call.
- Max 3 engineers in flight — merge coordination cost beats throughput beyond that, early on.
- All coordination state lives in GitHub Issues, never in a conversation's memory.
