import Link from "next/link";
import { Fragment } from "react";
import { errorExcerpt } from "@/lib/ansi";
import type { JobOut, ProjectRow } from "@/lib/types";
import {
  ACTIVE_STATUSES,
  formatDuration,
  formatPercent,
  formatRelative,
} from "@/lib/format";
import { DeleteProjectButton } from "./DeleteProjectButton";
import { LogViewer } from "./LogViewer";
import { Pulse } from "./Pulse";
import { StatusBadge } from "./StatusBadge";
import styles from "./ProjectList.module.css";

/** Failing first, then building, then alphabetical: what needs attention floats up. */
function byAttention(a: ProjectRow, b: ProjectRow): number {
  const rank = (p: ProjectRow) =>
    p.active_failure
      ? 0
      : p.latest && ACTIVE_STATUSES.has(p.latest.status)
        ? 1
        : 2;
  return rank(a) - rank(b) || a.name.localeCompare(b.name);
}

export interface ActiveFailure {
  job: JobOut;
  log: string | null;
}

export function ProjectList({
  projects,
  failures,
  days,
  now,
}: {
  projects: ProjectRow[];
  /** Keyed by project id; only projects with an active failure. */
  failures: Record<number, ActiveFailure>;
  days: number;
  /** Render time, for "12m ago". Passed in so rendering stays pure. */
  now: number;
}) {
  const tracked = projects.filter((p) => !p.removed_at);
  const removed = projects.filter((p) => p.removed_at);

  return (
    <>
      {tracked.length === 0 ? (
        <div className={styles.empty}>
          No projects yet. Set <code>PIPEPULSE_GITLAB_TOKEN</code>; the worker picks up your
          projects within a couple of minutes.
        </div>
      ) : (
        <TrackedProjects projects={tracked} failures={failures} days={days} now={now} />
      )}
      {removed.length > 0 && <RemovedProjects projects={removed} now={now} />}
    </>
  );
}

function TrackedProjects({
  projects,
  failures,
  days,
  now,
}: {
  projects: ProjectRow[];
  failures: Record<number, ActiveFailure>;
  days: number;
  now: number;
}) {
  return (
    <section className={styles.table} aria-label="Projects">
      <div className={`${styles.row} ${styles.head}`} role="presentation">
        <span>Project</span>
        <span>Pulse · last 20</span>
        <span>Status</span>
        <span className={styles.num}>Duration</span>
        <span className={styles.num}>Last run</span>
        <span className={styles.num}>Success · {days}d</span>
      </div>
      {[...projects].sort(byAttention).map((project) => (
        <Fragment key={project.id}>
          <Link
            href={`/projects/${project.id}`}
            className={`${styles.row} ${project.active_failure ? styles.failing : ""}`}
          >
            <span className={styles.project}>
              <span className={styles.name}>{project.name}</span>
              <span className={styles.path}>
                {project.path_with_namespace}
                {project.default_branch && (
                  <span className="mono"> · {project.default_branch}</span>
                )}
              </span>
            </span>
            <span className={styles.pulse}>
              <Pulse runs={project.pulse} label={project.name} />
            </span>
            <span>
              {project.latest ? (
                <StatusBadge status={project.latest.status} />
              ) : (
                "—"
              )}
            </span>
            <span className={`${styles.num} mono`}>
              {project.latest && ACTIVE_STATUSES.has(project.latest.status)
                ? "…"
                : formatDuration(project.latest?.duration_s)}
            </span>
            <span className={`${styles.num} ${styles.muted} mono`}>
              {project.latest
                ? formatRelative(project.latest.created_at, now)
                : "—"}
            </span>
            <span className={`${styles.num} mono`}>
              {formatPercent(project.stats.success_rate)}
            </span>
          </Link>
          {failures[project.id] && (
            <FailurePreview
              project={project.name}
              failure={failures[project.id]}
            />
          )}
        </Fragment>
      ))}
    </section>
  );
}

/** "└ test:e2e  Error: Cannot find module './auth'" under a failing row; expands to the log. */
function FailurePreview({
  project,
  failure,
}: {
  project: string;
  failure: ActiveFailure;
}) {
  const excerpt = failure.log ? errorExcerpt(failure.log) : null;
  const summary = (
    <>
      <span className={styles.branch} aria-hidden>
        └
      </span>
      <span className={`${styles.job} mono`}>{failure.job.name}</span>
      <span className={`${styles.excerpt} mono`}>
        {excerpt ??
          failure.job.failure_reason?.replaceAll("_", " ") ??
          "failed"}
      </span>
      {failure.log && <span className={styles.toggle}>log</span>}
    </>
  );

  if (!failure.log) {
    return (
      <div className={`${styles.failure} ${styles.failureStatic}`}>
        {summary}
      </div>
    );
  }
  return (
    <details className={styles.failureDetails}>
      <summary className={styles.failure}>{summary}</summary>
      <div className={styles.failureLog}>
        <LogViewer
          log={failure.log}
          label={`Log of ${failure.job.name} in ${project}`}
        />
      </div>
    </details>
  );
}

/** Projects dropped from the configuration: no longer polled, history kept until deleted. */
function RemovedProjects({ projects, now }: { projects: ProjectRow[]; now: number }) {
  return (
    <section className={styles.removed} aria-labelledby="removed-projects">
      <h2 id="removed-projects" className={styles.removedTitle}>
        Removed from configuration
        <span className={styles.removedHint}>
          not polled anymore; history is kept until you delete it
        </span>
      </h2>
      {projects.map((project) => (
        <div key={project.id} className={styles.removedRow}>
          <Link href={`/projects/${project.id}`} className={styles.project}>
            <span className={styles.name}>{project.name}</span>
            <span className={styles.path}>{project.path_with_namespace}</span>
          </Link>
          <span className={styles.pulse}>
            <Pulse runs={project.pulse} label={project.name} />
          </span>
          <span className={`${styles.muted} mono`}>
            removed {formatRelative(project.removed_at!, now)}
          </span>
          <DeleteProjectButton projectId={project.id} path={project.path_with_namespace} />
        </div>
      ))}
    </section>
  );
}
