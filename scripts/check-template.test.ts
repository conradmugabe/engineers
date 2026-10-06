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
  cpSync(join(repoRoot, ".claude"), join(copy, ".claude"), { recursive: true });
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
  const p = join(root, ".claude/agents/blind-tester.md");
  writeFileSync(p, readFileSync(p, "utf8").replace("tools: Skill,", "tools: Skill, Bash,"));
  expect(checkTemplate(root).fails).toContain(
    "agents/blind-tester.md grants `Bash`, which this role must never have",
  );
});

test("a reworded load-bearing sentence fails the check", () => {
  const root = copyTemplate();
  const p = join(root, ".claude/skills/work-issue/SKILL.md");
  writeFileSync(
    p,
    readFileSync(p, "utf8").replace("Give them nothing else", "Give them a little context"),
  );
  expect(checkTemplate(root).fails.some((f) => f.includes("Give them nothing else"))).toBe(true);
});
