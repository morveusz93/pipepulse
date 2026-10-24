import type { PulseRun } from "@/lib/types";
import { formatDuration, formatTimestamp, statusTone } from "@/lib/format";
import styles from "./Pulse.module.css";

const SLOTS = 20;
const BAR_WIDTH = 4;
const GAP = 3;
const HEIGHT = 28;
const MIN_BAR = 6;

/**
 * The signature element: one stripe per pipeline run, oldest on the left, read like an EKG.
 * - failures are full-height coral spikes (they usually end early, so sizing them by duration
 *   would make the most important runs the least visible)
 * - successful runs: height = duration on a log scale, normalized across the project's
 *   successful runs, so a slow-down shows as the line "swelling" even when everything passes
 * - running: mid-height amber, pulsing; canceled/skipped: short grey stubs
 */
export function Pulse({ runs, label }: { runs: PulseRun[]; label: string }) {
  const recent = runs.slice(-SLOTS);
  const heights = barHeights(recent);
  const padding = SLOTS - recent.length;
  const width = SLOTS * BAR_WIDTH + (SLOTS - 1) * GAP;

  const passed = recent.filter((r) => r.status === "success").length;
  const failed = recent.filter((r) => r.status === "failed").length;
  const summary = `${label}: last ${recent.length} runs, ${passed} passed, ${failed} failed`;

  return (
    <svg
      className={styles.pulse}
      width={width}
      height={HEIGHT}
      viewBox={`0 0 ${width} ${HEIGHT}`}
      role="img"
      aria-label={summary}
    >
      {Array.from({ length: padding }, (_, i) => (
        <circle
          key={`empty-${i}`}
          className={styles.empty}
          cx={i * (BAR_WIDTH + GAP) + BAR_WIDTH / 2}
          cy={HEIGHT / 2}
          r={1}
        />
      ))}
      {recent.map((run, i) => {
        const h = heights[i];
        const tone = statusTone(run.status);
        return (
          <rect
            key={run.id}
            className={`${styles.bar} ${styles[tone]}`}
            x={(padding + i) * (BAR_WIDTH + GAP)}
            y={(HEIGHT - h) / 2}
            width={BAR_WIDTH}
            height={h}
            rx={1.5}
          >
            <title>
              {`${run.status} · ${formatDuration(run.duration_s)} · ${formatTimestamp(run.created_at)} UTC`}
            </title>
          </rect>
        );
      })}
    </svg>
  );
}

// Successful runs span this range, leaving the full height to failure spikes.
const SUCCESS_MIN = 10;
const SUCCESS_MAX = HEIGHT - 6;

function barHeights(runs: PulseRun[]): number[] {
  const logs = runs
    .filter((r) => r.status === "success" && r.duration_s != null && r.duration_s > 0)
    .map((r) => Math.log(r.duration_s!));
  const min = Math.min(...logs);
  const max = Math.max(...logs);
  const middle = (SUCCESS_MIN + SUCCESS_MAX) / 2;

  return runs.map((run) => {
    switch (statusTone(run.status)) {
      case "failure":
        return HEIGHT;
      case "running":
        return middle;
      case "neutral":
        return MIN_BAR;
    }
    if (run.duration_s == null || !(max > min)) return middle;
    const t = (Math.log(run.duration_s) - min) / (max - min);
    return SUCCESS_MIN + t * (SUCCESS_MAX - SUCCESS_MIN);
  });
}
