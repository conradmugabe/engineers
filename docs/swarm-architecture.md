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

**1. Only the supervisor picks issues. Workers are handed one.**

This is the decision that removes the race instead of managing it. There is no contention
over a queue that exactly one thread reads, so no worker ever needs to ask whether an issue
is taken — it is told which issue is its own before it starts.

Dispatch is one pass, single-threaded: select the free issues, record them in the ledger,
label them on GitHub, then spawn. Because the label is written *before* a worker exists, what
you see on GitHub is true from the moment it is true, rather than a mirror written afterwards
by whoever won a race. If the label call fails, the issue is not built and its ledger entry is
rolled back — an issue we cannot mark as taken is one a second run would pick up again.

The alternative — every worker polls, picks something that looks free, and labels it — races
badly. GitHub has no compare-and-swap, so two workers both see an issue unlabelled, both label
it, both build it, and you pay twice and merge once.

**The only genuine race left is two supervisors** on one workspace: two terminals, or a
leftover process. A pidfile created with `O_CREAT|O_EXCL` settles that, and it is the whole of
the concurrency control. A stale pidfile whose process is gone is taken over rather than
blocking forever — and note that a pid owned by another user raises `PermissionError` rather
than `ProcessLookupError`, so getting that check backwards makes a live supervisor look dead
and lets a second one start.

**The per-issue ledger is not contention control.** It is the in-flight record: what is
running, under which worker, since when. It answers `status`, and it survives a crash so the
next run knows what was mid-flight. Entries heartbeat, so a worker killed mid-issue frees it
instead of parking it forever.

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
- **Resource limits are not optional, and they are two problems, not one.** Their machine ran
  out of disk and crashed repeatedly at high concurrency, and separately their debug-build
  tests blew past time limits.

  A **cgroup** boxes a process and everything it spawns under hard memory, CPU and
  process-count ceilings, so a runaway worker is killed by the kernel instead of competing
  with the whole machine. That matters most when nobody is watching: without a ceiling the
  OOM killer picks a victim at random at 3am, and it might be the supervisor.

  **Cgroups do not limit disk space** — the v2 `io` controller caps bandwidth, not capacity.
  Disk needs a different answer, and this design spends it hard: every worker gets its own
  checkout and runs the project's own install inside it, so ten workers on a Node project is
  five to ten gigabytes before anything is built.

  The answer is to make the number bounded and then check it. **A worktree is removed as soon
  as its issue is verified merged**, so peak usage is `workers x tree` — a constant, whatever
  the throughput. Without that it grows all night and any preflight number is stale within the
  hour. A floor (`--min-free-gb`) refuses to start below it and pauses dispatch if it is
  crossed mid-run: pausing costs throughput, filling the disk costs the machine.

  **Failure keeps its worktree.** The transcript records what the worker thought; the tree is
  the only place the state that broke it still exists. And "merged" is verified against the
  remote rather than taken from the worker's report — a worker that believes it merged and did
  not is the one case where cleaning up destroys real work.
- **Cost is real.** Their 11-day rewrite cost roughly $165,000 at API pricing. Concurrency is
  a spend dial, which is why it is a flag rather than a constant.

## What carries over from what we already built

Kept: `backend-engineer`, `frontend-engineer`, `qa-engineer`, `reviewer`, `hacker`,
`security-engineer`, `blind-tester`, the gate discipline, and the rule that no agent judges
its own work.

Dropped: `/new-idea`, `intake`, `product-analyst`, `researcher`, the nine-stage lifecycle,
the brief schemas and `check-brief.py`. Planning lives in your other tool now.
