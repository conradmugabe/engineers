#!/usr/bin/env python3
"""The swarm supervisor — point it at one repo, walk away.

    swarm.py run --repo owner/name --workers 10
    swarm.py status --repo owner/name
    swarm.py stop --repo owner/name

One process on your machine. It polls the repository for actionable issues, keeps N workers
busy, and restarts the ones that die. Each worker gets its own git worktree and its own
headless Claude.

**Only the supervisor picks issues.** Workers never choose; they are handed one. That single
fact removes the race rather than managing it — you cannot have contention over a queue that
exactly one thread reads. Dispatch is one pass: select the free issues, label them on GitHub,
record them in the ledger, then spawn. A worker that starts already knows its issue and never
looks at the queue.

The only genuine race left is two supervisors on one workspace — two terminals, or a leftover
process you forgot. That is what the supervisor lock below is for, and it is the whole of the
concurrency control. The per-issue ledger is no longer contention control; it is the in-flight
record, so `status` can tell you what is running and a crash can be recovered from.

**A run is bound to exactly one repository.** The bound repo is written to .swarm/config.json
and every worker re-checks it before touching anything. This is a hard constraint, not a
default: an agent with a shell and a GitHub token that wanders into the wrong repository is
the failure mode with no undo.

Concurrency is a spend dial. The Bun rewrite ran 64 agents at once and cost about $165,000
over eleven days. Start at 2 or 3 and watch what it does before you turn it up.
"""

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

# The ledger is a function call, not a subprocess. Spawning a Python interpreter per issue
# per poll cycle is precisely the "no slow commands inside the loop" rule this project puts
# on its own workers, and it also made the dispatch logic impossible to test in-process.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import claim  # noqa: E402

HEARTBEAT_SECONDS = 60
POLL_SECONDS = 30
READY_LABEL = "ready"
WORKING_LABEL = "in-progress"


def sh(*args, cwd=None, check=False, timeout=None):
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                          check=check, timeout=timeout)


def log(worker, msg):
    print(f"[{time.strftime('%H:%M:%S')}] {worker:<9} {msg}", flush=True)


# ---------------------------------------------------------------- repo binding

def pid_alive(pid: int) -> bool:
    """A pid owned by another user raises PermissionError, not ProcessLookupError — which
    means it exists. Getting this backwards makes a live supervisor look dead and lets a
    second one start, which is the exact race the lock is here to prevent."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def acquire_supervisor_lock(workdir: Path):
    """One supervisor per workspace. This is the only real race in the system.

    Workers cannot collide because they never select. Two supervisors can: both read the same
    queue, both take the first three issues, both spawn. A pidfile created with O_EXCL settles
    it, and a stale one (process gone) is taken over rather than blocking forever.
    """
    p = swarm_root(workdir) / "supervisor.pid"
    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        try:
            other = int(p.read_text().split()[0])
        except (OSError, ValueError, IndexError):
            other = None
        if other and other != os.getpid() and pid_alive(other):
            raise SystemExit(
                f"error: a supervisor is already running for {workdir} (pid {other}).\n"
                f"Two supervisors would both read the same queue and dispatch the same "
                f"issues. Stop that one, or use a different --workdir."
            )
        p.write_text(f"{os.getpid()} {time.time()}\n")
        return p
    with os.fdopen(fd, "w") as fh:
        fh.write(f"{os.getpid()} {time.time()}\n")
    return p


def release_supervisor_lock(p: Path):
    try:
        if p.exists() and p.read_text().split()[0] == str(os.getpid()):
            p.unlink()
    except (OSError, IndexError):
        pass


def swarm_root(workdir: Path) -> Path:
    d = workdir / ".swarm"
    d.mkdir(parents=True, exist_ok=True)
    return d


def bind_repo(workdir: Path, repo: str) -> dict:
    """Record the repository this run is bound to, and refuse to change it silently."""
    cfg_path = swarm_root(workdir) / "config.json"
    if cfg_path.exists():
        cfg = json.loads(cfg_path.read_text())
        if cfg.get("repo") != repo:
            raise SystemExit(
                f"error: {workdir}/.swarm is already bound to {cfg['repo']}.\n"
                f"A workspace serves one repository. Use a different --workdir for {repo}, "
                f"or delete .swarm/ if you are certain nothing is running."
            )
        return cfg
    cfg = {"repo": repo, "bound_at": time.time()}
    cfg_path.write_text(json.dumps(cfg, indent=2))
    return cfg


def ensure_clone(workdir: Path, repo: str) -> Path:
    base = workdir / "repo"
    if (base / ".git").is_dir():
        origin = sh("git", "-C", str(base), "remote", "get-url", "origin").stdout.strip()
        if repo not in origin:
            raise SystemExit(f"error: {base} points at {origin}, not {repo}")
        sh("git", "-C", str(base), "fetch", "--quiet", "origin")
        return base
    log("supervisor", f"cloning {repo}")
    r = sh("gh", "repo", "clone", repo, str(base))
    if r.returncode != 0:
        raise SystemExit(f"error: clone failed\n{r.stderr.strip()}")
    return base


def default_branch(repo_dir: Path) -> str:
    r = sh("git", "-C", str(repo_dir), "symbolic-ref", "refs/remotes/origin/HEAD")
    if r.returncode == 0 and r.stdout.strip():
        return r.stdout.strip().rsplit("/", 1)[-1]
    return "main"


# ---------------------------------------------------------------- work queue

def actionable_issues(repo: str, label: str):
    """Open issues that are ready to be built, oldest first.

    Deliberately conservative: an issue must carry the ready label and must not carry the
    working label. Anything a human is still writing simply has no label yet.
    """
    r = sh("gh", "issue", "list", "--repo", repo, "--state", "open",
           "--label", label, "--limit", "200",
           "--json", "number,title,labels,assignees")
    if r.returncode != 0:
        log("supervisor", f"gh issue list failed: {r.stderr.strip()}")
        return []
    out = []
    for it in json.loads(r.stdout or "[]"):
        names = {l["name"] for l in it.get("labels", [])}
        if WORKING_LABEL in names:
            continue
        out.append({"number": it["number"], "title": it["title"]})
    return sorted(out, key=lambda i: i["number"])


# ---------------------------------------------------------------- worker

def free_gb(path: Path) -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / 1e9


def worktree_cost_gb(repo_dir: Path) -> float:
    """What one worker's tree costs, measured rather than guessed.

    The checkout itself is usually small; the expensive part is whatever the project's own
    install puts there. Measuring the repo gives a floor, not the truth, so callers treat it
    as a lower bound and keep headroom.
    """
    total = 0
    for root, dirs, files in os.walk(repo_dir):
        if ".git" in dirs:
            dirs.remove(".git")
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total / 1e9


def merge_landed(repo_dir: Path, branch: str, base: str) -> bool:
    """Did this branch actually reach the base branch on the remote?

    Asked before deleting anything. A worker that believes it merged and did not is the one
    case where cleaning up destroys real work, so this checks the remote rather than trusting
    the worker's own report. A squash-merge leaves no ancestry, so the branch being gone from
    the remote is also accepted as evidence it was merged and deleted.
    """
    sh("git", "-C", str(repo_dir), "fetch", "--quiet", "--prune", "origin")
    merged = sh("git", "-C", str(repo_dir), "branch", "-r", "--merged", f"origin/{base}")
    if f"origin/{branch}" in merged.stdout:
        return True
    still_there = sh("git", "-C", str(repo_dir), "ls-remote", "--heads", "origin", branch)
    return still_there.returncode == 0 and not still_there.stdout.strip()


def remove_worktree(repo_dir: Path, wt: Path, branch: str):
    """Remove a worktree and its local branch, properly.

    `rm -rf` alone leaves administrative files under .git/worktrees, and the next
    `worktree add` on that path fails with a stale-lock error nobody enjoys diagnosing.
    """
    sh("git", "-C", str(repo_dir), "worktree", "remove", "--force", str(wt))
    shutil.rmtree(wt, ignore_errors=True)
    sh("git", "-C", str(repo_dir), "worktree", "prune")
    sh("git", "-C", str(repo_dir), "branch", "-D", branch)


def dispatch(repo, workdir, repo_dir, free, label, claim_ttl):
    """Select up to `free` issues and hand them out. The only place issues are chosen.

    Single-threaded by construction, so the selection needs no locking of its own. Each issue
    is recorded in the ledger and labelled on GitHub *before* a worker exists for it, so what
    you see on GitHub is true from the moment it is true, rather than a mirror written
    afterwards by whoever won a race.
    """
    claim.reap(str(workdir), claim_ttl)

    in_flight = {p.stem for p in (workdir / ".swarm" / "claims").glob("*.json")}
    queue = [i for i in actionable_issues(repo, label) if str(i["number"]) not in in_flight]

    assigned, slot = [], 0
    for issue in queue:
        if len(assigned) >= free:
            break
        slot += 1
        name = f"w{slot}"
        n = str(issue["number"])

        if claim.acquire(str(workdir), n, name, claim_ttl) != 0:
            # Should not happen — nothing else selects. If it does, something is wrong with
            # our assumptions rather than with this issue, so say so loudly.
            log("supervisor", f"unexpected: #{n} is already in the ledger — nothing else "
                              f"should be selecting issues")
            continue

        lr = sh("gh", "issue", "edit", n, "--repo", repo,
                "--add-label", WORKING_LABEL, "--remove-label", label)
        if lr.returncode != 0:
            # If we cannot mark it taken, do not build it: a second run of the supervisor,
            # or you looking at GitHub, would both see it as free.
            log("supervisor", f"#{n} skipped — could not label it: {lr.stderr.strip()}")
            claim.release(str(workdir), n, name)
            continue

        assigned.append((name, issue))
    return assigned


class Worker(threading.Thread):
    def __init__(self, name, workdir, repo, repo_dir, base_branch, issue, claim_ttl,
                 permission_mode, model, stop_event):
        super().__init__(daemon=True)
        self.name, self.workdir, self.repo = name, workdir, repo
        self.repo_dir, self.base_branch = repo_dir, base_branch
        self.issue, self.claim_ttl = issue, claim_ttl
        self.permission_mode, self.model = permission_mode, model
        self.stop_event = stop_event
        self.outcome = None
        self.proc = None

    # ---- ledger lifecycle. The supervisor acquired the entry; this worker only keeps it
    # warm while it runs and drops it when finished. It never selects and never claims.
    def _release(self):
        claim.release(str(self.workdir), str(self.issue["number"]), self.name)

    def _heartbeat_loop(self):
        while not self.stop_event.is_set() and self.proc and self.proc.poll() is None:
            claim.heartbeat(str(self.workdir), str(self.issue["number"]), self.name)
            self.stop_event.wait(HEARTBEAT_SECONDS)

    # ---- worktree
    def _worktree(self, branch):
        wt = self.workdir / "worktrees" / self.name
        if wt.exists():
            sh("git", "-C", str(self.repo_dir), "worktree", "remove", "--force", str(wt))
            shutil.rmtree(wt, ignore_errors=True)
        wt.parent.mkdir(parents=True, exist_ok=True)
        sh("git", "-C", str(self.repo_dir), "worktree", "prune")
        r = sh("git", "-C", str(self.repo_dir), "worktree", "add", "-b", branch,
               str(wt), f"origin/{self.base_branch}")
        if r.returncode != 0:
            log(self.name, f"worktree failed: {r.stderr.strip()}")
            return None
        return wt

    def run(self):
        n = self.issue["number"]
        threading.Thread(target=self._heartbeat_loop, daemon=True).start()
        try:
            branch = f"swarm/{n}"
            wt = self._worktree(branch)
            if wt is None:
                self.outcome = "worktree-failed"
                return

            log(self.name, f"#{n} {self.issue['title'][:56]}")
            cmd = ["claude", "-p", f"/work-issue {n}",
                   "--permission-mode", self.permission_mode]
            if self.model:
                cmd += ["--model", self.model]
            env = {**os.environ, "SWARM_WORKER": self.name, "SWARM_REPO": self.repo,
                   "SWARM_ISSUE": str(n), "SWARM_BRANCH": branch,
                   "SWARM_BASE": self.base_branch}
            self.proc = subprocess.Popen(cmd, cwd=str(wt), env=env,
                                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                         text=True)
            transcript = self.workdir / "logs" / f"{self.name}-issue-{n}.log"
            transcript.parent.mkdir(parents=True, exist_ok=True)
            with open(transcript, "w") as fh:
                for line in self.proc.stdout:
                    fh.write(line)
            code = self.proc.wait()
            self.outcome = "done" if code == 0 else f"exit-{code}"
            log(self.name, f"#{n} {self.outcome} — log: {transcript}")

            # The worker owns the outcome label; a failure goes back to the queue only
            # after a human looks, because an issue that fails forever burns tokens forever.
            if code == 0 and merge_landed(self.repo_dir, branch, self.base_branch):
                remove_worktree(self.repo_dir, wt, branch)
                log(self.name, f"#{n} merged — worktree removed, "
                               f"{free_gb(self.workdir):.1f}GB free")
            elif code == 0:
                # It exited clean but nothing reached the base branch. Keep the tree: this is
                # the case where deleting would destroy the only copy of real work.
                self.outcome = "merge-not-found"
                log(self.name, f"#{n} exited clean but no merge landed — keeping {wt}")

            if code != 0:
                # Failure keeps its worktree on purpose. The transcript says what the worker
                # thought; the tree is the only place the state that broke it still exists.
                log(self.name, f"#{n} failed — worktree kept for diagnosis at {wt}")
                sh("gh", "issue", "edit", str(n), "--repo", self.repo,
                   "--add-label", "blocked", "--remove-label", WORKING_LABEL)
                sh("gh", "issue", "comment", str(n), "--repo", self.repo, "--body",
                   f"Swarm worker `{self.name}` could not complete this issue "
                   f"(exit {code}). Transcript: `{transcript.name}`. Worktree kept at "
                   f"`{wt}` for diagnosis. Labelled `blocked` rather than returned to "
                   f"`ready`, so it does not retry forever.")
        finally:
            self._release()


# ---------------------------------------------------------------- supervisor

def run(args):
    workdir = Path(args.workdir).resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    bind_repo(workdir, args.repo)
    lock = acquire_supervisor_lock(workdir)
    repo_dir = ensure_clone(workdir, args.repo)
    base = default_branch(repo_dir)

    # Disk is the one resource a cgroup will not protect: the v2 io controller caps
    # bandwidth, not capacity. And it is the resource this design spends hardest, because
    # every worker gets its own checkout and runs the project's own install in it.
    #
    # Cleaning up on merge makes the ceiling `workers x tree`, a constant rather than
    # something that grows all night — which is the only reason a number checked here is
    # still true an hour later.
    avail = free_gb(workdir)
    per_worker = max(worktree_cost_gb(repo_dir), 0.05)
    projected = per_worker * args.workers
    log("supervisor", f"disk: {avail:.1f}GB free, ~{per_worker:.2f}GB per worktree, "
                      f"~{projected:.1f}GB for {args.workers} worker(s)")
    if avail < args.min_free_gb:
        raise SystemExit(
            f"error: {avail:.1f}GB free is below the {args.min_free_gb}GB floor.\n"
            f"Free space or lower --min-free-gb, but understand what you are choosing: "
            f"filling the disk does not fail one issue, it takes the machine down."
        )
    if projected > avail - args.min_free_gb:
        safe = max(1, int((avail - args.min_free_gb) / per_worker))
        log("supervisor", f"warning: {args.workers} workers may not fit. "
                          f"~{safe} would sit inside the floor. Install size is measured "
                          f"from the repo and is a lower bound — dependencies land later.")
    log("supervisor", f"bound to {args.repo} (base branch {base}), {args.workers} worker(s)")

    stop = threading.Event()

    def handle(signum, _frame):
        log("supervisor", "stopping — letting in-flight workers finish, claims will release")
        stop.set()
    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)

    active, idle_polls = {}, 0
    while not stop.is_set():
        for name, w in list(active.items()):
            if not w.is_alive():
                active.pop(name)

        # Pausing costs throughput; filling the disk costs the machine.
        if free_gb(workdir) < args.min_free_gb:
            log("supervisor", f"paused — {free_gb(workdir):.1f}GB free is under the "
                              f"{args.min_free_gb}GB floor. Waiting for workers to finish "
                              f"and release their trees.")
            stop.wait(POLL_SECONDS)
            continue

        free = args.workers - len(active)
        if free > 0:
            assigned = dispatch(args.repo, workdir, repo_dir, free, args.label,
                                args.claim_ttl)

            if not assigned and not active:
                idle_polls += 1
                if args.once:
                    log("supervisor", "queue empty — exiting (--once)")
                    break
                if idle_polls == 1:
                    log("supervisor", f"queue empty, polling every {POLL_SECONDS}s")
            else:
                idle_polls = 0

            if assigned:
                sh("git", "-C", str(repo_dir), "fetch", "--quiet", "origin")
            for name, issue in assigned:
                # Names come from dispatch, but a slot may still be busy; take the first free.
                if name in active:
                    name = next((f"w{i}" for i in range(1, args.workers + 1)
                                 if f"w{i}" not in active), name)
                w = Worker(name, workdir, args.repo, repo_dir, base, issue,
                           args.claim_ttl, args.permission_mode, args.model, stop)
                active[name] = w
                w.start()

        stop.wait(POLL_SECONDS if not active else 5)

    for w in active.values():
        w.join(timeout=args.grace)
    release_supervisor_lock(lock)
    log("supervisor", "stopped")
    return 0


def status(args):
    workdir = Path(args.workdir).resolve()
    cfg_path = workdir / ".swarm" / "config.json"
    if not cfg_path.exists():
        print(f"no swarm workspace at {workdir}")
        return 1
    cfg = json.loads(cfg_path.read_text())
    print(f"workspace : {workdir}")
    print(f"bound to  : {cfg['repo']}\n")
    claim.list_claims(str(workdir))
    queue = actionable_issues(cfg["repo"], args.label)
    print(f"\n{len(queue)} issue(s) ready and unclaimed")
    for i in queue[:10]:
        print(f"  #{i['number']:<6}{i['title'][:64]}")
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--repo", help="owner/name — the ONE repository this run may touch")
        p.add_argument("--workdir", default=str(Path.home() / ".swarm-workspaces" / "default"))
        p.add_argument("--label", default=READY_LABEL)
        return p

    r = common(sub.add_parser("run", help="start the swarm"))
    r.add_argument("--workers", type=int, default=3,
                   help="concurrent builders. This is a spend dial — start low.")
    r.add_argument("--model", default=None)
    r.add_argument("--permission-mode", default="acceptEdits",
                   help="passed to claude. Do not disable permission checks wholesale.")
    r.add_argument("--claim-ttl", type=int, default=900)
    r.add_argument("--grace", type=int, default=120)
    r.add_argument("--once", action="store_true", help="drain the queue and exit")
    r.add_argument("--min-free-gb", type=float, default=10.0,
                   help="stop dispatching below this much free disk. Cgroups cap memory "
                        "and CPU but not capacity, so this is the only guard there is.")

    common(sub.add_parser("status", help="what is claimed and what is waiting"))

    a = ap.parse_args(argv)
    if a.cmd == "run":
        if not a.repo:
            ap.error("run needs --repo owner/name")
        return run(a)
    return status(a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
