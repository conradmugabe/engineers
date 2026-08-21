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

**Only the supervisor picks issues.** Workers never choose; each is handed one before it
starts. There is no race over a queue that exactly one thread reads. Dispatch is a single
pass — select, record, label on GitHub, then spawn — so what you see on GitHub is true from
the moment it is true. If the label fails, the issue is not built.

**One supervisor per workspace**, enforced by a pidfile. Two supervisors is the only real
contention left, and it is what a second terminal gets you.

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

**Merged work has its worktree deleted; failed work keeps it.** That makes peak disk
`workers x tree` instead of something that grows all night, which is the only reason the
`--min-free-gb` floor means anything. The merge is verified against the remote first — a
worker that believes it merged and did not is the one case where cleanup destroys real work.
A failure keeps its tree because the transcript says what the worker thought and the tree is
the only place the state that broke it still exists.

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
