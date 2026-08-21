# Swarm — autonomous issue builders

Point it at one GitHub repository. It reads the open issues, claims them, builds them, tears
them apart in adversarial review, fixes what that finds, gates them, and merges. You start it
and walk away.

```bash
scripts/swarm.py run --repo owner/name --workers 3
scripts/swarm.py status --repo owner/name
```

There is no planning here. No ideation, no interview, no brief. Issues arrive already written;
this builds them.

## How a worker spends an issue

```
claim (atomic, on disk)
  → lead plans it            concrete steps, each ending in something observable
  → builder implements       one step, one commit, named paths only
  → 2× adversarial review    given the diff and nothing else: "assume it is wrong"
  → fixer applies findings   never the builder — it wants its own code accepted
  → gates                    types, lint, tests scoped to what changed
  → merge, push, release
```

## The rules that make it survivable

**One repository per run.** Bound in `.swarm/config.json` and re-checked by every worker
before it touches anything. An agent with a shell and a token that wanders into the wrong
repository is the failure with no undo.

**Claims are a local file lock.** `O_CREAT|O_EXCL` is atomic; GitHub has no compare-and-swap,
so the read-then-label pattern races and two workers build the same issue. The lock is
authoritative, the label is a mirror. Locks heartbeat, so a dead worker releases its issue
instead of parking it forever.

**One worktree per worker.** Not a convention — a structural impossibility of the failure
where agents run `git stash` and `git reset --hard` on each other.

**Git commands are allowlisted.** No `stash`, no `reset`, no `checkout .`, no `clean`, no
command touching files the worker did not name. Commit named paths immediately, never batch.

**Reviewers are starved of context deliberately.** They get the diff and the acceptance
criteria. Not the plan, not the reasoning, not what the builder found hard. The agent that
wrote the code wants it accepted; an agent handed the author's reasoning inherits the author's
blind spots.

**No stubbing to reach green.** If it takes a paragraph-long comment to justify why the
workaround is fine, the code is wrong — fix the code.

**An empty result is not a pass.** A test command reporting that nothing ran is a failure.

**A failed issue is labelled `blocked`, not returned to the queue.** An issue that retries
forever burns tokens forever.

## Concurrency is a spend dial

`--workers` is a cost decision, not a throughput one. The Bun rewrite ran 64 agents at once
and spent roughly $165,000 over eleven days. Start at 2 or 3, watch a night of it, then turn
it up.

## Layout

```
scripts/swarm.py            supervisor: polls, spawns, reaps, restarts
scripts/claim.py            atomic claiming, heartbeats, stale reclaim
scripts/check-template.py   integrity checks on this template itself
.claude/skills/work-issue/  what one worker does, start to finish
.claude/agents/             backend, frontend, qa, reviewer, hacker, security, blind-tester
docs/swarm-architecture.md  why it is shaped this way
docs/constitution.md        the rules that hold regardless of task
```

Prior art: [Rewriting Bun in Rust using AI agents](https://bun.com/blog/bun-in-rust) — the
role split, the git discipline, and the resource limits here are lifted from that run.
