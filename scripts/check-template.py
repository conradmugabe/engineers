#!/usr/bin/env python3
"""Integrity checks for the template itself.

Every artifact this pipeline produces is adversarially reviewed by a critic and a judge.
The machinery doing the reviewing was, until this script, reviewed by nobody — which is
constitution rule 7 violated one level up. An interactive tool can afford untested
machinery because a human notices within seconds. A pipeline designed to run for days
without anyone looking cannot.

Checks:
  1. Every agent a worker is told to dispatch actually exists.
  2. Every agent file's `name:` matches its filename, and every skill's matches its directory.
  3. Every skill an agent is told to load exists.
  4. Restricted roles still have their restrictions (enforced by allowlist, not instruction).
  5. Load-bearing sentences are still where the rules say they are.

A check that inspects nothing must not report clean: every rule below asserts it had a
non-empty input set, because a vacuous pass is indistinguishable from a real one to whoever
reads the exit code.

Usage: check-template.py [template_root]     Exit 0 clean, 1 on any failure.
"""

import re
import sys
from pathlib import Path

FRONTMATTER = re.compile(r"^---\s*\n(.*?)\n---", re.S)
NAME_FIELD = re.compile(r"^name:\s*(\S+)", re.M)
TOOLS_FIELD = re.compile(r"^tools:\s*(.+)$", re.M)
# Agents a worker is instructed to dispatch, named in backticks in the worker playbook.
DISPATCHED = re.compile(r"`([a-z][a-z-]+)`\s+agent")
SKILL_LOAD = re.compile(r"`([a-z][a-z-]{2,})`\s*—\s*your playbook", re.I)

# Roles whose restriction is the point of the role. If one of these silently gains a tool,
# the property it exists to guarantee is gone and nothing else would notice.
FORBIDDEN_TOOLS = {
    "blind-tester": ["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
    "reviewer": ["Write", "Edit"],
    "hacker": ["Write", "Edit"],
}


# Rules that are irreducibly prose still need an enforcement terminus. The constitution
# requires every rule to end in a tool allowlist, a gate, a schema, or a static check — and
# for a rule whose whole content is a sentence, this is the only one of the four available.
#
# Pinning the sentence does not stop anyone changing the rule. It stops the rule changing
# *quietly*: an edit to the prose now fails this check, so revising it becomes a deliberate
# act with a second edit attached. Rule 21 has been revised three times in a single session;
# each revision should have been a decision, not a diff nobody noticed.
PROSE_INVARIANTS = [
    (".claude/skills/work-issue/SKILL.md", "must contain $SWARM_REPO",
     "a run is bound to one repository; wandering is the failure with no undo"),
    (".claude/skills/work-issue/SKILL.md", "Give them nothing else",
     "reviewers are starved of context on purpose — the author's reasoning carries the author's blind spots"),
    (".claude/skills/work-issue/SKILL.md", "You do not fix your own review findings",
     "the builder defends its work; the fixer has no stake in it"),
    (".claude/skills/work-issue/SKILL.md", "the code is wrong — fix the code",
     "the stub-out anti-pattern, learned the hard way on the Bun rewrite"),
    (".claude/skills/work-issue/SKILL.md", "An empty result is not a pass",
     "a gate satisfied by the absence of work is the easiest one to pass by accident"),
    ("docs/constitution.md", "with no defensible default",
     "rule 21 — blocking needs BOTH halves, not owner-held information alone"),
    ("docs/constitution.md", "Classify per question, never in bulk",
     "rule 21 — a blanket classification hides the one row that blocks"),
    ("docs/constitution.md", "not finished until it exists as a check",
     "rule 22 — the rule this whole script exists to satisfy"),
    ("docs/constitution.md", "structurally unable to read the code",
     "rule 23 — blindness is a property of the system, not an instruction"),
    ("docs/constitution.md", "may not be whoever fixes it",
     "rule 24 — red team proves it, blue team closes it, red team re-attacks"),
]


def frontmatter(path):
    m = FRONTMATTER.match(path.read_text(errors="replace"))
    return m.group(1) if m else ""


def main(argv):
    root = Path(argv[0] if argv else ".").resolve()
    agents_dir = root / ".claude" / "agents"
    skills_dir = root / ".claude" / "skills"
    fails, notes = [], []

    if not agents_dir.is_dir() or not skills_dir.is_dir():
        print(f"error: {root} does not look like a template root", file=sys.stderr)
        return 2

    agents = {p.stem: p for p in agents_dir.glob("*.md")}
    skills = {p.name: p / "SKILL.md" for p in skills_dir.iterdir()
              if p.is_dir() and (p / "SKILL.md").is_file()}

    # 1. Agents a worker is told to dispatch must exist.
    worker = skills.get("work-issue")
    if worker and worker.is_file():
        dispatched = set(DISPATCHED.findall(worker.read_text(errors="replace")))
        if not dispatched:
            fails.append(
                "work-issue names no agent to dispatch — either the playbook lost its "
                "review step, or this check stopped matching it and is now passing vacuously"
            )
        for name in sorted(dispatched):
            if name not in agents:
                fails.append(
                    f"work-issue dispatches the `{name}` agent, but "
                    f".claude/agents/{name}.md does not exist — the worker will fail mid-issue"
                )
    else:
        fails.append("skills/work-issue/SKILL.md is missing — the swarm has no worker playbook")

    # 2. Declared names must match locations.
    for stem, path in sorted(agents.items()):
        m = NAME_FIELD.search(frontmatter(path))
        if not m:
            fails.append(f"agents/{stem}.md has no `name:` in its frontmatter")
        elif m.group(1) != stem:
            fails.append(f"agents/{stem}.md declares name `{m.group(1)}` — must match the filename")

    for dirname, path in sorted(skills.items()):
        m = NAME_FIELD.search(frontmatter(path))
        if not m:
            fails.append(f"skills/{dirname}/SKILL.md has no `name:` in its frontmatter")
        elif m.group(1) != dirname:
            fails.append(
                f"skills/{dirname}/SKILL.md declares name `{m.group(1)}` — must match the directory"
            )

    # 3. A playbook an agent is told to load first must exist.
    for stem, path in sorted(agents.items()):
        for skill in set(SKILL_LOAD.findall(path.read_text(errors="replace"))):
            if skill not in skills:
                fails.append(
                    f"agents/{stem}.md loads `{skill}` as its playbook, but "
                    f"skills/{skill}/SKILL.md does not exist"
                )

    # 5. Restricted roles are still restricted.
    for stem, forbidden in FORBIDDEN_TOOLS.items():
        if stem not in agents:
            fails.append(
                f"agents/{stem}.md is missing, but this check still expects to constrain it — "
                f"either restore the role or drop it from FORBIDDEN_TOOLS deliberately"
            )
            continue
        m = TOOLS_FIELD.search(frontmatter(agents[stem]))
        if not m:
            fails.append(
                f"agents/{stem}.md declares no `tools:` line — it inherits every tool, and its "
                f"restriction is the whole point of the role"
            )
            continue
        granted = {t.strip() for t in m.group(1).split(",")}
        for bad in forbidden:
            if bad in granted:
                fails.append(f"agents/{stem}.md grants `{bad}`, which this role must never have")

    # 6. Load-bearing sentences are still where the rules say they are.
    for rel, sentence, why in PROSE_INVARIANTS:
        target = root / rel
        if not target.is_file():
            fails.append(f"{rel} is missing — it should carry: \"{sentence}\"")
            continue
        if sentence not in target.read_text(errors="replace"):
            fails.append(
                f"{rel} no longer contains \"{sentence}\" — {why}. If the rule genuinely "
                f"changed, change this check in the same commit."
            )

    print(f"Template integrity — {root}\n")
    print(f"  {len(agents)} agents, {len(skills)} skills\n")
    for f in fails:
        print(f"  FAIL  {f}")
    for n in notes:
        print(f"  note  {n}")
    if not fails:
        print("  clean")
    print(f"\n{len(fails)} failure(s).")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
