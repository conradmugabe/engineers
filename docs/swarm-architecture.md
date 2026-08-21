# The swarm — autonomous issue builders

**What this is now.** You point it at one GitHub repository. It reads the open issues,
claims them, builds them, reviews them adversarially, and merges. You start it and walk
away. There is no ideation, no interview, no brief. Planning happens in a different tool
you are building; this one only builds.

**What it deliberately is not.** Not a planner. Not a chat. Not multi-repo — a run is
bound to exactly one repository and refuses to touch another.

## Shape

```
you:     swarm run --repo owner/name --workers 10
              │
              ├── supervisor (one process, your machine)
              │     • polls the repo for actionable issues
              │     • holds the concurrency limit
              │     • spawns and reaps workers, restarts crashed ones
              │
              └── worker × N   (each: own git worktree, own headless claude)
                    1. claim an issue        ← atomic, or you get duplicate work
                    2. lead plans it          smart engineer: concrete steps
                    3. builder implements     one step, one commit
                    4. 2× adversarial review  context-starved, "assume it is wrong"
                    5. fixer applies          only accepted findings
                    6. gates: lint, types, tests
                    7. merge, push, release the claim
                    8. loop
```

## The five decisions that matter

**1. Claiming is a local file lock, not a GitHub label.** Every worker runs on your one
machine, so `O_CREAT|O_EXCL` gives real atomicity for free. GitHub has no compare-and-swap:
a read-then-label pattern races, and two workers both "successfully" claim the same issue.
The lock is authoritative; the GitHub label is a mirror for your visibility, written after
the lock is held. Locks carry a heartbeat, so a worker that dies releases its issue rather
than parking it forever.

**2. One worktree per worker.** From the Bun rewrite: agents sharing a working tree ran
`git stash` and `git reset --hard` on each other within two minutes. Worktrees make that
impossible rather than discouraged.

**3. Git commands are allowlisted, not merely guided.** Every worker is forbidden
`git stash`, `git reset`, `git checkout .`, `git clean`, and any command that touches files
it did not name. Commit specific paths, immediately, no batching. This is the single rule
whose absence broke their first run.

**4. Reviewers are starved of context on purpose.** The reviewer gets the diff and the
acceptance criteria — never the builder's reasoning, never its plan. Sumner's framing is
exactly right: *the Claude that wrote the code wants it accepted; the Claude that reviews
wants to find issues.* Two reviewers per build, independent, both told to assume the code is
wrong.

**5. A fixer applies findings, not the builder.** The builder defends its work; the fixer has
no stake in it.

## Rules carried over from the Bun run

- **No slow commands inside the loop.** A full build or full test suite per worker × 10
  workers will thrash the machine. Scope every command to what the issue touched.
- **No stubbing to make it pass.** Asked to make things compile, agents stub the failing
  function out. The rule that fixed it: *if you need a paragraph-long comment to justify why
  the workaround is fine, the code is wrong — fix the code.*
- **Resource limits are not optional.** Their machine ran out of disk and crashed repeatedly
  at high concurrency. Workers run under a cgroup with a memory and disk ceiling.
- **Cost is real.** Their 11-day rewrite cost roughly $165,000 at API pricing. Concurrency is
  a spend dial, which is why it is a flag rather than a constant.

## What carries over from what we already built

Kept: `backend-engineer`, `frontend-engineer`, `qa-engineer`, `reviewer`, `hacker`,
`security-engineer`, `blind-tester`, the gate discipline, and the rule that no agent judges
its own work.

Dropped: `/new-idea`, `intake`, `product-analyst`, `researcher`, the nine-stage lifecycle,
the brief schemas and `check-brief.py`. Planning lives in your other tool now.
