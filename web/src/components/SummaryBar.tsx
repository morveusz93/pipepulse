import type { ProjectRow, Summary } from "@/lib/types";
import { formatDuration, formatPercent } from "@/lib/format";
import { Stat, StatStrip, Tone } from "./StatStrip";

export function SummaryBar({ summary, projects }: { summary: Summary; projects: ProjectRow[] }) {
  const failing = projects.filter((p) => p.active_failure).map((p) => p.name);
  const { stats, window_days: days } = summary;

  return (
    <StatStrip label="Summary">
      <Stat label="Projects" value={String(summary.projects)}>
        {summary.running > 0 ? (
          <Tone tone="running">{summary.running} running now</Tone>
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
    </StatStrip>
  );
}
