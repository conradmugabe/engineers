#!/usr/bin/env python3
"""Compute the pipeline frontier from the filesystem.

State is derived, never remembered. This reads the artifacts on disk and reports where
the project stands and what the single next action is. Any runtime — a Claude Code skill
today, a control plane later — calls this rather than reimplementing the state machine.

Per stage, three artifacts form the generator/critic/judge loop:

    docs/<NN>-<slug>.md            the artifact itself
    docs/<NN>-<slug>.critique.md   the critic's defect list
    docs/<NN>-<slug>.verdict.md    the judge's decision

A stage advances only on a verdict of PASS. If an artifact is modified after its critique
or verdict, those become STALE and must be re-run — that is how remediation re-enters the
loop without anyone tracking it by hand.

Usage:
    frontier.py [project_dir]           human-readable
    frontier.py [project_dir] --json    machine-readable

Exit codes: 0 work remains, 1 pipeline complete, 2 blocked on a human.
"""

import hashlib
import json
import re
import sys
from pathlib import Path

STAGES = [
    (0, "INTAKE", "00-brief", "product-analyst"),
    (1, "REQUIREMENTS", "01-requirements", "product-analyst"),
    (2, "FEATURES", "02-features", "product-designer"),
    (3, "SYSTEM", "03-system", "systems-architect"),
    (4, "SCOPE", "04-roadmap", "product-designer"),
    (5, "DESIGN", "05-design", "ux-designer"),
    (6, "BUILD", "06-build", "tech-lead"),
    (7, "VERIFY", "07-verify", "qa-engineer"),
    (8, "RELEASE", "08-release", "security-engineer"),
]

DECISION_RE = re.compile(r"\*\*Decision:\*\*\s*(PASS|REVISE|HUMAN_REQUIRED)", re.I)
ROUND_RE = re.compile(r"\*\*Revision round:\*\*\s*(\d+)\s*of\s*(\d+)", re.I)


DIGEST_RE = re.compile(r"\*\*Artifact-SHA256:\*\*\s*`?([0-9a-f]{64})`?", re.I)


def artifact_digest(path: Path) -> str:
    """Content hash of a stage artifact — a file, or every file under a directory.

    Staleness used to be decided by mtime, which is wrong in a way that only shows up when
    it matters most. `git clone` writes files in alphabetical order, so `00-brief.critique.md`
    lands microseconds *before* `00-brief.md`, and every passed stage in a freshly cloned
    project reports its critique as stale. `touch`, `git checkout -- <file>`, and any restore
    from backup do the same. A pipeline whose whole claim is that a new machine can pick up a
    half-finished project could not survive being moved to one.

    Content hashes have none of that. The question being asked is "has this artifact changed
    since it was reviewed", and that is a question about content.
    """
    h = hashlib.sha256()
    if path.is_file():
        h.update(path.read_bytes())
    elif path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file():
                h.update(str(p.relative_to(path)).encode())
                h.update(p.read_bytes())
    return h.hexdigest()


def recorded_digest(path: Path):
    """The artifact hash a critique or verdict recorded for what it reviewed."""
    if not path.is_file():
        return None
    m = DIGEST_RE.search(path.read_text(errors="replace"))
    return m.group(1).lower() if m else None


def newest_mtime(path: Path) -> float:
    """Fallback only, for artifacts written before hashes were recorded."""
    if path.is_file():
        return path.stat().st_mtime
    if path.is_dir():
        times = [p.stat().st_mtime for p in path.rglob("*") if p.is_file()]
        return max(times) if times else path.stat().st_mtime
    return 0.0


def is_stale(reviewed_by: Path, artifact: Path, digest: str, warnings: list) -> bool:
    """Has `artifact` changed since `reviewed_by` reviewed it?"""
    recorded = recorded_digest(reviewed_by)
    if recorded is not None:
        return recorded != digest
    warnings.append(
        f"{reviewed_by.name} records no Artifact-SHA256 — falling back to timestamps, "
        f"which are unreliable across clones and restores"
    )
    return reviewed_by.stat().st_mtime < newest_mtime(artifact)


def resolve_artifact(docs: Path, slug: str):
    """A stage artifact is either docs/<slug>.md or the directory docs/<slug>/."""
    as_file = docs / f"{slug}.md"
    if as_file.is_file():
        return as_file
    as_dir = docs / slug
    if as_dir.is_dir() and any(as_dir.iterdir()):
        return as_dir
    return None


def read_verdict(path: Path):
    if not path.is_file():
        return None
    text = path.read_text(errors="replace")
    decision = DECISION_RE.search(text)
    rounds = ROUND_RE.search(text)
    return {
        "decision": decision.group(1).upper() if decision else "UNPARSEABLE",
        "round": int(rounds.group(1)) if rounds else None,
        "budget": int(rounds.group(2)) if rounds else None,
    }


def examine(project: Path):
    docs = project / "docs"
    stages = []
    next_action = None
    warnings = []

    for number, name, slug, owner in STAGES:
        artifact = resolve_artifact(docs, slug)
        critique = docs / f"{slug}.critique.md"
        verdict_path = docs / f"{slug}.verdict.md"

        entry = {
            "stage": number,
            "name": name,
            "slug": slug,
            "owner": owner,
            "artifact": str(artifact.relative_to(project)) if artifact else None,
            "state": "NOT_STARTED",
            "verdict": None,
            "round": None,
            "budget": None,
        }

        if artifact is None:
            stages.append(entry)
            if next_action is None:
                # Stage 0 is the only stage whose upstream is a human. The raw idea or
                # client notes live in a file so the pipeline can be started by a timer
                # rather than by someone typing into a session.
                if number == 0 and not (docs / "00-idea.md").is_file():
                    next_action = {
                        "action": "AWAIT_INPUT",
                        "stage": 0,
                        "name": name,
                        "agent": None,
                        "why": "no raw input yet — start with /new-idea \"<the idea>\" or /new-idea @notes.md",
                        "writes": None,
                    }
                else:
                    next_action = {
                        "action": "GENERATE",
                        "stage": number,
                        "name": name,
                        "agent": owner,
                        "why": f"no stage {number} artifact exists",
                        "writes": f"docs/{slug}.md",
                    }
            continue

        digest = artifact_digest(artifact)
        entry["digest"] = digest[:12]

        if not critique.is_file() or is_stale(critique, artifact, digest, warnings):
            entry["state"] = "AWAITING_CRITIQUE" if not critique.is_file() else "CRITIQUE_STALE"
            stages.append(entry)
            if next_action is None:
                next_action = {
                    "action": "CRITIQUE",
                    "stage": number,
                    "name": name,
                    "agent": "critic",
                    "why": (
                        "no critique exists" if not critique.is_file()
                        else "the artifact changed after its critique"
                    ),
                    "writes": f"docs/{slug}.critique.md",
                }
            continue

        if not verdict_path.is_file() or is_stale(verdict_path, artifact, digest, warnings):
            entry["state"] = "AWAITING_VERDICT" if not verdict_path.is_file() else "VERDICT_STALE"
            stages.append(entry)
            if next_action is None:
                next_action = {
                    "action": "JUDGE",
                    "stage": number,
                    "name": name,
                    "agent": "judge",
                    "why": (
                        "no verdict exists" if not verdict_path.is_file()
                        else "the critique changed after the verdict"
                    ),
                    "writes": f"docs/{slug}.verdict.md",
                }
            continue

        verdict = read_verdict(verdict_path)
        entry["verdict"] = verdict["decision"]
        entry["round"] = verdict["round"]
        entry["budget"] = verdict["budget"]

        if verdict["decision"] == "PASS":
            entry["state"] = "PASSED"
            stages.append(entry)
            continue

        if verdict["decision"] == "HUMAN_REQUIRED":
            entry["state"] = "BLOCKED_ON_HUMAN"
            stages.append(entry)
            if next_action is None:
                next_action = {
                    "action": "ESCALATE",
                    "stage": number,
                    "name": name,
                    "agent": None,
                    "why": "the judge escalated; only the owner can unblock this",
                    "writes": None,
                }
            continue

        # A verdict that cannot be read is not a licence to keep going. Treating an
        # unreadable decision as REVISE meant a malformed verdict produced REMEDIATE on
        # every tick, forever — and on a timer, with nobody watching, that is an unbounded
        # spend with no escalation path. The same hole swallowed a REVISE whose round line
        # was missing or rephrased: no round means never exhausted means never escalated.
        # Anything the machine cannot read is a stop, not a continue.
        if verdict["decision"] == "UNPARSEABLE":
            entry["state"] = "BLOCKED_ON_HUMAN"
            stages.append(entry)
            if next_action is None:
                next_action = {
                    "action": "ESCALATE",
                    "stage": number,
                    "name": name,
                    "agent": None,
                    "why": f"{verdict_path.name} states no readable decision — it must contain "
                           f"**Decision:** PASS | REVISE | HUMAN_REQUIRED",
                    "writes": None,
                }
            continue

        if verdict["round"] is None or verdict["budget"] is None:
            entry["state"] = "BLOCKED_ON_HUMAN"
            stages.append(entry)
            if next_action is None:
                next_action = {
                    "action": "ESCALATE",
                    "stage": number,
                    "name": name,
                    "agent": None,
                    "why": f"{verdict_path.name} returns REVISE without stating its revision "
                           f"round — the retry budget cannot be enforced, so remediation would "
                           f"loop without limit",
                    "writes": None,
                }
            continue

        entry["state"] = "REVISING"
        stages.append(entry)
        if next_action is None:
            exhausted = verdict["round"] >= verdict["budget"]
            next_action = {
                "action": "ESCALATE" if exhausted else "REMEDIATE",
                "stage": number,
                "name": name,
                "agent": None if exhausted else owner,
                "why": (
                    f"retry budget exhausted at round {verdict['round']} of {verdict['budget']}"
                    if exhausted
                    else f"the judge returned REVISE (round {verdict['round']} of {verdict['budget']})"
                ),
                "writes": None if exhausted else f"docs/{slug}.md",
            }

    if next_action is None:
        next_action = {"action": "COMPLETE", "stage": None, "name": None,
                       "agent": None, "why": "every stage has passed", "writes": None}

    return {"project": str(project), "stages": stages, "next": next_action,
            "warnings": sorted(set(warnings))}


def main(argv):
    args = [a for a in argv if a != "--json"]
    as_json = "--json" in argv
    project = Path(args[0] if args else ".").resolve()

    if not (project / "docs").is_dir():
        print(f"error: {project}/docs does not exist — is this a pipeline project?",
              file=sys.stderr)
        return 2

    result = examine(project)

    if as_json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Pipeline frontier — {project}\n")
        symbols = {
            "PASSED": "[x]", "NOT_STARTED": "[ ]", "REVISING": "[!]",
            "BLOCKED_ON_HUMAN": "[H]", "AWAITING_CRITIQUE": "[>]",
            "AWAITING_VERDICT": "[>]", "CRITIQUE_STALE": "[~]", "VERDICT_STALE": "[~]",
        }
        for s in result["stages"]:
            detail = s["state"].replace("_", " ").lower()
            if s["verdict"] and s["state"] == "REVISING":
                detail += f" — round {s['round']} of {s['budget']}"
            print(f"  {symbols.get(s['state'], '[?]')} {s['stage']}  {s['name']:<14} {detail}")

        for w in result["warnings"]:
            print(f"\n  warning: {w}")

        nxt = result["next"]
        print(f"\nNext: {nxt['action']}", end="")
        if nxt["name"]:
            print(f" — stage {nxt['stage']} {nxt['name']}", end="")
        if nxt["agent"]:
            print(f", dispatch `{nxt['agent']}`", end="")
        print(f"\nWhy:  {nxt['why']}")
        if nxt["writes"]:
            print(f"Writes: {nxt['writes']}")

    action = result["next"]["action"]
    if action == "COMPLETE":
        return 1
    if action in ("ESCALATE", "AWAIT_INPUT"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
