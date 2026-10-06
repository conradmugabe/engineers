# Swarm — autonomous issue builders

Point it at one GitHub repository. It reads the open issues, claims them, builds them, tears
them apart in adversarial review, fixes what that finds, gates them, and merges. You start it
and walk away.

```bash
bun install                                       # once
bun scripts/swarm.ts run --repo owner/name --workers 3
bun scripts/swarm.ts status
bun scripts/swarm.ts stop                         # in-flight workers finish first
```

Written in TypeScript on [Bun](https://bun.sh). `bun test` runs the suite, `bun run typecheck`
the strict type check, `bun run check` the template's integrity check.

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

## Every worker runs in a box

Each worker is launched inside a cgroup with hard memory, CPU and process ceilings, sized
from available RAM divided by worker count. A runaway worker — a test that never terminates,
a build that allocates without bound — is then killed by the kernel alone, instead of
competing with the whole machine while nobody is watching. It exits non-zero, which the swarm
already handles: the issue is labelled `blocked` and its worktree is kept.

Swap is disabled inside the box on purpose. A worker that swaps instead of dying is how a
machine ends up locked but not crashed, which is worse — nothing fails, so nothing recovers.

`--memory-max` and `--cpu-quota` override the defaults; `--no-limits` turns the box off and
says so loudly. If cgroups are unavailable the swarm still runs, but warns rather than
pretending it is protected.

## Concurrency is a spend dial

`--workers` is a cost decision, not a throughput one. The Bun rewrite ran 64 agents at once
and spent roughly $165,000 over eleven days. Start at 2 or 3, watch a night of it, then turn
it up.

Disk stopped being the binding constraint once merged worktrees are removed; RAM during
builds is what actually limits you. A headless agent is a few hundred megabytes, but the
build and test runner it spawns can spike to several gigabytes, and the box covers the whole
process tree — which is the point.

## Layout

```
scripts/swarm.ts            supervisor: polls, dispatches, spawns, reaps
scripts/claim.ts            in-flight ledger: atomic entries, heartbeats, stale reclaim
scripts/check-template.ts   integrity checks on this template itself
scripts/*.test.ts           bun test suites for the above
.claude/skills/work-issue/  what one worker does, start to finish
.claude/agents/             backend, frontend, qa, reviewer, hacker, security, blind-tester
docs/swarm-architecture.md  why it is shaped this way
docs/constitution.md        the rules that hold regardless of task
```

Prior art: [Rewriting Bun in Rust using AI agents](https://bun.com/blog/bun-in-rust) — the
role split, the git discipline, and the resource limits here are lifted from that run.
