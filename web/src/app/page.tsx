import { Suspense } from "react";
import { AutoRefresh } from "@/components/AutoRefresh";
import { ProjectList } from "@/components/ProjectList";
import { SummaryBar } from "@/components/SummaryBar";
import { apiGet } from "@/lib/api";
import type { ProjectRow, Summary } from "@/lib/types";
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
  return { summary, projects, loadedAt: Date.now() };
}

async function Dashboard() {
  const { summary, projects, loadedAt } = await loadDashboard();
  return (
    <div className={styles.stack}>
      <SummaryBar summary={summary} projects={projects} />
      <ProjectList projects={projects} days={WINDOW_DAYS} now={loadedAt} />
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
