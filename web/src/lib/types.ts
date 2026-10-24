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
