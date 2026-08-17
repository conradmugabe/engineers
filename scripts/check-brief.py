#!/usr/bin/env python3
"""Consistency checks for a stage 0 brief.

Constitution rule 22: a correction is not finished until it exists as a check. This is that
check for the failure class that survived three remediation rounds on the first real run —
**scope stated in one place and not propagated to the others**, with the closure claim
re-asserted absolutely each round while a capability sat outside it.

Instance-level critique cannot close a class like that. Each round retires the named
instances and the next round produces new ones, sometimes manufactured by the remedy itself.
A check that runs over the whole document every time closes it.

Two kinds of output, and the distinction matters:

  FAIL  — a hard, mechanical contradiction. Exit code 1. These are facts, not opinions.
  FLAG  — a heuristic that needs a reader. Never fails the build on its own, because a
          false positive that blocks a gate teaches everyone to skip the gate.

Usage:
    check-brief.py [path/to/00-brief.md]
    check-brief.py --strict path   # FLAGs also fail; use in a gate that has a human behind it
"""

import re
import sys
from collections import defaultdict
from pathlib import Path

BUCKET_ROW = re.compile(r"^\|\s*(M|N|L)(\d+)\s*\|(.*)$")
REQ_ROW = re.compile(r"^\|\s*\*{0,2}(R-\d+)\*{0,2}\s*\|(.*)$")
ID_REF = re.compile(r"\b([MNL]\d+|R-\d+)\b")

# Prose that *schedules a capability*, outside a table, where it goes stale unnoticed.
#
# Deliberately narrow. An earlier version matched bare "is now" and produced nineteen false
# positives against two real ones — ordinary narrative ("that framing is now abandoned")
# reads identically to a scheduling claim. A flag that noisy trains its readers to skip it,
# which is worse than having no check at all. These four phrases only assert scheduling.
SCHEDULING_PROSE = re.compile(
    r"(?<!\w)(not later\b|which is now\b|stays? Now\b|remains? Now\b)",
)

# Words that name a capability strongly enough to cross-check a must against a nice.
STOPWORDS = set("""a an the and or of for to in on with without its it is are be been that this
those these their his her at by from as if then than so not no any all each every one two
own owner user users list lists todo todos account accounts share shares shared sharing
state states view views build built builds when where which who what how why into onto
including include includes per own only also more most less least new old same other
another such via using use used can cannot must should would could may might will shall
""".split())


def cells(row_body):
    return [c.strip() for c in row_body.split("|")]


def keywords(text):
    words = re.findall(r"[a-z][a-z-]{3,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def parse(path):
    lines = path.read_text(errors="replace").splitlines()
    buckets = {"M": {}, "N": {}, "L": {}}
    reqs = {}
    in_table = False

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        in_table = stripped.startswith("|")

        m = BUCKET_ROW.match(stripped)
        if m:
            kind, num, body = m.group(1), m.group(2), m.group(3)
            parts = cells(body)
            buckets[kind][f"{kind}{num}"] = {
                "line": i,
                "name": parts[0] if parts else "",
                "text": body,
            }
            continue

        r = REQ_ROW.match(stripped)
        if r:
            rid, body = r.group(1), r.group(2)
            parts = cells(body)
            reqs[rid] = {
                "line": i,
                "name": parts[0] if parts else "",
                "phase": parts[3] if len(parts) > 3 else "",
                "text": body,
            }
            continue

        if not in_table and SCHEDULING_PROSE.search(stripped) and len(stripped) > 40:
            reqs.setdefault("_prose", []).append((i, stripped))

    prose = reqs.pop("_prose", [])
    return lines, buckets, reqs, prose


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    path = Path(args[0] if args else "docs/00-brief.md")
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    lines, buckets, reqs, prose = parse(path)
    fails, flags = [], []

    must, nice, polish = buckets["M"], buckets["N"], buckets["L"]
    total = len(must) + len(nice) + len(polish)
    if total == 0:
        print(f"error: no bucket rows found in {path} — does it have the three-bucket sort?",
              file=sys.stderr)
        return 2

    pct = 100.0 * len(must) / total

    # --- 1. counts and percentage claimed in prose match the tables -------------------
    body = "\n".join(lines)
    for claimed in re.findall(r"(\d+)\s*must\s*[·|/]\s*(\d+)\s*nice\s*[·|/]\s*(\d+)\s*polish", body, re.I):
        cm, cn, cl = map(int, claimed)
        if (cm, cn, cl) != (len(must), len(nice), len(polish)):
            fails.append(
                f"stated counts {cm}/{cn}/{cl} do not match the tables "
                f"{len(must)}/{len(nice)}/{len(polish)}"
            )
    for claimed_pct in re.findall(r"(?:must-have is|Must-have is)\s*\*{0,2}(\d+)\s*%", body):
        if abs(int(claimed_pct) - pct) > 0.6:
            fails.append(f"stated must-have share {claimed_pct}% but tables give {pct:.1f}%")

    # --- 2. no must-have may depend on a non-must-have --------------------------------
    # (a) explicit: a must row naming a nice or polish id
    for mid, row in must.items():
        for ref in ID_REF.findall(row["text"]):
            if ref.startswith(("N", "L")):
                fails.append(
                    f"{mid} (line {row['line']}) references {ref}, which is not a must-have — "
                    f"a must-have cannot depend on something that may not be built"
                )
    # (b) heuristic: a must row whose text overlaps strongly with a nice row's name
    for mid, row in must.items():
        mkw = keywords(row["text"])
        for nid, nrow in nice.items():
            nkw = keywords(nrow["name"])
            if not nkw:
                continue
            shared = mkw & nkw
            if len(shared) >= 2:
                flags.append(
                    f"{mid} (line {row['line']}) shares {sorted(shared)} with {nid} "
                    f"\"{nrow['name'][:48]}\" — check {mid} does not contain {nid}"
                )

    # --- 3. every requirement Phase resolves, and Now only serves a must --------------
    for rid, row in reqs.items():
        phase = row["phase"]
        if not phase:
            flags.append(f"{rid} (line {row['line']}) has no Phase cell")
            continue
        refs = [r for r in ID_REF.findall(phase) if not r.startswith("R-")]
        if refs:
            for ref in refs:
                kind = ref[0]
                if ref not in buckets.get(kind, {}):
                    fails.append(f"{rid} (line {row['line']}) Phase names {ref}, which does not exist")
        elif re.search(r"\bnow\b", phase, re.I):
            # A bare "Now" cannot be checked: nothing says which capability it serves, so
            # nothing can confirm that capability is a must-have. Asking for the id turns an
            # unverifiable cell into a verifiable one — the convention exists to make the
            # check possible, not the other way round.
            flags.append(
                f"{rid} (line {row['line']}) Phase reads \"Now\" without naming the capability "
                f"it serves — write \"Now — M5\" so this can be checked mechanically"
            )

    # --- 4. scheduling asserted in prose, where it goes stale unnoticed ---------------
    for line_no, text in prose:
        flags.append(f"line {line_no}: prose schedules something — \"{text[:90]}\" — "
                     f"confirm it still matches the tables")

    # --- 5. absolute closure claims ---------------------------------------------------
    for m in re.finditer(r"every capability named anywhere[^.]*\.", body, re.I):
        line_no = body[: m.start()].count("\n") + 1
        flags.append(
            f"line {line_no}: absolute closure claim — this sentence has been false in "
            f"three consecutive rounds; verify or soften it"
        )

    # --- 6. duplicate ids --------------------------------------------------------------
    seen = defaultdict(list)
    for kind in buckets:
        for cid, row in buckets[kind].items():
            seen[cid].append(row["line"])
    for cid, where in seen.items():
        if len(where) > 1:
            fails.append(f"duplicate id {cid} at lines {where}")

    # --- report ------------------------------------------------------------------------
    print(f"Brief consistency — {path}\n")
    print(f"  {len(must)} must · {len(nice)} nice · {len(polish)} polish = {total} "
          f"({pct:.1f}% must-have)")
    print(f"  {len(reqs)} requirements\n")

    for f in fails:
        print(f"  FAIL  {f}")
    for f in flags:
        print(f"  FLAG  {f}")
    if not fails and not flags:
        print("  clean")

    print(f"\n{len(fails)} failure(s), {len(flags)} flag(s).")
    if fails:
        return 1
    if flags and strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
