import Link from "next/link";
import { notFound } from "next/navigation";
import { Suspense } from "react";
import { AutoRefresh } from "@/components/AutoRefresh";
import { Incidents } from "@/components/Incidents";
import { PipelineTable } from "@/components/PipelineTable";
import { Pulse } from "@/components/Pulse";
import { Stat, StatStrip, Tone } from "@/components/StatStrip";
import { StatusBadge } from "@/components/StatusBadge";
import { TrendCharts } from "@/components/TrendCharts";
import { ApiError, apiGet } from "@/lib/api";
import { formatDuration, formatPercent, formatTimestamp } from "@/lib/format";
import type { PipelinePage, ProjectRow, ProjectStats, TrendPoint } from "@/lib/types";
import styles from "./page.module.css";

const WINDOWS = [7, 30, 90] as const;
const DEFAULT_WINDOW = 30;
const RECENT_PIPELINES = 30;

export default function ProjectPage(props: PageProps<"/projects/[id]">) {
  return (
    <main className={styles.main}>
      <Link href="/" className={styles.back}>
        ← All projects
      </Link>
      <Suspense fallback={<div className={styles.skeleton} aria-busy="true" />}>
        <ProjectView params={props.params} searchParams={props.searchParams} />
      </Suspense>
      <AutoRefresh />
    </main>
  );
}

function parseWindow(value: string | string[] | undefined): number {
  const days = Number(Array.isArray(value) ? value[0] : value);
  return (WINDOWS as readonly number[]).includes(days) ? days : DEFAULT_WINDOW;
}

async function loadProject(id: string, days: number) {
  try {
    const [project, stats, trend, pipelines] = await Promise.all([
      apiGet<ProjectRow>(`/api/projects/${id}`, { days }),
      apiGet<ProjectStats>(`/api/projects/${id}/stats`, { days }),
      apiGet<TrendPoint[]>(`/api/projects/${id}/trend`, { days }),
      apiGet<PipelinePage>("/api/pipelines", { project_id: id, limit: RECENT_PIPELINES }),
    ]);
    return { project, stats, trend, pipelines, loadedAt: Date.now() };
  } catch (error) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) return null;
    throw error;
  }
}

async function ProjectView({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [{ id }, query] = await Promise.all([params, searchParams]);
  const days = parseWindow(query.days);
  const data = await loadProject(id, days);
  if (!data) notFound();
  const { project, stats, trend, pipelines, loadedAt } = data;

  return (
    <div className={styles.stack}>
      <header className={styles.header}>
        <div className={styles.identity}>
          <h1 className={styles.title}>{project.name}</h1>
          <div className={styles.subtitle}>
            <span>{project.path_with_namespace}</span>
            {project.default_branch && <span className="mono">{project.default_branch}</span>}
            {project.latest && <StatusBadge status={project.latest.status} />}
            {!project.is_demo && (
              <a href={project.web_url} target="_blank" rel="noreferrer" className={styles.external}>
                Open in GitLab ↗
              </a>
            )}
          </div>
        </div>
        <div className={styles.headerSide}>
          <Pulse runs={project.pulse} label={project.name} />
          <nav className={styles.windows} aria-label="Time window">
            {WINDOWS.map((w) => (
              <Link
                key={w}
                href={`?days=${w}`}
                className={styles.window}
                aria-current={w === days ? "page" : undefined}
                scroll={false}
              >
                {w}d
              </Link>
            ))}
          </nav>
        </div>
      </header>

      <StatsRow stats={stats} days={days} now={loadedAt} />

      <TrendCharts points={trend} />

      <section className={styles.panel}>
        <h2 className={styles.panelTitle}>
          Incidents on {project.default_branch ?? "the default branch"}
          <span className={styles.panelHint}>from first failure to the next green pipeline</span>
        </h2>
        <Incidents incidents={stats.mttr.history} now={loadedAt} />
      </section>

      <section>
        <h2 className={styles.sectionTitle}>
          Recent pipelines
          <span className={styles.panelHint}>all refs · click a failed one to see its logs</span>
        </h2>
        <PipelineTable
          pipelines={pipelines.items}
          defaultBranch={project.default_branch}
          now={loadedAt}
        />
      </section>
    </div>
  );
}

function StatsRow({ stats, days, now }: { stats: ProjectStats; days: number; now: number }) {
  const { current, previous, mttr } = stats;

  const rateDelta =
    current.success_rate != null && previous.success_rate != null
      ? (current.success_rate - previous.success_rate) * 100
      : null;
  const durationDelta =
    current.avg_duration_s != null && previous.avg_duration_s
      ? (current.avg_duration_s - previous.avg_duration_s) / previous.avg_duration_s
      : null;

  return (
    <StatStrip label="Project statistics">
      <Stat label={`Success rate · ${days}d`} value={formatPercent(current.success_rate)}>
        {rateDelta == null ? (
          "no previous data"
        ) : (
          <Tone tone={rateDelta > 0.5 ? "success" : rateDelta < -0.5 ? "failure" : undefined}>
            {rateDelta >= 0 ? "+" : "−"}
            {Math.abs(rateDelta).toFixed(1)} pp vs previous {days}d
          </Tone>
        )}
      </Stat>
      <Stat label="Avg duration" value={formatDuration(current.avg_duration_s)}>
        {durationDelta == null ? (
          "no previous data"
        ) : Math.abs(durationDelta) < 0.005 ? (
          `same as previous ${days}d`
        ) : (
          <Tone
            tone={durationDelta > 0.05 ? "failure" : durationDelta < -0.05 ? "success" : undefined}
          >
            {Math.abs(durationDelta * 100).toFixed(0)}% {durationDelta >= 0 ? "slower" : "faster"}{" "}
            vs previous {days}d
          </Tone>
        )}
      </Stat>
      <Stat label="Runs" value={String(current.runs)}>
        {current.succeeded} passed · {current.failed} failed
      </Stat>
      {mttr.open_since ? (
        <Stat
          label="Failing for"
          value={formatDuration((now - Date.parse(mttr.open_since)) / 1000)}
          tone="failure"
        >
          since {formatTimestamp(mttr.open_since)} UTC
        </Stat>
      ) : (
        <Stat label="MTTR · median" value={formatDuration(mttr.median_s)}>
          {mttr.recovered > 0
            ? `worst ${formatDuration(mttr.max_s)} · ${mttr.recovered} incident${mttr.recovered === 1 ? "" : "s"}`
            : "no incidents"}
        </Stat>
      )}
    </StatStrip>
  );
}
