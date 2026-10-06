#!/usr/bin/env bun
/**
 * The in-flight ledger for the swarm.
 *
 * Only the supervisor selects issues, so this is not contention control — there is no race
 * over a queue that exactly one thread reads. It is the record of what is running, under which
 * worker, since when: it answers `status`, and it survives a crash so the next run knows what
 * was mid-flight.
 *
 * It is still built on a real atomic primitive, because the cost is nothing and the one race
 * left (two supervisors on one workspace) is exactly the kind that slips past a lock-free
 * design. Opening with the `wx` flag is `O_CREAT|O_EXCL`: it either creates the entry or fails,
 * with no window in between.
 *
 * Entries carry a heartbeat. A worker that is killed, OOMs, or hits a crashed model leaves its
 * entry behind; without a heartbeat that issue is parked forever and the swarm quietly shrinks.
 * An entry is stale when its heartbeat is older than the TTL *and* its pid is gone.
 *
 * Usage:
 *     claim.ts acquire <issue> --worker W [--root DIR] [--ttl S]   exit 0 claimed, 1 taken
 *     claim.ts heartbeat <issue> --worker W
 *     claim.ts release <issue> --worker W
 *     claim.ts list [--root DIR]
 *     claim.ts reap [--root DIR] [--ttl S]      drop stale entries, print what was freed
 */

import {
  closeSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  renameSync,
  unlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { basename, join } from "node:path";
import { parseArgs } from "node:util";

export const DEFAULT_TTL = 900; // 15 minutes without a heartbeat and we assume the worker is gone

/** On-disk shape. snake_case so a ledger written by the old Python supervisor still reads. */
export interface ClaimRecord {
  issue: string;
  worker: string;
  pid: number;
  claimed_at: number;
  heartbeat: number;
}

export type AcquireResult = { ok: true; reclaimedFrom?: string } | { ok: false; heldBy: string };

export type ReleaseResult = { ok: true } | { ok: false; heldBy: string };

const now = () => Date.now() / 1000;

export function claimsDir(root: string): string {
  const d = join(root, ".swarm", "claims");
  mkdirSync(d, { recursive: true });
  return d;
}

function lockPath(root: string, issue: string): string {
  return join(claimsDir(root), `${issue}.json`);
}

export function pidAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch (e) {
    // EPERM means it exists, owned by someone else. Getting this backwards makes a live
    // process look dead.
    return (e as NodeJS.ErrnoException).code === "EPERM";
  }
}

function isClaimRecord(x: unknown): x is ClaimRecord {
  if (typeof x !== "object" || x === null) return false;
  const r = x as Record<string, unknown>;
  return (
    typeof r.issue === "string" &&
    typeof r.worker === "string" &&
    typeof r.pid === "number" &&
    typeof r.heartbeat === "number"
  );
}

function readLock(p: string): ClaimRecord | null {
  try {
    const parsed: unknown = JSON.parse(readFileSync(p, "utf8"));
    return isClaimRecord(parsed) ? parsed : null;
  } catch {
    return null;
  }
}

/** Write via a temp file and rename, so a concurrent reader sees the old file or the new one —
 * never a half-written one. */
function writeAtomic(p: string, rec: ClaimRecord, tag: string): void {
  const tmp = `${p}.${tag}.${process.pid}`;
  writeFileSync(tmp, JSON.stringify(rec, null, 2));
  renameSync(tmp, p);
}

export function isStale(rec: ClaimRecord | null, ttl: number): boolean {
  if (!rec) return true;
  if (now() - rec.heartbeat <= ttl) return false;
  return !pidAlive(rec.pid);
}

export function acquire(root: string, issue: string, worker: string, ttl: number): AcquireResult {
  const p = lockPath(root, issue);
  const rec: ClaimRecord = { issue, worker, pid: process.pid, claimed_at: now(), heartbeat: now() };

  let fd: number;
  try {
    fd = openSync(p, "wx", 0o644);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e;
    const existing = readLock(p);
    if (!isStale(existing, ttl)) return { ok: false, heldBy: existing?.worker ?? "unknown" };
    // Stale. Replace it atomically, then confirm we are the one who landed.
    writeAtomic(p, rec, "steal");
    const after = readLock(p);
    if (after?.pid !== process.pid) return { ok: false, heldBy: after?.worker ?? "unknown" };
    return { ok: true, reclaimedFrom: existing?.worker ?? "?" };
  }
  writeSync(fd, JSON.stringify(rec, null, 2));
  closeSync(fd);
  return { ok: true };
}

export function heartbeat(root: string, issue: string, worker: string): boolean {
  const p = lockPath(root, issue);
  const rec = readLock(p);
  if (!rec || rec.worker !== worker) return false;
  writeAtomic(p, { ...rec, heartbeat: now() }, "hb");
  return true;
}

export function release(root: string, issue: string, worker: string): ReleaseResult {
  const p = lockPath(root, issue);
  const rec = readLock(p);
  // Refuse to release someone else's claim — that is how two workers end up on one issue with
  // neither of them holding it.
  if (rec && rec.worker !== worker) return { ok: false, heldBy: rec.worker };
  try {
    unlinkSync(p);
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "ENOENT") throw e;
  }
  return { ok: true };
}

export function listClaims(root: string): ClaimRecord[] {
  const dir = claimsDir(root);
  return readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()
    .flatMap((f) => readLock(join(dir, f)) ?? []);
}

export function printClaims(root: string): void {
  const rows = listClaims(root);
  if (rows.length === 0) {
    console.log("no active claims");
    return;
  }
  console.log(
    `${"issue".padEnd(10)}${"worker".padEnd(14)}${"pid".padEnd(9)}${"last heartbeat".padStart(15)}`,
  );
  for (const r of rows) {
    const age = `${Math.floor(now() - r.heartbeat)}s ago`;
    console.log(
      `${r.issue.padEnd(10)}${r.worker.padEnd(14)}${String(r.pid).padEnd(9)}${age.padStart(15)}`,
    );
  }
}

/** Drop stale entries. Returns the issues freed. */
export function reap(root: string, ttl: number): string[] {
  const dir = claimsDir(root);
  const freed: string[] = [];
  for (const f of readdirSync(dir)
    .filter((f) => f.endsWith(".json"))
    .sort()) {
    const p = join(dir, f);
    const rec = readLock(p);
    if (isStale(rec, ttl)) {
      freed.push(rec?.issue ?? basename(f, ".json"));
      try {
        unlinkSync(p);
      } catch {
        /* already gone */
      }
    }
  }
  return freed;
}

function main(argv: string[]): number {
  const { values, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      worker: { type: "string", default: "w0" },
      root: { type: "string", default: "." },
      ttl: { type: "string", default: String(DEFAULT_TTL) },
    },
  });
  const [action, issue] = positionals;
  const { worker, root } = values;
  const ttl = Number(values.ttl);

  const needsIssue = (): string => {
    if (!issue) throw new Error(`${action} needs an issue number`);
    return issue;
  };

  switch (action) {
    case "acquire": {
      const r = acquire(root, needsIssue(), worker, ttl);
      if (!r.ok) {
        console.error(`issue ${issue} is held by ${r.heldBy}`);
        return 1;
      }
      console.log(
        r.reclaimedFrom
          ? `claimed ${issue} (reclaimed a stale lock held by ${r.reclaimedFrom})`
          : `claimed ${issue}`,
      );
      return 0;
    }
    case "heartbeat":
      if (heartbeat(root, needsIssue(), worker)) return 0;
      console.error(`no lock for ${issue} held by ${worker}`);
      return 1;
    case "release": {
      const r = release(root, needsIssue(), worker);
      if (!r.ok) {
        console.error(`refusing: ${issue} is held by ${r.heldBy}, not ${worker}`);
        return 1;
      }
      console.log(`released ${issue}`);
      return 0;
    }
    case "list":
      printClaims(root);
      return 0;
    case "reap": {
      const freed = reap(root, ttl);
      console.log(
        `reaped ${freed.length} stale claim(s)${freed.length ? `: ${freed.join(", ")}` : ""}`,
      );
      return 0;
    }
    default:
      console.error(
        "usage: claim.ts acquire|heartbeat|release|list|reap [issue] [--worker W] [--root DIR] [--ttl S]",
      );
      return 2;
  }
}

if (import.meta.main) process.exit(main(process.argv.slice(2)));
