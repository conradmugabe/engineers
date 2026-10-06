#!/usr/bin/env bun
/**
 * Integrity checks for the plugin itself.
 *
 * Every issue the swarm builds is adversarially reviewed. The machinery doing the reviewing was,
 * until this script, reviewed by nobody — which is constitution rule 7 violated one level up.
 * An interactive tool can afford untested machinery because a human notices within seconds. A
 * pipeline designed to run for days without anyone looking cannot.
 *
 * Checks:
 *   1. Every agent a worker is told to dispatch actually exists.
 *   2. Every agent file's `name:` matches its filename, and every skill's matches its directory.
 *   3. Every skill an agent is told to load exists.
 *   4. Restricted roles still have their restrictions (enforced by allowlist, not instruction).
 *   5. Load-bearing sentences are still where the rules say they are.
 *
 * A check that inspects nothing must not report clean: every rule below asserts it had a
 * non-empty input set, because a vacuous pass is indistinguishable from a real one to whoever
 * reads the exit code.
 *
 * Usage: check-template.ts [template_root]     Exit 0 clean, 1 on any failure.
 */

import { existsSync, readdirSync, readFileSync } from "node:fs";
import { basename, join, resolve } from "node:path";

const FRONTMATTER = /^---\s*\n([\s\S]*?)\n---/;
const NAME_FIELD = /^name:\s*(\S+)/m;
const TOOLS_FIELD = /^tools:\s*(.+)$/m;
// Agents a worker is instructed to dispatch, named in backticks in the worker playbook.
const DISPATCHED = /`((?:[a-z-]+:)?[a-z][a-z-]+)`\s+agent/g;
const SKILL_LOAD = /`((?:[a-z-]+:)?[a-z][a-z-]{2,})`\s*—\s*your playbook/gi;

// Roles whose restriction is the point of the role. If one of these silently gains a tool,
// the property it exists to guarantee is gone and nothing else would notice.
const FORBIDDEN_TOOLS: Record<string, readonly string[]> = {
  "blind-tester": ["Read", "Grep", "Glob", "Bash", "Write", "Edit"],
  reviewer: ["Write", "Edit"],
  hacker: ["Write", "Edit"],
};

// Rules that are irreducibly prose still need an enforcement terminus. The constitution
// requires every rule to end in a tool allowlist, a gate, a schema, or a static check — and
// for a rule whose whole content is a sentence, this is the only one of the four available.
//
// Pinning the sentence does not stop anyone changing the rule. It stops the rule changing
// *quietly*: an edit to the prose now fails this check, so revising it becomes a deliberate
// act with a second edit attached. Rule 21 has been revised three times in a single session;
// each revision should have been a decision, not a diff nobody noticed.
const PROSE_INVARIANTS: readonly (readonly [file: string, sentence: string, why: string])[] = [
  [
    "skills/work-issue/SKILL.md",
    "must contain $SWARM_REPO",
    "a run is bound to one repository; wandering is the failure with no undo",
  ],
  [
    "skills/work-issue/SKILL.md",
    "Give them nothing else",
    "reviewers are starved of context on purpose — the author's reasoning carries the author's blind spots",
  ],
  [
    "skills/work-issue/SKILL.md",
    "You do not fix your own review findings",
    "the builder defends its work; the fixer has no stake in it",
  ],
  [
    "skills/work-issue/SKILL.md",
    "the code is wrong — fix the code",
    "the stub-out anti-pattern, learned the hard way on the Bun rewrite",
  ],
  [
    "skills/work-issue/SKILL.md",
    "An empty result is not a pass",
    "a gate satisfied by the absence of work is the easiest one to pass by accident",
  ],
  [
    "docs/constitution.md",
    "with no defensible default",
    "rule 21 — blocking needs BOTH halves, not owner-held information alone",
  ],
  [
    "docs/constitution.md",
    "Classify per question, never in bulk",
    "rule 21 — a blanket classification hides the one row that blocks",
  ],
  [
    "docs/constitution.md",
    "not finished until it exists as a check",
    "rule 22 — the rule this whole script exists to satisfy",
  ],
  [
    "docs/constitution.md",
    "structurally unable to read the code",
    "rule 23 — blindness is a property of the system, not an instruction",
  ],
  [
    "docs/constitution.md",
    "may not be whoever fixes it",
    "rule 24 — red team proves it, blue team closes it, red team re-attacks",
  ],
];

const read = (p: string) => readFileSync(p, "utf8");
const frontmatter = (p: string) => FRONTMATTER.exec(read(p))?.[1] ?? "";

/** Run every check against a template root. Returns the failures; empty means clean. */
export function checkTemplate(root: string): { agents: number; skills: number; fails: string[] } {
  const agentsDir = join(root, "agents");
  const skillsDir = join(root, "skills");
  const manifest = join(root, ".claude-plugin", "plugin.json");
  if (!existsSync(agentsDir) || !existsSync(skillsDir) || !existsSync(manifest)) {
    throw new Error(`${root} does not look like a plugin root`);
  }
  const plugin = (JSON.parse(read(manifest)) as { name: string }).name;

  /** Inside a plugin, its agents and skills are only reachable as `plugin:name`. A bare name
   * reads fine in prose and resolves to nothing at runtime. */
  const unprefixed = (ref: string): string | null => {
    const colon = ref.indexOf(":");
    return colon > 0 && ref.slice(0, colon) === plugin ? ref.slice(colon + 1) : null;
  };

  const agents = new Map(
    readdirSync(agentsDir)
      .filter((f) => f.endsWith(".md"))
      .map((f) => [basename(f, ".md"), join(agentsDir, f)] as const),
  );
  const skills = new Map(
    readdirSync(skillsDir, { withFileTypes: true })
      .filter((d) => d.isDirectory() && existsSync(join(skillsDir, d.name, "SKILL.md")))
      .map((d) => [d.name, join(skillsDir, d.name, "SKILL.md")] as const),
  );
  const fails: string[] = [];

  // 1. Agents a worker is told to dispatch must exist.
  const worker = skills.get("work-issue");
  if (worker) {
    const dispatched = new Set([...read(worker).matchAll(DISPATCHED)].flatMap((m) => m[1] ?? []));
    if (dispatched.size === 0) {
      fails.push(
        "work-issue names no agent to dispatch — either the playbook lost its review step, " +
          "or this check stopped matching it and is now passing vacuously",
      );
    }
    for (const ref of [...dispatched].sort()) {
      const name = unprefixed(ref);
      if (name === null) {
        fails.push(
          `work-issue dispatches \`${ref}\` — inside the plugin it must be \`${plugin}:<agent>\`, ` +
            "or the worker will fail mid-issue",
        );
      } else if (!agents.has(name)) {
        fails.push(
          `work-issue dispatches the \`${ref}\` agent, but agents/${name}.md does not exist ` +
            "— the worker will fail mid-issue",
        );
      }
    }
  } else {
    fails.push("skills/work-issue/SKILL.md is missing — the swarm has no worker playbook");
  }

  // 2. Declared names must match locations.
  for (const [stem, path] of [...agents].sort()) {
    const name = NAME_FIELD.exec(frontmatter(path))?.[1];
    if (!name) fails.push(`agents/${stem}.md has no \`name:\` in its frontmatter`);
    else if (name !== stem)
      fails.push(`agents/${stem}.md declares name \`${name}\` — must match the filename`);
  }
  for (const [dir, path] of [...skills].sort()) {
    const name = NAME_FIELD.exec(frontmatter(path))?.[1];
    if (!name) fails.push(`skills/${dir}/SKILL.md has no \`name:\` in its frontmatter`);
    else if (name !== dir)
      fails.push(`skills/${dir}/SKILL.md declares name \`${name}\` — must match the directory`);
  }

  // 3. A playbook an agent is told to load first must exist.
  for (const [stem, path] of [...agents].sort()) {
    for (const ref of new Set([...read(path).matchAll(SKILL_LOAD)].flatMap((m) => m[1] ?? []))) {
      const skill = unprefixed(ref);
      if (skill === null) {
        fails.push(
          `agents/${stem}.md loads \`${ref}\` as its playbook — inside the plugin it must be \`${plugin}:<skill>\``,
        );
      } else if (!skills.has(skill)) {
        fails.push(
          `agents/${stem}.md loads \`${ref}\` as its playbook, but skills/${skill}/SKILL.md does not exist`,
        );
      }
    }
  }

  // 4. Restricted roles are still restricted.
  for (const [stem, forbidden] of Object.entries(FORBIDDEN_TOOLS)) {
    const path = agents.get(stem);
    if (!path) {
      fails.push(
        `agents/${stem}.md is missing, but this check still expects to constrain it — ` +
          "either restore the role or drop it from FORBIDDEN_TOOLS deliberately",
      );
      continue;
    }
    const tools = TOOLS_FIELD.exec(frontmatter(path))?.[1];
    if (!tools) {
      fails.push(
        `agents/${stem}.md declares no \`tools:\` line — it inherits every tool, and its ` +
          "restriction is the whole point of the role",
      );
      continue;
    }
    const granted = new Set(tools.split(",").map((t) => t.trim()));
    for (const bad of forbidden) {
      if (granted.has(bad))
        fails.push(`agents/${stem}.md grants \`${bad}\`, which this role must never have`);
    }
  }

  // 5. Load-bearing sentences are still where the rules say they are.
  for (const [rel, sentence, why] of PROSE_INVARIANTS) {
    const target = join(root, rel);
    if (!existsSync(target)) {
      fails.push(`${rel} is missing — it should carry: "${sentence}"`);
    } else if (!read(target).includes(sentence)) {
      fails.push(
        `${rel} no longer contains "${sentence}" — ${why}. If the rule genuinely changed, ` +
          "change this check in the same commit.",
      );
    }
  }

  return { agents: agents.size, skills: skills.size, fails };
}

function main(argv: string[]): number {
  const root = resolve(argv[0] ?? ".");
  let result: ReturnType<typeof checkTemplate>;
  try {
    result = checkTemplate(root);
  } catch (e) {
    console.error(`error: ${(e as Error).message}`);
    return 2;
  }
  console.log(`Template integrity — ${root}\n`);
  console.log(`  ${result.agents} agents, ${result.skills} skills\n`);
  for (const f of result.fails) console.log(`  FAIL  ${f}`);
  if (result.fails.length === 0) console.log("  clean");
  console.log(`\n${result.fails.length} failure(s).`);
  return result.fails.length ? 1 : 0;
}

if (import.meta.main) process.exit(main(process.argv.slice(2)));
