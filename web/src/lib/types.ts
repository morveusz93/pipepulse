// Mirrors api/src/pipepulse/schemas.py.

export type Scope = "default" | "all";

export type PipelineStatus =
  | "success"
  | "failed"
  | "running"
  | "pending"
  | "created"
  | "waiting_for_resource"
  | "preparing"
  | "canceled"
  | "skipped"
  | "manual"
  | "scheduled"
  | (string & {});

export interface PipelineBrief {
  id: number;
  gitlab_pipeline_id: number;
  status: PipelineStatus;
  ref: string;
  duration_s: number | null;
  created_at: string;
  finished_at: string | null;
  web_url: string;
}

export interface PulseRun {
  id: number;
  status: PipelineStatus;
  duration_s: number | null;
  created_at: string;
}

export interface WindowStats {
  runs: number;
  succeeded: number;
  failed: number;
  success_rate: number | null;
  avg_duration_s: number | null;
}

export interface ProjectRow {
  id: number;
  name: string;
  path_with_namespace: string;
  web_url: string;
  default_branch: string | null;
  is_demo: boolean;
  last_polled_at: string | null;
  latest: PipelineBrief | null;
  active_failure: boolean;
  pulse: PulseRun[];
  stats: WindowStats;
}

export interface Summary {
  window_days: number;
  projects: number;
  active_failures: number;
  running: number;
  stats: WindowStats;
}

export interface AuthState {
  demo_mode: boolean;
  admin_enabled: boolean;
  authenticated: boolean;
}

export interface TrendPoint {
  day: string;
  runs: number;
  succeeded: number;
  failed: number;
  success_rate: number | null;
  avg_duration_s: number | null;
  p90_duration_s: number | null;
}

export interface Incident {
  failed_at: string;
  recovered_at: string | null;
  duration_s: number | null;
}

export interface Mttr {
  incidents: number;
  recovered: number;
  avg_s: number | null;
  median_s: number | null;
  max_s: number | null;
  open_since: string | null;
  history: Incident[];
}

export interface ProjectStats {
  window_days: number;
  scope: Scope;
  current: WindowStats;
  previous: WindowStats;
  mttr: Mttr;
}

export interface JobOut {
  id: number;
  gitlab_job_id: number;
  name: string;
  stage: string;
  status: string;
  failure_reason: string | null;
  duration_s: number | null;
  web_url: string;
  finished_at: string | null;
  has_log: boolean;
}

export interface PipelineOut extends PipelineBrief {
  project_id: number;
  project_name: string;
  sha: string;
  source: string | null;
  commit_title: string | null;
  queued_duration_s: number | null;
  started_at: string | null;
  failed_jobs: JobOut[];
}

export interface PipelinePage {
  items: PipelineOut[];
  total: number;
  limit: number;
  offset: number;
}

export interface JobLog {
  job: JobOut;
  pipeline_id: number;
  log: string | null;
}
