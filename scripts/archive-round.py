#!/usr/bin/env python3
"""Archive the current critique and verdict before a new round overwrites them.

Round 1 of the first real run is gone. Its critique and verdict were written to
`docs/<slug>.critique.md` and `docs/<slug>.verdict.md`, and round 2 wrote to the same two
paths. Nothing malicious, nothing unusual — just single mutable paths in a loop that runs
more than once.

That matters more here than it would elsewhere. This pipeline's central claim is that the
decision history lives on disk and survives any session, so a gate loop that destroys its own
record on every iteration falsifies the claim it exists to support. The verdicts are also the
only place the *reasoning* survives: which findings were rejected and why, what a judge
accepted against its own instinct, which promise was made about the next round. A defect list
without that is worth very little.

Run this before writing a new critique or verdict. It is idempotent and refuses to clobber.

Usage:
    archive-round.py [docs_dir] [slug]      # defaults: docs, 00-brief
"""

import filecmp
import re
import shutil
import sys
from pathlib import Path

ROUND_RE = re.compile(r"\*\*Revision round:\*\*\s*(\d+)", re.I)


def round_of(verdict: Path):
    if not verdict.is_file():
        return None
    m = ROUND_RE.search(verdict.read_text(errors="replace"))
    return int(m.group(1)) if m else None


def next_index(history: Path) -> int:
    used = []
    for p in history.glob("r*-*.md"):
        m = re.match(r"r(\d+)-", p.name)
        if m:
            used.append(int(m.group(1)))
    return (max(used) + 1) if used else 1


def main(argv):
    docs = Path(argv[0] if argv else "docs")
    slug = argv[1] if len(argv) > 1 else "00-brief"

    if not docs.is_dir():
        print(f"error: {docs} is not a directory", file=sys.stderr)
        return 2

    critique = docs / f"{slug}.critique.md"
    verdict = docs / f"{slug}.verdict.md"

    if not critique.is_file() and not verdict.is_file():
        print(f"nothing to archive for {slug} — no critique or verdict on disk")
        return 0

    history = docs / "history" / slug
    history.mkdir(parents=True, exist_ok=True)

    # Prefer the round the verdict states; fall back to the next free slot so an
    # unparseable verdict still gets preserved rather than silently skipped.
    n = round_of(verdict) or next_index(history)

    moved, skipped = [], []
    for src, kind in ((critique, "critique"), (verdict, "verdict")):
        if not src.is_file():
            continue
        dest = history / f"r{n}-{kind}.md"
        if dest.exists():
            if filecmp.cmp(str(src), str(dest), shallow=False):
                # Already archived, unchanged. Re-running is a no-op, not a new round.
                skipped.append(dest)
                continue
            # Same round number, different content — the round was re-run. Take the next
            # free slot rather than overwriting, but never invent a round number for a file
            # that is merely a duplicate: an earlier version of this script did exactly that
            # and produced an "r5-verdict.md" that was byte-for-byte round 3's. A history
            # with fabricated round numbers is worse than no history, because it is the
            # artifact everything else is told to trust.
            dest = history / f"r{next_index(history)}-{kind}.md"
        # Copy, never move. Moving looks tidier and is wrong: the frontier derives state
        # from the live paths, so emptying them turns a stage awaiting a decision into a
        # stage that was never critiqued. Archiving must be invisible to the state machine.
        # (Learned by doing it — one run of this script with `move` silently reset a stage
        # sitting on a HUMAN_REQUIRED escalation back to "no critique exists".)
        shutil.copy2(str(src), str(dest))
        moved.append(dest)

    for m in moved:
        print(f"archived → {m}")
    for s_ in skipped:
        print(f"already archived, unchanged → {s_}")
    print(f"\n{len(moved)} file(s) archived; the live paths are untouched, so the frontier "
          f"still reads the current state.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
