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

Round 4 added checks 6 and 7, for the two defects that survived a critic and a judge and
were caught by hand:

  6. Every "Later phases" entry names a bucket row. A deferred capability is still a
     capability; deferring it is a schedule, not an exemption from the sort. This is the
     one that would have caught locale-aware date formatting three rounds earlier.
  7. The persona table declares what each row is conditional on. The judge called this
     inference "semantic" and left it with the critic — it is only semantic while the table
     has nowhere to record the answer. Requiring the column makes it mechanical.

Both were verified by reintroducing the original defect and confirming the check fires.
That test found a bug in check 7 that reading it had not: the escape-hatch regex matched
"Unconditional", swallowing the exact case the check exists to catch. **Write the check,
then break the document on purpose to see it fire.**

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

# Sections that state scope outside the three bucket tables. Each is a place a demotion has
# to be propagated to, and each has gone stale at least once on this project.
LATER_HEADING = re.compile(r"^#{2,3}\s+Later phases\b", re.I)
HEADING = re.compile(r"^#{1,6}\s")
# Bold is markdown style, not the property. Requiring it meant an unbolded entry
# evaded the check entirely — it tested formatting and reported on scope.
# Boundary on em/en dash only. An ASCII hyphen also lives inside names like
# "Multi-device sync", and matching it truncated the name and lost the trailing id.
LATER_ITEM = re.compile(r"^[-*]\s+\*{0,2}(?P<name>[^*\n]{3,}?)\*{0,2}\s*(?:[—–]|$)")

# The persona table is the trust-boundary contract four downstream stages consume. A row
# describing a persona that only exists if a nice-to-have is built will cause that
# capability to be built — silently re-promoting it through a door stage 4 does not watch.
PERSONA_HEADER = re.compile(r"^\|.*\bpersona\b.*\|.*must not reach.*\|", re.I)
CONDITIONAL_COL = re.compile(r"conditional", re.I)

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
    all_rows = []
    reqs = {}
    later = []
    personas = {"found": False, "has_conditional_col": False, "col": None, "rows": []}
    in_table = False
    in_later = False
    persona_cols = None

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        in_table = stripped.startswith("|")

        # --- Later phases: every entry must name the bucket row it corresponds to -------
        if LATER_HEADING.match(stripped):
            in_later = True
            continue
        if in_later and HEADING.match(stripped):
            in_later = False
        if in_later:
            m_later = LATER_ITEM.match(stripped)
            if m_later:
                later.append((i, m_later.group("name").strip(),
                              ID_REF.findall(stripped)))

        # --- Persona table: locate it, and whether it declares conditionality -----------
        if PERSONA_HEADER.match(stripped):
            personas["found"] = True
            persona_cols = [c.strip() for c in stripped.strip("|").split("|")]
            for idx, col in enumerate(persona_cols):
                if CONDITIONAL_COL.search(col):
                    personas["has_conditional_col"] = True
                    personas["col"] = idx
            continue
        if persona_cols is not None:
            if not stripped.startswith("|"):
                persona_cols = None
            elif not stripped.startswith("|---"):
                parts = [c.strip() for c in stripped.strip("|").split("|")]
                personas["rows"].append((i, parts))

        m = BUCKET_ROW.match(stripped)
        if m:
            kind, num, body = m.group(1), m.group(2), m.group(3)
            parts = cells(body)
            cid = f"{kind}{num}"
            all_rows.append((cid, i))
            buckets[kind][cid] = {
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
    return lines, buckets, reqs, prose, later, personas, all_rows


def main(argv):
    strict = "--strict" in argv
    args = [a for a in argv if not a.startswith("--")]
    path = Path(args[0] if args else "docs/00-brief.md")
    if not path.is_file():
        print(f"error: {path} not found", file=sys.stderr)
        return 2

    lines, buckets, reqs, prose, later, personas, all_rows = parse(path)
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
    # `\s+` not a literal space: the brief wraps between "Must-have" and "is", and the
    # limb silently matched nothing for four rounds. Substituting 88% still passed.
    for claimed_pct in re.findall(r"[Mm]ust-have\s+is\s*\*{0,2}(\d+(?:\.\d+)?)\s*%", body):
        if abs(float(claimed_pct) - pct) > 0.6:
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

    # --- 6. every Later-phases entry maps to a bucket row -----------------------------
    #
    # Added round 4. "Locale-aware date formatting" sat in Later phases and in no bucket for
    # three rounds while the closure sentence claimed every capability was placed — found by
    # a critic reading carefully, which is exactly the work a check should be doing. A
    # deferred capability is still a capability; deferring it is a schedule, not an exemption
    # from the sort.
    all_ids = {cid for kind in buckets for cid in buckets[kind]}
    for line_no, name, refs in later:
        if not refs:
            flags.append(
                f"line {line_no}: Later-phases entry \"{name[:48]}\" names no bucket id — "
                f"a deferred capability still belongs in a bucket; write \"— N16\""
            )
            continue
        for ref in refs:
            if ref.startswith("R-"):
                continue
            if ref not in all_ids:
                fails.append(
                    f"line {line_no}: Later-phases entry \"{name[:48]}\" names {ref}, "
                    f"which is not in any bucket table"
                )

    # --- 7. the persona contract declares what it is conditional on -------------------
    #
    # Added round 4, and the reason is worth stating. The judge found three persona rows
    # whose existence depended on unscheduled nice-to-haves with nothing saying so, and
    # called the inference "semantic" — something only a careful reader could catch. It is
    # only semantic while the table has nowhere to put the answer. Requiring the column
    # turns it mechanical: downstream stages read this table as the contract, and a persona
    # they cannot produce is an instruction to build the missing capability, which silently
    # undoes a demotion.
    if personas["found"]:
        if not personas["has_conditional_col"]:
            flags.append(
                "the persona table has no \"Conditional on\" column — it states scope, so "
                "each row must say which capability it depends on, or a dormant persona "
                "reads as live work"
            )
        else:
            col = personas["col"]
            for line_no, parts in personas["rows"]:
                if col >= len(parts):
                    continue
                cond, rest = parts[col], " ".join(p for i, p in enumerate(parts) if i != col)
                if not cond:
                    flags.append(f"line {line_no}: persona row has an empty \"Conditional on\" cell")
                    continue
                for ref in ID_REF.findall(cond):
                    if not ref.startswith("R-") and ref not in all_ids:
                        fails.append(
                            f"line {line_no}: persona row is conditional on {ref}, "
                            f"which is not in any bucket table"
                        )
                # A row leaning on a nice/polish capability must be visibly conditional on it.
                leaned = {r for r in ID_REF.findall(rest) if r.startswith(("N", "L"))}
                declared = set(ID_REF.findall(cond))
                undeclared = leaned - declared
                # "Unconditional" contains "conditional" — an escape hatch that matched it
                # would let the one cell this check exists to catch through. Found by
                # testing the check against a reintroduced defect rather than by reading it.
                hedged = re.sub(r"unconditional", "", cond, flags=re.I)
                if undeclared and not re.search(r"dormant|unscheduled|conditional", hedged, re.I):
                    flags.append(
                        f"line {line_no}: persona row mentions {sorted(undeclared)} "
                        f"(not must-have) but its \"Conditional on\" cell does not say so"
                    )

    # --- 8. duplicate ids --------------------------------------------------------------
    seen = defaultdict(list)
    for cid, line_no in all_rows:
        seen[cid].append(line_no)
    for cid, where in sorted(seen.items()):
        if len(where) > 1:
            fails.append(
                f"duplicate id {cid} at lines {where} — the later row silently replaced the "
                f"earlier one, which also corrupts every count derived from these tables"
            )

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
