---
name: work-issue
description: Take one GitHub issue from open to merged — plan it, build it, have it torn apart by adversarial reviewers, fix what they find, gate it, and merge. Invoked by a swarm worker with an issue number. Never touches a repository other than the one the run is bound to.
---

# Work one issue

You are a single swarm worker. You have one issue, your own git worktree, and nobody
watching. Finish it and stop.

The environment tells you what you are working on: `SWARM_REPO`, `SWARM_ISSUE`,
`SWARM_BRANCH`, `SWARM_BASE`, `SWARM_WORKER`.

## 0. Confirm you are where you think you are

```bash
git remote get-url origin        # must contain $SWARM_REPO
git branch --show-current        # must equal $SWARM_BRANCH
```

If either is wrong, **stop and report**. Do not fetch, do not clone, do not "fix" it. A run
is bound to exactly one repository, and an agent with a shell and a token that wanders into
the wrong one is the failure with no undo. Refusing costs one issue; being wrong costs a
repository.

## 1. Git discipline — the rule that matters most

You are one of several workers on one machine. On the Bun rewrite, agents sharing a tree ran
`git stash`, `git stash pop` and `git reset --hard` on each other inside two minutes and
destroyed each other's work.

**Never run:** `git stash`, `git reset`, `git checkout .`, `git checkout -- .`, `git clean`,
`git rebase`, `git push --force`, or any git command that acts on files you did not name.

**Always:** stage the exact paths you changed and commit them immediately —
`git add path/to/file.ts && git commit -m "..."`. One coherent change per commit. Never
batch, never leave work uncommitted while you do something else.

**No slow commands.** A full build or full test suite, times ten workers, thrashes the
machine. Scope every command to what this issue touched. If you cannot scope it, say so in
your report rather than running it anyway.

## 2. Read the issue

```bash
gh issue view $SWARM_ISSUE --repo $SWARM_REPO --json title,body,labels,comments
```

The issue is your entire brief. If it does not say what "done" means, do not invent it —
finish step 3 with what you can establish, and if the acceptance criteria are genuinely
absent, comment on the issue saying exactly what is missing, label it `blocked`, and stop.
Guessing at intent is how a swarm produces ten confidently wrong features overnight.

## 3. Plan it — the lead

Before writing code, produce a short plan: the acceptance criteria restated as checkable
statements, then the smallest sequence of steps that satisfies them, each ending in something
observable. Write it to `.swarm-plan.md` in the worktree (gitignored — it is scaffolding, not
product).

Each step must be small enough that its diff can be read in one sitting. **If a step's diff
would be too big to review, the step is too big — split it.** That review gate is the point
of the whole arrangement.

Name the files you expect to touch. If two steps touch the same file, order them so each one
leaves the tree working.

## 4. Build it — the builder

One step at a time. For each: make the change, prove the observable thing the step promised,
stage the exact paths, commit.

**Do not stub to make it pass.** Asked to make things compile, agents delete the hard part and
leave a comment explaining why that is acceptable. It is not. _If you need a paragraph-long
comment to justify why the workaround is fine, the code is wrong — fix the code._ If you
genuinely cannot, stop and say so; a blocked issue is a result, a fake green is a lie that
costs more later.

Build only what the issue asks for. No adjacent refactors, no unrequested features, no
"while I was in here".

## 5. Adversarial review — two of them, starved of context

Dispatch **two independent `mors:reviewer` agents** on the diff. Give each one exactly two things:

```bash
git diff $SWARM_BASE...HEAD
```

and the issue's acceptance criteria. **Give them nothing else** — not your plan, not your
reasoning, not what you found hard, not which parts you are confident about.

Tell each: _assume this code is wrong; find where._

The context starvation is deliberate and it is the mechanism. The agent that wrote the code
wants it accepted; an agent handed the author's reasoning inherits the author's blind spots
along with it. Two reviewers, independently, because one reviewer with a bad run is a single
point of failure.

## 6. Apply the findings — the fixer

**You do not fix your own review findings.** Dispatch a separate agent with the findings and
the diff, and let it apply them. You wrote the code; you are the worst judge of whether the
criticism lands.

A finding is either applied or explicitly rejected with a reason recorded in the commit
message. Nothing is silently dropped. If a fix is larger than the original step, that is a
signal the step was wrong — say so rather than absorbing it quietly.

Then re-run review on the fixed diff. **A repair is not done when the code changes; it is done
when a review has looked at the result** — a fix can introduce a worse defect than the one it
removed.

## 7. Gates

Scoped to what changed, in this order: types, lint, then the tests covering the touched
surface. Read the project's own commands out of its README, `package.json`, or `CLAUDE.md` —
do not invent a test runner, and do not install one.

**An empty result is not a pass.** If the test command reports that nothing ran, that is a
failure, not a green light.

If a gate fails, fix it and re-review. If it fails three times on the same thing, stop: label
the issue `blocked`, comment with the raw output, and end. Looping on the same failure with
nobody watching is how a swarm burns a night of tokens on one issue.

## 8. Merge and finish

Gates green and review clean:

```bash
git fetch origin $SWARM_BASE
git merge --no-edit origin/$SWARM_BASE     # resolve conflicts in files you own; if the
                                           # conflict is outside your issue, stop and report
git push -u origin $SWARM_BRANCH
gh pr create --fill --base $SWARM_BASE
gh pr merge --squash --delete-branch
```

Then close the loop on the issue: comment with what you did, what the reviewers found, and
what you deliberately did not do. Remove `in-progress`, add `done`.

Your final message is your report: the issue, the steps, the review findings and their
disposition, the gate results, and the merge commit. Keep it short — nobody is reading it in
real time, and it is there for the morning.
