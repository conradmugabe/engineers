import { afterEach, expect, test } from "bun:test";
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { checkTemplate } from "./check-template.ts";

const repoRoot = resolve(import.meta.dir, "..");
let copy: string | undefined;
afterEach(() => {
  if (copy) rmSync(copy, { recursive: true, force: true });
});

function copyTemplate(): string {
  copy = mkdtempSync(join(tmpdir(), "template-"));
  for (const dir of [".claude-plugin", "agents", "skills"]) {
    cpSync(join(repoRoot, dir), join(copy, dir), { recursive: true });
  }
  cpSync(join(repoRoot, "docs"), join(copy, "docs"), { recursive: true });
  return copy;
}

test("this template is clean", () => {
  const r = checkTemplate(repoRoot);
  expect(r.fails).toEqual([]);
  expect(r.agents).toBeGreaterThan(0);
});

test("a blind tester that gains a shell fails the check", () => {
  const root = copyTemplate();
  const p = join(root, "agents/blind-tester.md");
  writeFileSync(p, readFileSync(p, "utf8").replace("tools: Skill,", "tools: Skill, Bash,"));
  expect(checkTemplate(root).fails).toContain(
    "agents/blind-tester.md grants `Bash`, which this role must never have",
  );
});

test("a reworded load-bearing sentence fails the check", () => {
  const root = copyTemplate();
  const p = join(root, "skills/work-issue/SKILL.md");
  writeFileSync(
    p,
    readFileSync(p, "utf8").replace("Give them nothing else", "Give them a little context"),
  );
  expect(checkTemplate(root).fails.some((f) => f.includes("Give them nothing else"))).toBe(true);
});

test("an unprefixed dispatch fails the check — it would resolve to nothing in the plugin", () => {
  const root = copyTemplate();
  const p = join(root, "skills/work-issue/SKILL.md");
  writeFileSync(p, readFileSync(p, "utf8").replace("`mors:reviewer` agents", "`reviewer` agents"));
  expect(checkTemplate(root).fails.some((f) => f.includes("dispatches `reviewer`"))).toBe(true);
});

test("an unprefixed playbook load fails the check", () => {
  const root = copyTemplate();
  const p = join(root, "agents/qa-engineer.md");
  writeFileSync(
    p,
    readFileSync(p, "utf8").replace(
      "`mors:qa-engineer` — your playbook",
      "`qa-engineer` — your playbook",
    ),
  );
  expect(checkTemplate(root).fails.some((f) => f.includes("loads `qa-engineer`"))).toBe(true);
});
