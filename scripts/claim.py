#!/usr/bin/env python3
"""Atomic issue claiming for the swarm.

Every worker runs on one machine, so the filesystem gives us a real atomic primitive:
`O_CREAT|O_EXCL` either creates the lock or fails, with no window in between. That is worth
more than it sounds. GitHub has no compare-and-swap — the obvious "list issues, pick an
unlabelled one, add the label" pattern has a read-then-write race, and under ten workers
polling the same repo it fires constantly. Both workers see the issue unlabelled, both label
it, both build it, and you pay twice for a merge conflict.

So the lock on disk is authoritative and the GitHub label is a mirror, written only after the
lock is held. If the two ever disagree, the lock wins.

Locks carry a heartbeat. A worker that is killed, OOMs, or hits a crashed model leaves its
lock behind; without a heartbeat that issue is parked forever and the swarm quietly shrinks.
A lock is stale when its heartbeat is older than the TTL *and* its pid is gone.

Usage:
    claim.py acquire <issue> --worker W [--root DIR] [--ttl S]   exit 0 claimed, 1 taken
    claim.py heartbeat <issue> --worker W
    claim.py release <issue> --worker W
    claim.py list [--root DIR]
    claim.py reap [--root DIR] [--ttl S]      drop stale locks, print what was freed
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

DEFAULT_TTL = 900  # 15 minutes without a heartbeat and we assume the worker is gone


def claims_dir(root: str) -> Path:
    d = Path(root) / ".swarm" / "claims"
    d.mkdir(parents=True, exist_ok=True)
    return d


def lock_path(root: str, issue: str) -> Path:
    return claims_dir(root) / f"{issue}.json"


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    return True


def read_lock(p: Path):
    try:
        return json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        return None


def is_stale(rec, ttl: int) -> bool:
    if not rec:
        return True
    if time.time() - rec.get("heartbeat", 0) <= ttl:
        return False
    pid = rec.get("pid")
    return not (isinstance(pid, int) and pid_alive(pid))


def acquire(root, issue, worker, ttl):
    p = lock_path(root, issue)
    rec = {"issue": issue, "worker": worker, "pid": os.getpid(),
           "claimed_at": time.time(), "heartbeat": time.time()}
    payload = json.dumps(rec, indent=2).encode()

    try:
        fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    except FileExistsError:
        existing = read_lock(p)
        if not is_stale(existing, ttl):
            holder = (existing or {}).get("worker", "unknown")
            print(f"issue {issue} is held by {holder}", file=sys.stderr)
            return 1
        # Stale. Steal it by replacing the file atomically via rename, so a third worker
        # racing us here sees either the old lock or ours — never a half-written file.
        tmp = p.with_suffix(f".steal.{os.getpid()}")
        tmp.write_bytes(payload)
        os.replace(tmp, p)
        after = read_lock(p)
        if not after or after.get("pid") != os.getpid():
            print(f"issue {issue} was stolen from under us", file=sys.stderr)
            return 1
        print(f"claimed {issue} (reclaimed a stale lock held by "
              f"{(existing or {}).get('worker', '?')})")
        return 0

    with os.fdopen(fd, "wb") as fh:
        fh.write(payload)
    print(f"claimed {issue}")
    return 0


def heartbeat(root, issue, worker):
    p = lock_path(root, issue)
    rec = read_lock(p)
    if not rec:
        print(f"no lock for {issue}", file=sys.stderr)
        return 1
    if rec.get("worker") != worker:
        print(f"lock for {issue} belongs to {rec.get('worker')}, not {worker}", file=sys.stderr)
        return 1
    rec["heartbeat"] = time.time()
    tmp = p.with_suffix(f".hb.{os.getpid()}")
    tmp.write_text(json.dumps(rec, indent=2))
    os.replace(tmp, p)
    return 0


def release(root, issue, worker):
    p = lock_path(root, issue)
    rec = read_lock(p)
    if rec and rec.get("worker") != worker:
        # Refuse to release someone else's claim — that is how two workers end up on one
        # issue with neither of them holding it.
        print(f"refusing: {issue} is held by {rec.get('worker')}, not {worker}", file=sys.stderr)
        return 1
    try:
        p.unlink()
    except FileNotFoundError:
        pass
    print(f"released {issue}")
    return 0


def list_claims(root):
    rows = []
    for p in sorted(claims_dir(root).glob("*.json")):
        rec = read_lock(p)
        if not rec:
            continue
        age = int(time.time() - rec.get("heartbeat", 0))
        rows.append((rec.get("issue"), rec.get("worker"), rec.get("pid"), age))
    if not rows:
        print("no active claims")
        return 0
    print(f"{'issue':<10}{'worker':<14}{'pid':<9}{'last heartbeat':>15}")
    for issue, worker, pid, age in rows:
        print(f"{issue:<10}{worker:<14}{pid:<9}{str(age) + 's ago':>15}")
    return 0


def reap(root, ttl):
    freed = []
    for p in sorted(claims_dir(root).glob("*.json")):
        rec = read_lock(p)
        if is_stale(rec, ttl):
            freed.append((rec or {}).get("issue", p.stem))
            p.unlink(missing_ok=True)
    print(f"reaped {len(freed)} stale claim(s)" + (f": {', '.join(map(str, freed))}" if freed else ""))
    return 0


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("action", choices=["acquire", "heartbeat", "release", "list", "reap"])
    ap.add_argument("issue", nargs="?")
    ap.add_argument("--worker", default="w0")
    ap.add_argument("--root", default=".")
    ap.add_argument("--ttl", type=int, default=DEFAULT_TTL)
    a = ap.parse_args(argv)

    if a.action in ("acquire", "heartbeat", "release") and not a.issue:
        ap.error(f"{a.action} needs an issue number")

    return {
        "acquire": lambda: acquire(a.root, a.issue, a.worker, a.ttl),
        "heartbeat": lambda: heartbeat(a.root, a.issue, a.worker),
        "release": lambda: release(a.root, a.issue, a.worker),
        "list": lambda: list_claims(a.root),
        "reap": lambda: reap(a.root, a.ttl),
    }[a.action]()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
