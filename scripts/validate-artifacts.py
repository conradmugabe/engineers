#!/usr/bin/env python3
"""Validate pipeline artifacts against their schemas.

Runtime-agnostic: any runtime (a Claude Code skill today, a control plane later) shells
out to this and reads the exit code. That is what makes a gate a gate rather than a
suggestion.

Artifacts are JSON files whose `id` field carries a prefix that selects the schema:

    REQ-*          requirement.schema.json
    FEAT-*         feature.schema.json
    ADR-*          architecture-decision.schema.json
    TASK-DESIGN-*  implementation-design.schema.json
    TEST-*         test.schema.json
    HACT-*         human-action.schema.json

Usage:
    validate-artifacts.py <path> [<path> ...]   # files or directories (recursed)
    validate-artifacts.py --schemas <dir> <path>

Exit codes: 0 all valid, 1 validation failures, 2 usage or setup error.
"""

import json
import sys
from pathlib import Path

PREFIX_TO_SCHEMA = [
    ("TASK-DESIGN-", "implementation-design.schema.json"),
    ("REQ-", "requirement.schema.json"),
    ("FEAT-", "feature.schema.json"),
    ("ADR-", "architecture-decision.schema.json"),
    ("TEST-", "test.schema.json"),
    ("HACT-", "human-action.schema.json"),
]


def find_schema_dir(explicit):
    if explicit:
        return Path(explicit)
    here = Path(__file__).resolve().parent
    for candidate in (here.parent / "schemas", Path.cwd() / "schemas"):
        if candidate.is_dir():
            return candidate
    return None


def schema_for(artifact_id):
    for prefix, filename in PREFIX_TO_SCHEMA:
        if artifact_id.startswith(prefix):
            return filename
    return None


def collect(paths):
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            yield from sorted(p.rglob("*.json"))
        elif p.is_file():
            yield p
        else:
            print(f"error: no such path: {p}", file=sys.stderr)
            sys.exit(2)


def main(argv):
    args = list(argv)
    allow_empty = "--allow-empty" in args
    args = [a for a in args if a != "--allow-empty"]
    schema_dir_arg = None
    if "--schemas" in args:
        i = args.index("--schemas")
        try:
            schema_dir_arg = args[i + 1]
        except IndexError:
            print("error: --schemas needs a directory", file=sys.stderr)
            return 2
        del args[i : i + 2]

    if not args:
        print(__doc__.strip(), file=sys.stderr)
        return 2

    schema_dir = find_schema_dir(schema_dir_arg)
    if not schema_dir or not schema_dir.is_dir():
        print("error: could not locate a schemas/ directory; pass --schemas", file=sys.stderr)
        return 2

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print("error: pip install jsonschema", file=sys.stderr)
        return 2

    validators = {}
    for _, filename in PREFIX_TO_SCHEMA:
        path = schema_dir / filename
        if not path.is_file():
            continue
        schema = json.loads(path.read_text())
        Draft202012Validator.check_schema(schema)
        validators[filename] = Draft202012Validator(schema)

    checked = 0
    failures = 0
    skipped = []

    for path in collect(args):
        try:
            doc = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            print(f"FAIL {path}: not valid JSON — {exc}")
            failures += 1
            continue

        if not isinstance(doc, dict) or "id" not in doc:
            skipped.append((path, "no `id` field — not a pipeline artifact"))
            continue

        filename = schema_for(doc["id"])
        if filename is None:
            skipped.append((path, f"unrecognised id prefix: {doc['id']}"))
            continue
        if filename not in validators:
            skipped.append((path, f"schema not found: {filename}"))
            continue

        checked += 1
        errors = sorted(validators[filename].iter_errors(doc), key=lambda e: list(e.path))
        if errors:
            failures += 1
            print(f"FAIL {path}  ({doc['id']} against {filename})")
            for err in errors:
                location = ".".join(str(p) for p in err.path) or "(root)"
                print(f"       {location}: {err.message}")
        else:
            print(f"ok   {path}  ({doc['id']})")

    for path, reason in skipped:
        print(f"skip {path}: {reason}")

    print(f"\n{checked} artifact(s) checked, {failures} failed, {len(skipped)} skipped.")

    # A check that ran over nothing must not report green. "0 checked, 0 failed, exit 0" is
    # indistinguishable from "everything passed" to a gate that only reads the exit code —
    # and a gate satisfied by the absence of work is the easiest gate in the system to pass
    # by accident. Pass --allow-empty only where finding nothing is genuinely the expectation.
    if failures:
        return 1
    if checked == 0 and not allow_empty:
        print("error: no artifacts were validated — a check that ran over nothing is not a "
              "pass. Point it at artifacts, or pass --allow-empty if that is expected.",
              file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
