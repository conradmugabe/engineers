import { afterEach, beforeEach, describe, expect, test } from "bun:test";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import * as claim from "./claim.ts";

let root: string;
beforeEach(() => {
  root = mkdtempSync(join(tmpdir(), "claim-"));
});
afterEach(() => {
  rmSync(root, { recursive: true, force: true });
});

const DEAD_PID = 2 ** 22 + 1; // above Linux's pid_max ceiling, so never a live process

function plant(issue: string, worker: string, pid: number, heartbeatAgo: number) {
  const t = Date.now() / 1000 - heartbeatAgo;
  writeFileSync(
    join(claim.claimsDir(root), `${issue}.json`),
    JSON.stringify({ issue, worker, pid, claimed_at: t, heartbeat: t }),
  );
}

describe("acquire", () => {
  test("claims a free issue", () => {
    expect(claim.acquire(root, "7", "w1", 900)).toEqual({ ok: true });
  });

  test("refuses an issue held by a live claim", () => {
    claim.acquire(root, "7", "w1", 900);
    expect(claim.acquire(root, "7", "w2", 900)).toEqual({ ok: false, heldBy: "w1" });
  });

  test("steals a claim whose heartbeat is old and whose pid is dead", () => {
    plant("7", "w1", DEAD_PID, 10_000);
    expect(claim.acquire(root, "7", "w2", 900)).toEqual({ ok: true, reclaimedFrom: "w1" });
  });

  test("does not steal an old claim whose process is still alive", () => {
    plant("7", "w1", process.pid, 10_000);
    expect(claim.acquire(root, "7", "w2", 900).ok).toBe(false);
  });
});

describe("release", () => {
  test("refuses to release another worker's claim", () => {
    claim.acquire(root, "7", "w1", 900);
    expect(claim.release(root, "7", "w2")).toEqual({ ok: false, heldBy: "w1" });
    expect(claim.listClaims(root)).toHaveLength(1);
  });

  test("releases its own claim", () => {
    claim.acquire(root, "7", "w1", 900);
    expect(claim.release(root, "7", "w1")).toEqual({ ok: true });
    expect(claim.listClaims(root)).toHaveLength(0);
  });
});

test("heartbeat refreshes only the holder's claim", () => {
  plant("7", "w1", process.pid, 500);
  expect(claim.heartbeat(root, "7", "w2")).toBe(false);
  expect(claim.heartbeat(root, "7", "w1")).toBe(true);
  const [rec] = claim.listClaims(root);
  expect(Date.now() / 1000 - (rec?.heartbeat ?? 0)).toBeLessThan(5);
});

test("reap drops stale claims and keeps live ones", () => {
  plant("1", "w1", DEAD_PID, 10_000);
  plant("2", "w2", process.pid, 0);
  expect(claim.reap(root, 900)).toEqual(["1"]);
  expect(claim.listClaims(root).map((c) => c.issue)).toEqual(["2"]);
});
