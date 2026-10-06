import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as claim from "./claim.ts";
import {
  dispatch,
  keepWarm,
  mergeLanded,
  PLUGIN_ROOT,
  workerCommand,
  type DispatchCtx,
  type Sh,
  type ShResult,
} from "./swarm.ts";

const ok = (stdout = ""): ShResult => ({ code: 0, stdout, stderr: "" });

/** A fake shell: the first route whose prefix matches the command answers it. Every call is recorded. */
function fakeSh(routes: [prefix: string, result: ShResult][]): Sh & { calls: string[] } {
  const calls: string[] = [];
  const run = (args: string[]) => {
    const cmd = args.join(" ");
    calls.push(cmd);
    return routes.find(([prefix]) => cmd.includes(prefix))?.[1] ?? ok();
  };
  return Object.assign(run, { calls });
}

describe("mergeLanded", () => {
  test("a branch that was never pushed has not merged", () => {
    // The Python treated "absent on the remote" as "squash-merged and deleted". A branch that
    // was never pushed is absent too, so its worktree — the only copy of the work — was deleted.
    const run = fakeSh([
      ["branch -r --merged", ok("  origin/main\n")],
      ["gh pr list", ok("[]")],
    ]);
    expect(mergeLanded(run, "/r", "o/n", "swarm/1", "main")).toBe(false);
  });

  test("a squash-merged PR counts as merged", () => {
    const run = fakeSh([
      ["branch -r --merged", ok("  origin/main\n")],
      ["gh pr list", ok('[{"number":5}]')],
    ]);
    expect(mergeLanded(run, "/r", "o/n", "swarm/1", "main")).toBe(true);
  });

  test("an ancestor of the base branch counts as merged", () => {
    const run = fakeSh([["branch -r --merged", ok("  origin/main\n  origin/swarm/1\n")]]);
    expect(mergeLanded(run, "/r", "o/n", "swarm/1", "main")).toBe(true);
  });

  test("swarm/12 being merged does not mean swarm/1 is", () => {
    const run = fakeSh([
      ["branch -r --merged", ok("  origin/main\n  origin/swarm/12\n")],
      ["gh pr list", ok("[]")],
    ]);
    expect(mergeLanded(run, "/r", "o/n", "swarm/1", "main")).toBe(false);
  });
});

describe("dispatch", () => {
  let workdir: string;
  beforeEach(() => {
    workdir = mkdtempSync(join(tmpdir(), "swarm-"));
  });
  afterEach(() => {
    rmSync(workdir, { recursive: true, force: true });
  });

  const issues = (...ns: number[]) =>
    ok(
      JSON.stringify(
        ns.map((n) => ({ number: n, title: `issue ${n}`, labels: [{ name: "ready" }] })),
      ),
    );
  const ctx = (run: Sh): DispatchCtx => ({
    run,
    repo: "o/n",
    workdir,
    label: "ready",
    claimTtl: 900,
  });

  test("records the claim under the slot that will release it", () => {
    // The Python named slots w1.. on every pass and renamed the worker afterwards if w1 was busy.
    // The ledger said w1, the worker released as w2, the release was refused, the entry leaked.
    const [a] = dispatch(ctx(fakeSh([["gh issue list", issues(4)]])), ["w2"]);
    expect(a?.slot).toBe("w2");
    expect(claim.listClaims(workdir).map((c) => c.worker)).toEqual(["w2"]);
    expect(claim.release(workdir, "4", "w2").ok).toBe(true);
  });

  test("fills only as many slots as are free, oldest issue first", () => {
    const assigned = dispatch(ctx(fakeSh([["gh issue list", issues(9, 3, 5)]])), ["w1", "w3"]);
    expect(assigned.map((a) => [a.slot, a.issue.number])).toEqual([
      ["w1", 3],
      ["w3", 5],
    ]);
  });

  test("does not build an issue it could not label", () => {
    const run = fakeSh([
      ["gh issue list", issues(4)],
      ["gh issue edit", { code: 1, stdout: "", stderr: "HTTP 403" }],
    ]);
    expect(dispatch(ctx(run), ["w1"])).toEqual([]);
    expect(claim.listClaims(workdir)).toEqual([]);
  });

  test("skips issues already in the ledger", () => {
    claim.acquire(workdir, "3", "w1", 900);
    const assigned = dispatch(ctx(fakeSh([["gh issue list", issues(3, 4)]])), ["w2"]);
    expect(assigned.map((a) => a.issue.number)).toEqual([4]);
  });
});

describe("keepWarm", () => {
  test("beats while the process lives and stops when it exits", async () => {
    // The Python started its heartbeat thread before the process existed; the loop saw no
    // process, exited at once, and never beat.
    let beats = 0;
    const exited = Bun.sleep(60);
    keepWarm(
      exited,
      () => {
        beats += 1;
      },
      15,
    );
    await exited;
    const atExit = beats;
    expect(atExit).toBeGreaterThanOrEqual(3);
    await Bun.sleep(50);
    expect(beats).toBe(atExit);
  });
});

describe("workerCommand", () => {
  const cmd = workerCommand(42, "acceptEdits");
  const after = (flag: string) => cmd[cmd.indexOf(flag) + 1];

  test("invokes the namespaced skill and loads this plugin explicitly", () => {
    // Without --plugin-dir the worker runs inside the target repo, where /work-issue does not exist.
    expect(cmd.slice(0, 3)).toEqual(["claude", "-p", "/mors:work-issue 42"]);
    expect(after("--plugin-dir")).toBe(PLUGIN_ROOT);
  });

  test("never waits on a prompt nobody will answer", () => {
    expect(after("--permission-prompts")).toBe("none");
  });

  test("denies the git commands that destroy other work", () => {
    const deny = cmd.slice(cmd.indexOf("--disallowedTools") + 1);
    for (const c of [
      "git stash",
      "git reset",
      "git clean *",
      "git rebase *",
      "git push --force*",
    ]) {
      expect(deny.some((d) => d.startsWith(`Bash(${c}`))).toBe(true);
    }
  });
});
