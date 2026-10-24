import { describe, expect, it } from "vitest";
import { filterPipelines, shiftTimes, type Snapshot } from "./demo-core";
import type { PipelineOut } from "./types";

const HOUR = 3_600_000;

describe("shiftTimes", () => {
  it("moves known timestamp keys and leaves other strings alone", () => {
    const shifted = shiftTimes(
      { created_at: "2026-10-24T10:00:00.000Z", ref: "main", nested: [{ open_since: "2026-10-24T11:00:00.000Z" }] },
      2 * HOUR,
    );
    expect(shifted).toEqual({
      created_at: "2026-10-24T12:00:00.000Z",
      ref: "main",
      nested: [{ open_since: "2026-10-24T13:00:00.000Z" }],
    });
  });

  it("moves calendar days by whole days only", () => {
    expect(shiftTimes({ day: "2026-10-24" }, 20 * HOUR)).toEqual({ day: "2026-10-25" });
    expect(shiftTimes({ day: "2026-10-24" }, 5 * HOUR)).toEqual({ day: "2026-10-24" });
  });

  it("keeps nulls and numbers", () => {
    expect(shiftTimes({ finished_at: null, duration_s: 42 }, HOUR)).toEqual({ finished_at: null, duration_s: 42 });
  });
});

function pipeline(id: number, over: Partial<PipelineOut>): PipelineOut {
  return {
    id,
    gitlab_pipeline_id: id,
    status: "success",
    ref: "main",
    duration_s: 100,
    created_at: new Date(Date.UTC(2026, 9, 24, 0, id)).toISOString(),
    finished_at: null,
    web_url: "",
    project_id: 1,
    project_name: "p",
    sha: "a",
    source: "push",
    commit_title: null,
    queued_duration_s: null,
    started_at: null,
    failed_jobs: [],
    ...over,
  };
}

const snapshot = {
  projects: { "1": { rows: { "7": { default_branch: "main" } } }, "2": { rows: { "7": { default_branch: "develop" } } } },
  pipelines: [
    pipeline(1, { status: "failed", duration_s: 30 }),
    pipeline(2, { ref: "feature", source: "merge_request_event", duration_s: 500 }),
    pipeline(3, { duration_s: null, status: "running" }),
    pipeline(4, { project_id: 2, ref: "develop" }),
    pipeline(5, { project_id: 2, ref: "main" }),
  ],
} as unknown as Snapshot;

const ids = (params: Record<string, string | number>) =>
  filterPipelines(snapshot, params).items.map((p) => p.id);

describe("filterPipelines", () => {
  it("defaults to newest first", () => {
    expect(ids({})).toEqual([5, 4, 3, 2, 1]);
  });

  it("filters by project, status and source", () => {
    expect(ids({ project_id: 1, status: "failed" })).toEqual([1]);
    expect(ids({ source: "merge_request_event" })).toEqual([2]);
  });

  it("scope=default uses each project's own default branch", () => {
    expect(ids({ scope: "default" })).toEqual([4, 3, 1]);
  });

  it("sorts by duration with nulls last", () => {
    expect(ids({ project_id: 1, sort: "-duration" })).toEqual([2, 1, 3]);
    expect(ids({ project_id: 1, sort: "duration" })).toEqual([1, 2, 3]);
  });

  it("paginates and reports the full total", () => {
    const page = filterPipelines(snapshot, { limit: 2, offset: 2 });
    expect(page.items.map((p) => p.id)).toEqual([3, 2]);
    expect(page.total).toBe(5);
  });
});
