import Link from "next/link";
import type { ProjectRow } from "@/lib/types";
import { ACTIVE_STATUSES, formatDuration, formatPercent, formatRelative } from "@/lib/format";
import { Pulse } from "./Pulse";
import { StatusBadge } from "./StatusBadge";
import styles from "./ProjectList.module.css";

/** Failing first, then building, then alphabetical: what needs attention floats up. */
function byAttention(a: ProjectRow, b: ProjectRow): number {
  const rank = (p: ProjectRow) =>
    p.active_failure ? 0 : p.latest && ACTIVE_STATUSES.has(p.latest.status) ? 1 : 2;
  return rank(a) - rank(b) || a.name.localeCompare(b.name);
}

export function ProjectList({
  projects,
  days,
  now,
}: {
  projects: ProjectRow[];
  days: number;
  /** Render time, for "12m ago". Passed in so rendering stays pure. */
  now: number;
}) {
  if (projects.length === 0) {
    return (
      <div className={styles.empty}>
        No projects yet. Connect a GitLab instance and add projects to start tracking pipelines.
      </div>
    );
  }

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
        <Link
          key={project.id}
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
          <span>{project.latest ? <StatusBadge status={project.latest.status} /> : "—"}</span>
          <span className={`${styles.num} mono`}>
            {project.latest && ACTIVE_STATUSES.has(project.latest.status)
              ? "…"
              : formatDuration(project.latest?.duration_s)}
          </span>
          <span className={`${styles.num} ${styles.muted} mono`}>
            {project.latest ? formatRelative(project.latest.created_at, now) : "—"}
          </span>
          <span className={`${styles.num} mono`}>{formatPercent(project.stats.success_rate)}</span>
        </Link>
      ))}
    </section>
  );
}
