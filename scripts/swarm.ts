#!/usr/bin/env bun
/**
 * The swarm supervisor — point it at one repo, walk away.
 *
 *     swarm.ts run --repo owner/name --workers 10
 *     swarm.ts status
 *     swarm.ts stop
 *
 * One process on your machine. It polls the repository for actionable issues, keeps N workers
 * busy, and replaces the ones that finish. Each worker gets its own git worktree and its own
 * headless Claude.
 *
 * **Only the supervisor picks issues.** Workers never choose; they are handed one. That single
 * fact removes the race rather than managing it — you cannot have contention over a queue that
 * exactly one thread reads. Dispatch is one pass: select the free issues, record them in the
 * ledger, label them on GitHub, then spawn. A worker that starts already knows its issue and
 * never looks at the queue.
 *
 * The only genuine race left is two supervisors on one workspace — two terminals, or a leftover
 * process you forgot. That is what the supervisor lock below is for, and it is the whole of the
 * concurrency control. The per-issue ledger is the in-flight record, so `status` can tell you
 * what is running and a crash can be recovered from.
 *
 * **A run is bound to exactly one repository.** The bound repo is written to .swarm/config.json
 * and every worker re-checks it before touching anything. This is a hard constraint, not a
 * default: an agent with a shell and a GitHub token that wanders into the wrong repository is
 * the failure mode with no undo.
 *
 * Concurrency is a spend dial. The Bun rewrite ran 64 agents at once and cost about $165,000
 * over eleven days. Start at 2 or 3 and watch what it does before you turn it up.
 */

import {
  closeSync,
  existsSync,
  mkdirSync,
  openSync,
  readdirSync,
  readFileSync,
  rmSync,
  statfsSync,
  statSync,
  unlinkSync,
  writeFileSync,
  writeSync,
} from "node:fs";
import { cpus, homedir } from "node:os";
import { join, resolve } from "node:path";
import { parseArgs } from "node:util";
import * as claim from "./claim.ts";

const HEARTBEAT_MS = 60_000;
const POLL_MS = 30_000;
const READY_LABEL = "ready";
const WORKING_LABEL = "in-progress";
const BLOCKED_LABEL = "blocked";

// ---------------------------------------------------------------- shell

export interface ShResult {
  code: number;
  stdout: string;
  stderr: string;
}

/** Every external command goes through one of these, so tests can hand in a fake. */
export type Sh = (args: string[], cwd?: string) => ShResult;

export const sh: Sh = (args, cwd) => {
  const r = Bun.spawnSync(args, { ...(cwd ? { cwd } : {}), stdout: "pipe", stderr: "pipe" });
  return { code: r.exitCode, stdout: r.stdout.toString(), stderr: r.stderr.toString() };
};

function log(who: string, msg: string): void {
  const t = new Date().toTimeString().slice(0, 8);
  console.log(`[${t}] ${who.padEnd(9)} ${msg}`);
}

// ---------------------------------------------------------------- repo binding

function swarmRoot(workdir: string): string {
  const d = join(workdir, ".swarm");
  mkdirSync(d, { recursive: true });
  return d;
}

function readPidfile(p: string): number | null {
  try {
    const pid = Number(readFileSync(p, "utf8").split(/\s+/)[0]);
    return Number.isInteger(pid) && pid > 0 ? pid : null;
  } catch {
    return null;
  }
}

/**
 * One supervisor per workspace. This is the only real race in the system.
 *
 * Workers cannot collide because they never select. Two supervisors can: both read the same
 * queue, both take the first three issues, both spawn. A pidfile created with O_EXCL settles
 * it, and a stale one (process gone) is taken over rather than blocking forever.
 */
function acquireSupervisorLock(workdir: string): string {
  const p = join(swarmRoot(workdir), "supervisor.pid");
  const stamp = `${process.pid} ${Date.now() / 1000}\n`;
  try {
    const fd = openSync(p, "wx", 0o644);
    writeSync(fd, stamp);
    closeSync(fd);
    return p;
  } catch (e) {
    if ((e as NodeJS.ErrnoException).code !== "EEXIST") throw e;
  }
  const other = readPidfile(p);
  if (other && other !== process.pid && claim.pidAlive(other)) {
    fail(
      `a supervisor is already running for ${workdir} (pid ${other}).\n` +
        `Two supervisors would both read the same queue and dispatch the same issues. ` +
        `Stop that one, or use a different --workdir.`,
    );
  }
  writeFileSync(p, stamp);
  return p;
}

function releaseSupervisorLock(p: string): void {
  if (readPidfile(p) === process.pid) unlinkSync(p);
}

interface SwarmConfig {
  repo: string;
  bound_at: number;
}

/** Record the repository this run is bound to, and refuse to change it silently. */
function bindRepo(workdir: string, repo: string): SwarmConfig {
  const cfgPath = join(swarmRoot(workdir), "config.json");
  if (existsSync(cfgPath)) {
    const cfg = JSON.parse(readFileSync(cfgPath, "utf8")) as SwarmConfig;
    if (cfg.repo !== repo) {
      fail(
        `${workdir}/.swarm is already bound to ${cfg.repo}.\n` +
          `A workspace serves one repository. Use a different --workdir for ${repo}, ` +
          `or delete .swarm/ if you are certain nothing is running.`,
      );
    }
    return cfg;
  }
  const cfg: SwarmConfig = { repo, bound_at: Date.now() / 1000 };
  writeFileSync(cfgPath, JSON.stringify(cfg, null, 2));
  return cfg;
}

function ensureClone(workdir: string, repo: string): string {
  const base = join(workdir, "repo");
  if (existsSync(join(base, ".git"))) {
    const origin = sh(["git", "-C", base, "remote", "get-url", "origin"]).stdout.trim();
    if (!origin.includes(repo)) fail(`${base} points at ${origin}, not ${repo}`);
    sh(["git", "-C", base, "fetch", "--quiet", "origin"]);
    return base;
  }
  log("supervisor", `cloning ${repo}`);
  const r = sh(["gh", "repo", "clone", repo, base]);
  if (r.code !== 0) fail(`clone failed\n${r.stderr.trim()}`);
  return base;
}

function defaultBranch(repoDir: string): string {
  const r = sh(["git", "-C", repoDir, "symbolic-ref", "refs/remotes/origin/HEAD"]);
  const ref = r.stdout.trim();
  return r.code === 0 && ref ? ref.slice(ref.lastIndexOf("/") + 1) : "main";
}

// ---------------------------------------------------------------- work queue

export interface Issue {
  number: number;
  title: string;
}

interface GhIssue {
  number: number;
  title: string;
  labels: { name: string }[];
}

/**
 * Open issues that are ready to be built, oldest first.
 *
 * Deliberately conservative: an issue must carry the ready label and must not carry the
 * working label. Anything a human is still writing simply has no label yet.
 */
export function actionableIssues(run: Sh, repo: string, label: string): Issue[] {
  const r = run([
    "gh",
    "issue",
    "list",
    "--repo",
    repo,
    "--state",
    "open",
    "--label",
    label,
    "--limit",
    "200",
    "--json",
    "number,title,labels",
  ]);
  if (r.code !== 0) {
    log("supervisor", `gh issue list failed: ${r.stderr.trim()}`);
    return [];
  }
  const issues = JSON.parse(r.stdout || "[]") as GhIssue[];
  return issues
    .filter((it) => !it.labels.some((l) => l.name === WORKING_LABEL))
    .map(({ number, title }) => ({ number, title }))
    .sort((a, b) => a.number - b.number);
}

export interface DispatchCtx {
  run: Sh;
  repo: string;
  workdir: string;
  label: string;
  claimTtl: number;
}

export interface Assignment {
  slot: string;
  issue: Issue;
}

/**
 * Select issues for the given free slots and hand them out. The only place issues are chosen.
 *
 * Single-threaded by construction, so the selection needs no locking of its own. Each issue
 * is recorded in the ledger under the slot that will run it, and labelled on GitHub, *before*
 * a worker exists for it — so what you see on GitHub is true from the moment it is true.
 *
 * The caller passes the actual free slot names. The ledger entry and the worker that later
 * releases it must agree on the name, or the release is refused and the entry leaks.
 */
export function dispatch(ctx: DispatchCtx, freeSlots: readonly string[]): Assignment[] {
  claim.reap(ctx.workdir, ctx.claimTtl);

  const inFlight = new Set(claim.listClaims(ctx.workdir).map((c) => c.issue));
  const queue = actionableIssues(ctx.run, ctx.repo, ctx.label).filter(
    (i) => !inFlight.has(String(i.number)),
  );

  const assigned: Assignment[] = [];
  const slots = [...freeSlots];
  for (const issue of queue) {
    const slot = slots[0];
    if (slot === undefined) break;
    const n = String(issue.number);

    if (!claim.acquire(ctx.workdir, n, slot, ctx.claimTtl).ok) {
      // Should not happen — nothing else selects. If it does, something is wrong with our
      // assumptions rather than with this issue, so say so loudly.
      log(
        "supervisor",
        `unexpected: #${n} is already in the ledger — nothing else should be selecting issues`,
      );
      continue;
    }

    const lr = ctx.run([
      "gh",
      "issue",
      "edit",
      n,
      "--repo",
      ctx.repo,
      "--add-label",
      WORKING_LABEL,
      "--remove-label",
      ctx.label,
    ]);
    if (lr.code !== 0) {
      // If we cannot mark it taken, do not build it: a second run of the supervisor, or you
      // looking at GitHub, would both see it as free.
      log("supervisor", `#${n} skipped — could not label it: ${lr.stderr.trim()}`);
      claim.release(ctx.workdir, n, slot);
      continue;
    }

    slots.shift();
    assigned.push({ slot, issue });
  }
  return assigned;
}

// ---------------------------------------------------------------- resources

/** Free-plus-reclaimable, which is what a new process can actually get. */
function availableRamGb(): number {
  try {
    const line = readFileSync("/proc/meminfo", "utf8")
      .split("\n")
      .find((l) => l.startsWith("MemAvailable:"));
    return line ? Number(line.split(/\s+/)[1]) / 1e6 : 0;
  } catch {
    return 0;
  }
}

/** Can we box a worker? Needs cgroup v2 with memory delegated to this user. */
function cgroupAvailable(): boolean {
  if (!Bun.which("systemd-run")) return false;
  try {
    const uid = process.getuid?.() ?? 0;
    return readFileSync(`/sys/fs/cgroup/user.slice/user-${uid}.slice/cgroup.controllers`, "utf8")
      .split(/\s+/)
      .includes("memory");
  } catch {
    return false;
  }
}

export interface Limits {
  memoryMax: string;
  cpuQuota: string;
  tasksMax: number;
}

/**
 * Box a worker so a runaway one dies alone.
 *
 * Disk was the loud problem; memory is the quiet one. A test that never terminates, a model
 * that retries forever, a build that allocates without bound — unchecked, any of these
 * competes with the whole machine, and at 3am the kernel's OOM killer picks a victim at
 * random. It might pick the supervisor, and then the swarm is dead and nothing says so.
 *
 * Inside a cgroup, that worker is killed and nothing else notices. It exits non-zero, which
 * the swarm already treats as a failure: the issue is labelled `blocked` and its worktree is
 * kept, so the evidence survives.
 *
 * A scope covers the process and everything it spawns, which is the point — the build and
 * the test runner are where the memory actually goes, not in the agent itself.
 */
function wrapInCgroup(cmd: string[], name: string, limits: Limits): string[] {
  return [
    "systemd-run",
    "--user",
    "--scope",
    "--quiet",
    `--unit=swarm-${name}-${process.pid}`,
    "-p",
    `MemoryMax=${limits.memoryMax}`,
    "-p",
    "MemorySwapMax=0", // swapping instead of dying is how a machine locks up
    "-p",
    `CPUQuota=${limits.cpuQuota}`,
    "-p",
    `TasksMax=${limits.tasksMax}`,
    "--",
    ...cmd,
  ];
}

function freeGb(path: string): number {
  const s = statfsSync(path);
  return (s.bavail * s.bsize) / 1e9;
}

/**
 * What one worker's tree costs, measured rather than guessed.
 *
 * The checkout itself is usually small; the expensive part is whatever the project's own
 * install puts there. Measuring the repo gives a floor, not the truth, so callers treat it
 * as a lower bound and keep headroom.
 */
function worktreeCostGb(dir: string): number {
  const bytes = (d: string): number => {
    let total = 0;
    for (const entry of readdirSync(d, { withFileTypes: true })) {
      const p = join(d, entry.name);
      if (entry.isDirectory()) {
        if (entry.name !== ".git") total += bytes(p);
      } else if (entry.isFile()) {
        try {
          total += statSync(p).size;
        } catch {
          /* vanished mid-walk */
        }
      }
    }
    return total;
  };
  return bytes(dir) / 1e9;
}

// ---------------------------------------------------------------- worktrees

/**
 * Did this branch actually reach the base branch on the remote?
 *
 * Asked before deleting anything. A worker that believes it merged and did not is the one
 * case where cleaning up destroys real work, so this checks the remote rather than trusting
 * the worker's own report.
 *
 * A squash-merge leaves no ancestry, so the second check asks GitHub for a merged PR from the
 * branch. It must never infer a merge from the branch being absent on the remote: a branch
 * that was never pushed is absent too, and that is exactly the work that exists nowhere else.
 */
export function mergeLanded(
  run: Sh,
  repoDir: string,
  repo: string,
  branch: string,
  base: string,
): boolean {
  run(["git", "-C", repoDir, "fetch", "--quiet", "--prune", "origin"]);
  const merged = run(["git", "-C", repoDir, "branch", "-r", "--merged", `origin/${base}`]);
  // Whole-line match: a substring test would count origin/swarm/1 as merged when only
  // origin/swarm/12 is.
  if (merged.code === 0 && merged.stdout.split("\n").some((l) => l.trim() === `origin/${branch}`)) {
    return true;
  }
  const prs = run([
    "gh",
    "pr",
    "list",
    "--repo",
    repo,
    "--head",
    branch,
    "--base",
    base,
    "--state",
    "merged",
    "--json",
    "number",
    "--limit",
    "1",
  ]);
  return prs.code === 0 && (JSON.parse(prs.stdout || "[]") as unknown[]).length > 0;
}

/**
 * Remove a worktree and its local branch, properly.
 *
 * Deleting the directory alone leaves administrative files under .git/worktrees, and the next
 * `worktree add` on that path fails with a stale-lock error nobody enjoys diagnosing.
 */
function removeWorktree(repoDir: string, wt: string, branch: string): void {
  sh(["git", "-C", repoDir, "worktree", "remove", "--force", wt]);
  rmSync(wt, { recursive: true, force: true });
  sh(["git", "-C", repoDir, "worktree", "prune"]);
  sh(["git", "-C", repoDir, "branch", "-D", branch]);
}

function createWorktree(repoDir: string, wt: string, branch: string, base: string): boolean {
  if (existsSync(wt)) {
    sh(["git", "-C", repoDir, "worktree", "remove", "--force", wt]);
    rmSync(wt, { recursive: true, force: true });
  }
  mkdirSync(join(wt, ".."), { recursive: true });
  sh(["git", "-C", repoDir, "worktree", "prune"]);
  const r = sh(["git", "-C", repoDir, "worktree", "add", "-b", branch, wt, `origin/${base}`]);
  if (r.code !== 0) log("supervisor", `worktree failed: ${r.stderr.trim()}`);
  return r.code === 0;
}

// ---------------------------------------------------------------- worker

export type Outcome = "merged" | "worktree-failed" | "merge-not-found" | `exit-${number}`;

/**
 * Heartbeat for exactly as long as the process lives.
 *
 * Takes the process's exit promise rather than a handle that may not exist yet, so it cannot
 * be started before there is anything to keep warm.
 */
export function keepWarm(exited: Promise<unknown>, beat: () => void, everyMs: number): void {
  beat();
  const timer = setInterval(beat, everyMs);
  void exited.finally(() => {
    clearInterval(timer);
  });
}

interface WorkerCtx {
  workdir: string;
  repo: string;
  repoDir: string;
  base: string;
  permissionMode: string;
  model: string | undefined;
  limits: Limits | null;
}

async function runWorker(ctx: WorkerCtx, slot: string, issue: Issue): Promise<Outcome> {
  const n = issue.number;
  const branch = `swarm/${n}`;
  const wt = join(ctx.workdir, "worktrees", slot);
  const transcript = join(ctx.workdir, "logs", `${slot}-issue-${n}.log`);

  const markBlocked = (why: string) => {
    sh([
      "gh",
      "issue",
      "edit",
      String(n),
      "--repo",
      ctx.repo,
      "--add-label",
      BLOCKED_LABEL,
      "--remove-label",
      WORKING_LABEL,
    ]);
    sh([
      "gh",
      "issue",
      "comment",
      String(n),
      "--repo",
      ctx.repo,
      "--body",
      `Swarm worker \`${slot}\` could not complete this issue (${why}). ` +
        (existsSync(transcript) ? `Transcript: \`${transcript}\`. ` : "") +
        (existsSync(wt) ? `Worktree kept at \`${wt}\` for diagnosis. ` : "") +
        `Labelled \`${BLOCKED_LABEL}\` rather than returned to \`${READY_LABEL}\`, so it does not retry forever.`,
    ]);
  };

  try {
    if (!createWorktree(ctx.repoDir, wt, branch, ctx.base)) {
      markBlocked("its worktree could not be created");
      return "worktree-failed";
    }

    log(slot, `#${n} ${issue.title.slice(0, 56)}`);
    let cmd = ["claude", "-p", `/work-issue ${n}`, "--permission-mode", ctx.permissionMode];
    if (ctx.model) cmd.push("--model", ctx.model);
    if (ctx.limits) cmd = wrapInCgroup(cmd, slot, ctx.limits);

    mkdirSync(join(ctx.workdir, "logs"), { recursive: true });
    const fd = openSync(transcript, "w");
    const proc = Bun.spawn(cmd, {
      cwd: wt,
      env: {
        ...process.env,
        SWARM_WORKER: slot,
        SWARM_REPO: ctx.repo,
        SWARM_ISSUE: String(n),
        SWARM_BRANCH: branch,
        SWARM_BASE: ctx.base,
      },
      stdout: fd,
      stderr: fd,
    });
    keepWarm(proc.exited, () => claim.heartbeat(ctx.workdir, String(n), slot), HEARTBEAT_MS);
    const code = await proc.exited;
    closeSync(fd);

    if (code !== 0) {
      // Failure keeps its worktree on purpose. The transcript says what the worker thought;
      // the tree is the only place the state that broke it still exists.
      log(slot, `#${n} exit-${code} — worktree kept for diagnosis at ${wt}`);
      markBlocked(`exit ${code}`);
      return `exit-${code}`;
    }
    if (!mergeLanded(sh, ctx.repoDir, ctx.repo, branch, ctx.base)) {
      // It exited clean but nothing reached the base branch — it stopped on purpose, or it
      // believes it merged and did not. Either way a human looks; the tree is kept because
      // deleting it would destroy the only copy of real work.
      log(slot, `#${n} exited clean but no merge landed — keeping ${wt}`);
      markBlocked("it exited cleanly but no merge reached the base branch");
      return "merge-not-found";
    }
    removeWorktree(ctx.repoDir, wt, branch);
    log(slot, `#${n} merged — worktree removed, ${freeGb(ctx.workdir).toFixed(1)}GB free`);
    return "merged";
  } finally {
    claim.release(ctx.workdir, String(n), slot);
  }
}

// ---------------------------------------------------------------- supervisor

function fail(msg: string): never {
  console.error(`error: ${msg}`);
  process.exit(1);
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((done) => {
    const t = setTimeout(done, ms);
    signal.addEventListener(
      "abort",
      () => {
        clearTimeout(t);
        done();
      },
      { once: true },
    );
  });
}

interface RunOpts {
  repo: string;
  workdir: string;
  label: string;
  workers: number;
  model: string | undefined;
  permissionMode: string;
  claimTtl: number;
  graceMs: number;
  once: boolean;
  memoryMax: string | undefined;
  cpuQuota: string | undefined;
  tasksMax: number;
  noLimits: boolean;
  minFreeGb: number;
}

async function run(o: RunOpts): Promise<number> {
  mkdirSync(o.workdir, { recursive: true });
  bindRepo(o.workdir, o.repo);
  const lock = acquireSupervisorLock(o.workdir);
  const repoDir = ensureClone(o.workdir, o.repo);
  const base = defaultBranch(repoDir);

  // Disk is the one resource a cgroup will not protect: the v2 io controller caps bandwidth,
  // not capacity. And it is the resource this design spends hardest, because every worker gets
  // its own checkout and runs the project's own install in it.
  //
  // Cleaning up on merge makes the ceiling `workers x tree`, a constant rather than something
  // that grows all night — which is the only reason a number checked here is still true an
  // hour later.
  const avail = freeGb(o.workdir);
  const perWorker = Math.max(worktreeCostGb(repoDir), 0.05);
  const projected = perWorker * o.workers;
  log(
    "supervisor",
    `disk: ${avail.toFixed(1)}GB free, ~${perWorker.toFixed(2)}GB per worktree, ` +
      `~${projected.toFixed(1)}GB for ${o.workers} worker(s)`,
  );
  if (avail < o.minFreeGb) {
    fail(
      `${avail.toFixed(1)}GB free is below the ${o.minFreeGb}GB floor.\n` +
        `Free space or lower --min-free-gb, but understand what you are choosing: ` +
        `filling the disk does not fail one issue, it takes the machine down.`,
    );
  }

  let limits: Limits | null = null;
  if (o.noLimits) {
    log(
      "supervisor",
      "warning: --no-limits — a runaway worker can take the machine down, and nobody is watching",
    );
  } else if (!cgroupAvailable()) {
    log(
      "supervisor",
      "warning: no cgroup v2 with delegated memory (needs systemd-run). " +
        "Workers run unboxed; a runaway one competes with everything else.",
    );
  } else {
    const ram = availableRamGb();
    const headroom = ram - 4;
    const mem = o.memoryMax ?? `${Math.max(2, headroom / o.workers).toFixed(1)}G`;
    limits = {
      memoryMax: mem,
      cpuQuota: o.cpuQuota ?? `${Math.max(100, Math.floor(cpus().length / o.workers) * 100)}%`,
      tasksMax: o.tasksMax,
    };
    log(
      "supervisor",
      `ram: ${ram.toFixed(1)}GB available; each worker boxed at ${limits.memoryMax} / ${limits.cpuQuota} cpu`,
    );
    if (parseFloat(mem) * o.workers > headroom) {
      log(
        "supervisor",
        `warning: ${o.workers} x ${mem} exceeds ${headroom.toFixed(1)}GB of headroom. ` +
          `They will not all peak at once, but if they do the kernel starts killing workers.`,
      );
    }
  }

  if (projected > avail - o.minFreeGb) {
    const safe = Math.max(1, Math.floor((avail - o.minFreeGb) / perWorker));
    log(
      "supervisor",
      `warning: ${o.workers} workers may not fit. ~${safe} would sit inside the floor. ` +
        `Install size is measured from the repo and is a lower bound — dependencies land later.`,
    );
  }
  log("supervisor", `bound to ${o.repo} (base branch ${base}), ${o.workers} worker(s)`);

  const stop = new AbortController();
  const onSignal = () => {
    log("supervisor", "stopping — letting in-flight workers finish, claims will release");
    stop.abort();
  };
  process.on("SIGINT", onSignal);
  process.on("SIGTERM", onSignal);

  const ctx: WorkerCtx = {
    workdir: o.workdir,
    repo: o.repo,
    repoDir,
    base,
    permissionMode: o.permissionMode,
    model: o.model,
    limits,
  };
  const dctx: DispatchCtx = {
    run: sh,
    repo: o.repo,
    workdir: o.workdir,
    label: o.label,
    claimTtl: o.claimTtl,
  };
  const allSlots = Array.from({ length: o.workers }, (_, i) => `w${i + 1}`);
  // A slot is busy exactly as long as its promise is in this map.
  const active = new Map<string, Promise<void>>();
  let idlePolls = 0;

  while (!stop.signal.aborted) {
    // Pausing costs throughput; filling the disk costs the machine.
    if (freeGb(o.workdir) < o.minFreeGb) {
      log(
        "supervisor",
        `paused — ${freeGb(o.workdir).toFixed(1)}GB free is under the ${o.minFreeGb}GB floor. ` +
          `Waiting for workers to finish and release their trees.`,
      );
      await Promise.race([sleep(POLL_MS, stop.signal), ...active.values()]);
      continue;
    }

    const freeSlots = allSlots.filter((s) => !active.has(s));
    if (freeSlots.length > 0) {
      const assigned = dispatch(dctx, freeSlots);

      if (assigned.length === 0 && active.size === 0) {
        idlePolls += 1;
        if (o.once) {
          log("supervisor", "queue empty — exiting (--once)");
          break;
        }
        if (idlePolls === 1) log("supervisor", `queue empty, polling every ${POLL_MS / 1000}s`);
      } else {
        idlePolls = 0;
      }

      if (assigned.length > 0) sh(["git", "-C", repoDir, "fetch", "--quiet", "origin"]);
      for (const { slot, issue } of assigned) {
        const job = runWorker(ctx, slot, issue)
          .then((outcome) => {
            if (outcome !== "merged") log(slot, `#${issue.number} ${outcome}`);
          })
          .catch((e: unknown) => {
            log(slot, `#${issue.number} crashed: ${String(e)}`);
          })
          .finally(() => active.delete(slot));
        active.set(slot, job);
      }
    }

    // Wake on the poll interval, a stop signal, or any worker finishing — whichever is first.
    await Promise.race([sleep(POLL_MS, stop.signal), ...active.values()]);
  }

  await Promise.race([Promise.all(active.values()), Bun.sleep(o.graceMs)]);
  releaseSupervisorLock(lock);
  log("supervisor", "stopped");
  return 0;
}

function status(workdir: string, label: string): number {
  const cfgPath = join(workdir, ".swarm", "config.json");
  if (!existsSync(cfgPath)) {
    console.log(`no swarm workspace at ${workdir}`);
    return 1;
  }
  const cfg = JSON.parse(readFileSync(cfgPath, "utf8")) as SwarmConfig;
  console.log(`workspace : ${workdir}`);
  console.log(`bound to  : ${cfg.repo}\n`);
  claim.printClaims(workdir);
  const queue = actionableIssues(sh, cfg.repo, label);
  console.log(`\n${queue.length} issue(s) ready and unclaimed`);
  for (const i of queue.slice(0, 10))
    console.log(`  #${String(i.number).padEnd(6)}${i.title.slice(0, 64)}`);
  return 0;
}

/** Ask the running supervisor to stop the same way Ctrl-C does: in-flight workers finish. */
function stopSupervisor(workdir: string): number {
  const pid = readPidfile(join(workdir, ".swarm", "supervisor.pid"));
  if (!pid || !claim.pidAlive(pid)) {
    console.log(`no supervisor running for ${workdir}`);
    return 1;
  }
  process.kill(pid, "SIGTERM");
  console.log(`sent SIGTERM to supervisor ${pid} — in-flight workers will finish first`);
  return 0;
}

const USAGE = `usage: swarm.ts run --repo owner/name [--workers N] [options]
       swarm.ts status [--workdir DIR]
       swarm.ts stop   [--workdir DIR]

  --repo owner/name    the ONE repository this run may touch
  --workdir DIR        default ~/.swarm-workspaces/default
  --label L            default ${READY_LABEL}
  --workers N          concurrent builders. This is a spend dial — start low. (default 3)
  --model M
  --permission-mode M  passed to claude. Do not disable permission checks wholesale. (default acceptEdits)
  --claim-ttl S        default 900
  --grace S            seconds to let in-flight workers finish on stop (default 120)
  --once               drain the queue and exit
  --memory-max 3G      per-worker memory ceiling. Default: headroom / workers.
  --cpu-quota 200%     per-worker CPU. Default: cores / workers.
  --tasks-max N        default 2048
  --no-limits          run workers unboxed. A runaway one can then take the machine down.
  --min-free-gb N      stop dispatching below this much free disk. Cgroups cap memory and CPU
                       but not capacity, so this is the only guard there is. (default 10)`;

async function main(argv: string[]): Promise<number> {
  const { values: v, positionals } = parseArgs({
    args: argv,
    allowPositionals: true,
    options: {
      repo: { type: "string" },
      workdir: { type: "string", default: join(homedir(), ".swarm-workspaces", "default") },
      label: { type: "string", default: READY_LABEL },
      workers: { type: "string", default: "3" },
      model: { type: "string" },
      "permission-mode": { type: "string", default: "acceptEdits" },
      "claim-ttl": { type: "string", default: "900" },
      grace: { type: "string", default: "120" },
      once: { type: "boolean", default: false },
      "memory-max": { type: "string" },
      "cpu-quota": { type: "string" },
      "tasks-max": { type: "string", default: "2048" },
      "no-limits": { type: "boolean", default: false },
      "min-free-gb": { type: "string", default: "10" },
      help: { type: "boolean", short: "h", default: false },
    },
  });
  const workdir = resolve(v.workdir);

  switch (positionals[0]) {
    case "run": {
      if (!v.repo) {
        console.error("run needs --repo owner/name");
        return 2;
      }
      const workers = Number(v.workers);
      if (!Number.isInteger(workers) || workers < 1) {
        console.error("--workers must be a positive integer");
        return 2;
      }
      return run({
        repo: v.repo,
        workdir,
        label: v.label,
        workers,
        model: v.model,
        permissionMode: v["permission-mode"],
        claimTtl: Number(v["claim-ttl"]),
        graceMs: Number(v.grace) * 1000,
        once: v.once,
        memoryMax: v["memory-max"],
        cpuQuota: v["cpu-quota"],
        tasksMax: Number(v["tasks-max"]),
        noLimits: v["no-limits"],
        minFreeGb: Number(v["min-free-gb"]),
      });
    }
    case "status":
      return status(workdir, v.label);
    case "stop":
      return stopSupervisor(workdir);
    default:
      console.log(USAGE);
      return v.help ? 0 : 2;
  }
}

if (import.meta.main) process.exit(await main(process.argv.slice(2)));
