import { Suspense } from "react";
import { AutoRefresh } from "@/components/AutoRefresh";
import { ProjectList } from "@/components/ProjectList";
import { SummaryBar } from "@/components/SummaryBar";
import { apiGet } from "@/lib/api";
import type { ActiveFailure } from "@/components/ProjectList";
import type { JobLog, PipelinePage, ProjectRow, Summary } from "@/lib/types";
import styles from "./page.module.css";

const WINDOW_DAYS = 7;

export default function Home() {
  return (
    <main className={styles.main}>
      <div className={styles.titleRow}>
        <h1 className={styles.title}>Pipeline health</h1>
        <span className={styles.caption}>Default branches · last {WINDOW_DAYS} days</span>
      </div>
      <Suspense fallback={<DashboardSkeleton />}>
        <Dashboard />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

async function loadDashboard() {
  const [summary, projects] = await Promise.all([
    apiGet<Summary>("/api/summary", { days: WINDOW_DAYS }),
    apiGet<ProjectRow[]>("/api/projects", { days: WINDOW_DAYS }),
  ]);
  const failures = await loadActiveFailures(projects.filter((p) => p.active_failure));
  return { summary, projects, failures, loadedAt: Date.now() };
}

/** Newest red default-branch pipeline of each failing project, with its first job's log. */
async function loadActiveFailures(failing: ProjectRow[]): Promise<Record<number, ActiveFailure>> {
  const entries = await Promise.all(
    failing.map(async (project) => {
      const page = await apiGet<PipelinePage>("/api/pipelines", {
        project_id: project.id,
        status: "failed",
        scope: "default",
        limit: 1,
      });
      const job = page.items[0]?.failed_jobs[0];
      if (!job) return null;
      const log = job.has_log ? await apiGet<JobLog>(`/api/jobs/${job.id}/log`) : null;
      return [project.id, { job, log: log?.log ?? null }] as const;
    }),
  );
  return Object.fromEntries(entries.filter((e) => e !== null));
}

async function Dashboard() {
  const { summary, projects, failures, loadedAt } = await loadDashboard();
  return (
    <div className={styles.stack}>
      <SummaryBar summary={summary} projects={projects} />
      <ProjectList projects={projects} failures={failures} days={WINDOW_DAYS} now={loadedAt} />
    </div>
  );
}

function DashboardSkeleton() {
  return (
    <div className={styles.stack} aria-busy="true" aria-label="Loading dashboard">
      <div className={`${styles.skeleton} ${styles.skeletonSummary}`} />
      <div className={`${styles.skeleton} ${styles.skeletonList}`} />
    </div>
  );
}
