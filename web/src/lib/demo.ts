import "server-only";

import { readFile } from "node:fs/promises";
import path from "node:path";
import { connection } from "next/server";
import { filterPipelines, shiftTimes, type Snapshot } from "./demo-core";
import type { AuthState, JobLog, JobOut } from "./types";

/**
 * Frontend-only demo: serves a snapshot exported from the real API
 * (`python -m pipepulse.seed.snapshot`) instead of calling a backend. Enabled with
 * PIPEPULSE_DEMO=true. Timestamps are shifted by "now - generated_at" on every read, so the
 * demo always looks like it was captured a moment ago.
 */

export const DEMO_ENABLED = process.env.PIPEPULSE_DEMO === "true";

const SNAPSHOT_PATH = path.join(process.cwd(), "src/demo/snapshot.json");
let snapshotPromise: Promise<Snapshot> | undefined;

function loadSnapshot(): Promise<Snapshot> {
  snapshotPromise ??= readFile(SNAPSHOT_PATH, "utf8").then((raw) => JSON.parse(raw) as Snapshot);
  return snapshotPromise;
}

export class DemoNotFound extends Error {}

type Params = Record<string, string | number>;

/** The API's routes, answered from the snapshot. */
export async function demoGet(apiPath: string, params: Params = {}): Promise<unknown> {
  // Reading a local file doesn't count as request-time I/O, so without this Next.js would
  // prerender the demo at build time and freeze its timestamps.
  await connection();
  const now = Date.now();
  const snapshot = await loadSnapshot();
  const shift = <T>(value: T) => shiftTimes(value, now - Date.parse(snapshot.generated_at));
  const days = String(params.days ?? "");

  if (apiPath === "/api/auth/me") {
    return { demo_mode: true, admin_enabled: false, authenticated: false } satisfies AuthState;
  }
  if (apiPath === "/api/summary") return shift(snapshot.summary);
  if (apiPath === "/api/projects") {
    return shift(Object.values(snapshot.projects).map((p) => p.rows["7"]));
  }

  const project = /^\/api\/projects\/(\d+)(?:\/(stats|trend))?$/.exec(apiPath);
  if (project) {
    const entry = snapshot.projects[project[1]];
    const kind = (project[2] ?? "rows") as "rows" | "stats" | "trend";
    const data = entry?.[kind][days || (kind === "trend" ? "30" : "7")];
    if (!data) throw new DemoNotFound(apiPath);
    return shift(data);
  }

  if (apiPath === "/api/pipelines") return shift(filterPipelines(snapshot, params));

  const log = /^\/api\/jobs\/(\d+)\/log$/.exec(apiPath);
  if (log) {
    for (const pipeline of snapshot.pipelines) {
      const job = pipeline.failed_jobs.find((j: JobOut) => String(j.id) === log[1]);
      if (job) {
        return shift({ job, pipeline_id: pipeline.id, log: snapshot.logs[log[1]] ?? null } satisfies JobLog);
      }
    }
  }
  throw new DemoNotFound(apiPath);
}
