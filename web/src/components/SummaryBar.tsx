import type { ProjectRow, Summary } from "@/lib/types";
import { formatDuration, formatPercent } from "@/lib/format";
import styles from "./SummaryBar.module.css";

export function SummaryBar({ summary, projects }: { summary: Summary; projects: ProjectRow[] }) {
  const failing = projects.filter((p) => p.active_failure).map((p) => p.name);
  const { stats, window_days: days } = summary;

  return (
    <section className={styles.bar} aria-label="Summary">
      <Stat label="Projects" value={String(summary.projects)}>
        {summary.running > 0 ? (
          <span className={styles.running}>{summary.running} running now</span>
        ) : (
          "none running"
        )}
      </Stat>
      <Stat
        label="Active failures"
        value={String(summary.active_failures)}
        tone={summary.active_failures > 0 ? "failure" : undefined}
      >
        {failing.length > 0 ? failing.join(", ") : "all default branches green"}
      </Stat>
      <Stat label="Avg build" value={formatDuration(stats.avg_duration_s)}>
        successful runs, {days}d
      </Stat>
      <Stat label={`Success rate · ${days}d`} value={formatPercent(stats.success_rate)}>
        {stats.succeeded} passed · {stats.failed} failed
      </Stat>
    </section>
  );
}

function Stat({
  label,
  value,
  tone,
  children,
}: {
  label: string;
  value: string;
  tone?: "failure";
  children: React.ReactNode;
}) {
  return (
    <div className={styles.stat}>
      <div className={styles.label}>{label}</div>
      <div className={`${styles.value} mono ${tone ? styles[tone] : ""}`}>{value}</div>
      <div className={styles.sub}>{children}</div>
    </div>
  );
}
