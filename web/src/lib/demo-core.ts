import type { PipelineOut, PipelinePage, ProjectRow, ProjectStats, Summary, TrendPoint } from "./types";

// Pure parts of the frontend-only demo (see demo.ts), kept free of server-only imports so they
// can be unit tested.

type Windowed<T> = Record<string, T>; // keyed by window length in days

export interface Snapshot {
  generated_at: string;
  summary: Summary;
  projects: Record<string, { rows: Windowed<ProjectRow>; stats: Windowed<ProjectStats>; trend: Windowed<TrendPoint[]> }>;
  pipelines: PipelineOut[];
  logs: Record<string, string>;
}

const TIME_KEYS = new Set([
  "created_at",
  "started_at",
  "finished_at",
  "updated_at",
  "last_polled_at",
  "failed_at",
  "recovered_at",
  "open_since",
]);
const DAY_MS = 86_400_000;

/** Deep copy with every timestamp moved forward by `deltaMs` (calendar days by whole days). */
export function shiftTimes<T>(value: T, deltaMs: number): T {
  if (Array.isArray(value)) return value.map((v) => shiftTimes(v, deltaMs)) as T;
  if (value === null || typeof value !== "object") return value;
  const out: Record<string, unknown> = {};
  for (const [key, v] of Object.entries(value)) {
    if (typeof v === "string" && TIME_KEYS.has(key)) {
      out[key] = new Date(Date.parse(v) + deltaMs).toISOString();
    } else if (typeof v === "string" && key === "day") {
      const shifted = new Date(Date.parse(`${v}T00:00:00Z`) + Math.round(deltaMs / DAY_MS) * DAY_MS);
      out[key] = shifted.toISOString().slice(0, 10);
    } else {
      out[key] = shiftTimes(v, deltaMs);
    }
  }
  return out as T;
}

type Params = Record<string, string | number>;

/** Same semantics as GET /api/pipelines (filters, sort with nulls last, limit/offset). */
export function filterPipelines(snapshot: Snapshot, params: Params): PipelinePage {
  const projectId = params.project_id === undefined ? undefined : Number(params.project_id);
  const defaultBranch = (id: number) => snapshot.projects[id]?.rows["7"]?.default_branch ?? "main";
  const sort = String(params.sort ?? "-created_at");
  const limit = Number(params.limit ?? 50);
  const offset = Number(params.offset ?? 0);

  const matching = snapshot.pipelines.filter(
    (p) =>
      (projectId === undefined || p.project_id === projectId) &&
      (params.status === undefined || p.status === params.status) &&
      (params.source === undefined || p.source === params.source) &&
      (params.scope !== "default" || p.ref === defaultBranch(p.project_id)),
  );

  const byDuration = (a: PipelineOut, b: PipelineOut) =>
    a.duration_s === null ? 1 : b.duration_s === null ? -1 : a.duration_s - b.duration_s;
  const byCreated = (a: PipelineOut, b: PipelineOut) =>
    Date.parse(a.created_at) - Date.parse(b.created_at) || a.id - b.id;
  const comparators: Record<string, (a: PipelineOut, b: PipelineOut) => number> = {
    "-created_at": (a, b) => byCreated(b, a),
    created_at: byCreated,
    "-duration": (a, b) =>
      a.duration_s === null || b.duration_s === null ? byDuration(a, b) : byDuration(b, a) || b.id - a.id,
    duration: (a, b) => byDuration(a, b) || a.id - b.id,
  };
  matching.sort(comparators[sort] ?? comparators["-created_at"]);

  return { items: matching.slice(offset, offset + limit), total: matching.length, limit, offset };
}
